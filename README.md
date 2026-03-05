# GLM-OCR — Hệ thống OCR dữ liệu

Ứng dụng web OCR PDF → Markdown cho công ty, sử dụng mô hình [GLM-OCR](https://github.com/zai-org/GLM-OCR) qua Zhipu MaaS API.

## ✨ Tính năng

- **📤 Upload PDF** — Kéo thả hoặc chọn file, hỗ trợ nhiều file
- **🔍 OCR tự động** — Chuyển đổi PDF sang Markdown chất lượng cao
- **📊 Dashboard** — Thống kê, biểu đồ, lịch sử xử lý
- **📁 Google Drive** — Batch processing tự động từ Google Drive
- **📦 Download** — Tải markdown riêng lẻ hoặc ZIP tất cả
- **🔐 Bảo mật** — Mật khẩu đăng nhập

## 🏗️ Kiến trúc

```
GitHub push → GitHub Actions → Cloud Build → Cloud Run (Flask + MaaS API)
```

- **Backend**: Flask (Python)
- **OCR**: Zhipu MaaS API (GLM-OCR model, không cần GPU)
- **Hosting**: Google Cloud Run (serverless, tự scale)
- **CI/CD**: GitHub Actions
- **Database**: SQLite (job history)

## 🚀 Deploy

### 1. Chuẩn bị

- Google Cloud project (đã có)
- API key từ [open.bigmodel.cn](https://open.bigmodel.cn)
- GitHub repository

### 2. Setup Google Cloud (chạy 1 lần)

```bash
# Đặt Project ID
export GCP_PROJECT_ID="your-project-id"

# Chạy setup
bash setup/setup_gcloud.sh
```

### 3. Cấu hình GitHub Secrets

Vào repo GitHub → Settings → Secrets and variables → Actions:

| Secret | Giá trị | Bắt buộc |
|--------|---------|----------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | ✅ |
| `GCP_SA_KEY` | Service Account key JSON | ✅ |
| `ZHIPU_API_KEY` | API key từ Zhipu | ✅ |
| `APP_PASSWORD` | Mật khẩu đăng nhập app | ✅ |
| `GOOGLE_DRIVE_ENABLED` | `true` để bật Drive sync | ❌ |
| `DRIVE_INPUT_FOLDER_ID` | ID folder Drive chứa PDF | ❌ |
| `DRIVE_OUTPUT_FOLDER_ID` | ID folder Drive nhận markdown | ❌ |
| `DRIVE_CREDENTIALS_JSON` | Base64 encode credentials | ❌ |

### 4. Push & Deploy

```bash
git init
git add .
git commit -m "GLM-OCR app"
git remote add origin https://github.com/YOUR/REPO.git
git push -u origin main
```

→ GitHub Actions sẽ tự động build Docker → deploy lên Cloud Run!

### Deploy thủ công

```bash
gcloud run deploy glm-ocr-app --source . --region asia-southeast1
```

## 📁 Google Drive Batch

Xem [setup/setup_drive.md](setup/setup_drive.md) để cấu hình.

## 🏃 Chạy local

```bash
pip install -r requirements.txt
export ZHIPU_API_KEY="your-key"
export DATA_DIR="./data"
python app.py
```


## 📁 Cấu trúc

```
glm-ocr-app/
├── app.py                 # Flask server
├── config.py              # Cấu hình
├── db.py                  # SQLite job history
├── drive_sync.py          # Google Drive sync
├── Dockerfile             # Docker image
├── requirements.txt       # Python deps
├── .github/workflows/
│   └── deploy.yml         # GitHub Actions CI/CD
├── setup/
│   ├── setup_gcloud.sh    # Google Cloud setup
│   └── setup_drive.md     # Drive setup guide
└── static/
    ├── index.html          # Main app UI
    └── login.html          # Login page
```

## 💰 Chi phí

| Thành phần | Chi phí |
|------------|---------|
| Cloud Run | ~$0 khi idle, ~$0.0001/request |
| MaaS API | Xem pricing tại open.bigmodel.cn |
| Google Drive | Free |
| **Tổng** | **Rất thấp** (~vài USD/tháng) |
