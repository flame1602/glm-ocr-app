# Cấu hình Google Drive Sync

## 1. Tạo Service Account

```bash
# Tạo Service Account
gcloud iam service-accounts create drive-sync \
    --display-name="GLM-OCR Drive Sync"

# Tạo key
gcloud iam service-accounts keys create credentials.json \
    --iam-account=drive-sync@YOUR-PROJECT.iam.gserviceaccount.com
```

## 2. Tạo Folder trên Google Drive

1. Tạo 2 folder trên Google Drive:
   - **GLM-OCR Input**: nơi đặt file PDF cần OCR
   - **GLM-OCR Output**: nơi nhận file markdown kết quả

2. **Share cả 2 folder** cho Service Account email:
   - Nhấn phải vào folder → Share
   - Nhập email: `drive-sync@YOUR-PROJECT.iam.gserviceaccount.com`
   - Quyền: **Editor**

3. **Lấy Folder ID**: mở folder, URL sẽ có dạng:
   ```
   https://drive.google.com/drive/folders/1ABC...XYZ
   ```
   `1ABC...XYZ` chính là Folder ID.

## 3. Cấu hình secrets

```bash
# Base64 encode credentials
cat credentials.json | base64

# Thêm vào GitHub Secrets:
GOOGLE_DRIVE_ENABLED   = true
DRIVE_INPUT_FOLDER_ID  = (ID folder Input)
DRIVE_OUTPUT_FOLDER_ID = (ID folder Output)
DRIVE_CREDENTIALS_JSON = (base64 string ở trên)
```

## 4. Cách sử dụng

1. Đặt file PDF vào folder **GLM-OCR Input** trên Drive
2. Hệ thống tự động pull PDF → OCR → upload markdown vào **GLM-OCR Output**
3. File PDF đã xử lý sẽ được chuyển vào subfolder `processed/`
4. Theo dõi trạng thái trên tab **Google Drive** trong app

> 💡 Mặc định hệ thống sync mỗi 60 giây. Có thể điều chỉnh qua env var `DRIVE_SYNC_INTERVAL`.
