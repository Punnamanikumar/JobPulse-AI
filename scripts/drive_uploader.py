"""
Google Drive Uploader — uploads reports and logs to Drive in date folders.

Structure created in Google Drive:
    JobPulse Reports/
    ├── 2026-02-22/
    │   ├── LinkedIn_India_Jobs_2026-02-22.xlsx
    │   ├── Naukri_India_Jobs_2026-02-22.xlsx
    │   └── run_log_2026-02-22.txt
    └── 2026-02-23/
        └── ...

Usage:
    from drive_uploader import upload_reports
    links = upload_reports()  # returns dict of {filename: web_link}
"""

import os
import glob
from datetime import date
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth import get_credentials

ROOT_FOLDER_NAME = "JobPulse Reports"
TODAY = date.today().isoformat()

# Cache root folder ID to avoid repeated lookups
_ROOT_FOLDER_ID_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".drive_folder_id"
)


def _get_drive_service():
    """Build and return a Drive API service."""
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


def _find_or_create_folder(service, name: str, parent_id: str = None) -> str:
    """Find a folder by name (under parent), or create it. Returns folder ID."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(
        q=query, spaces="drive", fields="files(id, name)", pageSize=1
    ).execute()

    files = results.get("files", [])
    if files:
        folder_id = files[0]["id"]
        print(f"   📂  Found existing folder: {name} ({folder_id[:12]}…)")
        return folder_id

    # Create folder
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    print(f"   📁  Created Drive folder: {name} ({folder_id[:12]}…)")
    return folder_id


def _get_root_folder_id(service) -> str:
    """Get or create the root 'JobPulse Reports' folder.
    Caches the ID in .drive_folder_id for subsequent runs.
    """
    # 1. Check env var (user-configured — must be a valid folder ID)
    custom_id = os.environ.get("DRIVE_FOLDER_ID", "").strip()
    if custom_id:
        try:
            service.files().get(fileId=custom_id, fields="id").execute()
            print(f"   📂  Using DRIVE_FOLDER_ID from env: {custom_id[:12]}…")
            return custom_id
        except Exception:
            print(f"   ⚠️  DRIVE_FOLDER_ID from env is invalid, ignoring…")

    # 2. Check cached ID file
    if os.path.exists(_ROOT_FOLDER_ID_FILE):
        cached_id = open(_ROOT_FOLDER_ID_FILE).read().strip()
        if cached_id:
            # Verify it still exists
            try:
                service.files().get(fileId=cached_id, fields="id").execute()
                print(f"   📂  Using cached root folder ID: {cached_id[:12]}…")
                return cached_id
            except Exception:
                print(f"   ⚠️  Cached folder ID invalid, searching…")

    # 3. Search or create
    folder_id = _find_or_create_folder(service, ROOT_FOLDER_NAME)

    # Cache it for future runs
    try:
        with open(_ROOT_FOLDER_ID_FILE, "w") as f:
            f.write(folder_id)
    except Exception:
        pass

    return folder_id


def _share_folder(service, folder_id: str, email: str):
    """Share a folder with a specific email (writer access)."""
    if not email:
        return
    try:
        # Directly create permission (skip listing — drive.file scope can't list others' perms)
        service.permissions().create(
            fileId=folder_id,
            body={
                "type": "user",
                "role": "writer",
                "emailAddress": email,
            },
            sendNotificationEmail=False,
        ).execute()
        print(f"   🔗  Shared Drive folder with {email}")
    except Exception as e:
        err_str = str(e).lower()
        # If already shared, ignore the error
        if "already" in err_str or "duplicate" in err_str:
            print(f"   ℹ️  Folder already shared with {email}")
        else:
            print(f"   ⚠️  Could not share folder with {email}: {e}")


def _upload_file(service, file_path: str, folder_id: str) -> dict:
    """Upload a single file to a Drive folder. Returns file metadata with webViewLink."""
    filename = os.path.basename(file_path)

    # Determine MIME type
    if filename.endswith(".xlsx"):
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif filename.endswith(".txt"):
        mime_type = "text/plain"
    else:
        mime_type = "application/octet-stream"

    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
    ).execute()

    print(f"   ☁️  Uploaded: {filename} → {file.get('webViewLink', 'N/A')}")
    return file


def upload_reports() -> dict:
    """Upload today's reports and logs to Google Drive.

    Returns:
        dict: {filename: webViewLink} for all uploaded files
    """
    print(f"\n📁  Uploading reports to Google Drive …")

    try:
        service = _get_drive_service()
    except Exception as e:
        print(f"   ⚠️  Drive upload skipped — auth failed: {e}")
        return {}

    # Get/create root folder (cached for reliability)
    root_id = _get_root_folder_id(service)

    # Share root folder with recipient
    recipient = os.environ.get("RECIPIENT_EMAIL", "").strip()
    _share_folder(service, root_id, recipient)

    # Get/create date subfolder
    date_folder_id = _find_or_create_folder(service, TODAY, parent_id=root_id)

    # Find files to upload
    files_to_upload = []

    # Excel reports
    for pattern in [
        f"reports/LinkedIn_India_Jobs_{TODAY}.xlsx",
        f"reports/Naukri_India_Jobs_{TODAY}.xlsx",
    ]:
        matches = glob.glob(pattern)
        if not matches:
            fallback = sorted(glob.glob(pattern.replace(TODAY, "*")))
            if fallback:
                matches = [fallback[-1]]
        files_to_upload.extend(matches)

    # Run log
    log_file = f"reports/run_log_{TODAY}.txt"
    if os.path.exists(log_file):
        files_to_upload.append(log_file)
    else:
        logs = sorted(glob.glob("reports/run_log_*.txt"))
        if logs:
            files_to_upload.append(logs[-1])

    if not files_to_upload:
        print("   ⚠️  No report files found to upload.")
        return {}

    # Upload each file
    links = {}
    for fpath in files_to_upload:
        try:
            result = _upload_file(service, fpath, date_folder_id)
            links[result["name"]] = result.get("webViewLink", "")
        except Exception as e:
            print(f"   ⚠️  Failed to upload {fpath}: {e}")

    # Get date folder link
    try:
        folder_info = service.files().get(
            fileId=date_folder_id, fields="webViewLink"
        ).execute()
        links["_folder"] = folder_info.get("webViewLink", "")
        print(f"   📂  Drive folder: {links['_folder']}")
    except Exception:
        pass

    print(f"   ✅  {len(links) - (1 if '_folder' in links else 0)} files uploaded to Drive.")
    return links
