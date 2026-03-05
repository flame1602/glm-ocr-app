"""
GLM-OCR App — Google Drive Sync Worker
Polls a Drive folder for new PDFs, processes them, uploads results.
"""
import os
import io
import json
import time
import base64
import threading
import traceback
from pathlib import Path

from config import (
    GOOGLE_DRIVE_ENABLED, DRIVE_CREDENTIALS_JSON,
    DRIVE_INPUT_FOLDER_ID, DRIVE_OUTPUT_FOLDER_ID,
    DRIVE_SYNC_INTERVAL, INPUT_DIR, OUTPUT_DIR
)

drive_state = {
    "enabled": False,
    "running": False,
    "last_sync": 0,
    "files_synced": 0,
    "errors": [],
    "status": "disabled",
}
drive_lock = threading.Lock()

_service = None


def _get_drive_service():
    """Build Google Drive API service from credentials."""
    global _service
    if _service:
        return _service
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if not DRIVE_CREDENTIALS_JSON:
            raise ValueError("DRIVE_CREDENTIALS_JSON not set")

        creds_data = json.loads(base64.b64decode(DRIVE_CREDENTIALS_JSON))
        creds = service_account.Credentials.from_service_account_info(
            creds_data,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        _service = build("drive", "v3", credentials=creds)
        return _service
    except Exception as e:
        print(f"❌ Drive auth error: {e}")
        raise


def list_drive_pdfs(folder_id):
    """List PDF files in a Drive folder."""
    service = _get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false",
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
        pageSize=100
    ).execute()
    return results.get("files", [])


def download_from_drive(file_id, dest_path):
    """Download a file from Drive."""
    from googleapiclient.http import MediaIoBaseDownload
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def upload_to_drive(file_path, folder_id, filename=None):
    """Upload a file to a Drive folder."""
    from googleapiclient.http import MediaFileUpload
    service = _get_drive_service()
    file_metadata = {
        "name": filename or os.path.basename(file_path),
        "parents": [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id,name"
    ).execute()
    return uploaded


def move_to_processed(file_id, folder_id):
    """Move processed file to a 'processed' subfolder in Drive."""
    service = _get_drive_service()
    # Find or create 'processed' subfolder
    results = service.files().list(
        q=f"'{folder_id}' in parents and name='processed' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id)"
    ).execute()
    folders = results.get("files", [])
    if folders:
        proc_id = folders[0]["id"]
    else:
        meta = {"name": "processed", "mimeType": "application/vnd.google-apps.folder", "parents": [folder_id]}
        proc_folder = service.files().create(body=meta, fields="id").execute()
        proc_id = proc_folder["id"]

    # Move file
    service.files().update(
        fileId=file_id,
        addParents=proc_id,
        removeParents=folder_id,
        fields="id,parents"
    ).execute()


def sync_once(ocr_func):
    """Run one sync cycle: download PDFs → OCR → upload results."""
    if not DRIVE_INPUT_FOLDER_ID:
        return 0

    with drive_lock:
        drive_state["running"] = True
        drive_state["status"] = "syncing"

    count = 0
    try:
        pdfs = list_drive_pdfs(DRIVE_INPUT_FOLDER_ID)
        for pdf_info in pdfs:
            file_id = pdf_info["id"]
            filename = pdf_info["name"]
            local_path = os.path.join(INPUT_DIR, f"drive_{filename}")

            try:
                # Download
                download_from_drive(file_id, local_path)

                # OCR
                md_path = ocr_func(local_path, source="google_drive")

                # Upload result if output folder configured
                if md_path and DRIVE_OUTPUT_FOLDER_ID:
                    upload_to_drive(md_path, DRIVE_OUTPUT_FOLDER_ID)

                # Move to processed
                move_to_processed(file_id, DRIVE_INPUT_FOLDER_ID)
                count += 1

            except Exception as e:
                print(f"❌ Drive sync error for {filename}: {e}")
                traceback.print_exc()
                with drive_lock:
                    drive_state["errors"].append({
                        "file": filename,
                        "error": str(e)[:200],
                        "time": time.time()
                    })
                    # Keep only last 20 errors
                    drive_state["errors"] = drive_state["errors"][-20:]

            finally:
                # Cleanup local temp
                if os.path.exists(local_path):
                    os.remove(local_path)

    except Exception as e:
        print(f"❌ Drive sync cycle error: {e}")
        traceback.print_exc()

    with drive_lock:
        drive_state["running"] = False
        drive_state["last_sync"] = time.time()
        drive_state["files_synced"] += count
        drive_state["status"] = "idle"

    return count


def start_sync_worker(ocr_func):
    """Start background sync thread."""
    if not GOOGLE_DRIVE_ENABLED:
        print("📁 Google Drive sync: disabled")
        return

    with drive_lock:
        drive_state["enabled"] = True
        drive_state["status"] = "starting"

    def worker():
        print(f"📁 Google Drive sync: started (interval={DRIVE_SYNC_INTERVAL}s)")
        with drive_lock:
            drive_state["status"] = "idle"
        while True:
            try:
                sync_once(ocr_func)
            except Exception as e:
                print(f"❌ Drive worker error: {e}")
            time.sleep(DRIVE_SYNC_INTERVAL)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def get_drive_status():
    with drive_lock:
        return dict(drive_state)
