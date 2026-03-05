#!/bin/bash
#
# GLM-OCR: Setup Google Cloud cho Cloud Run deployment
# Chạy 1 lần để cấu hình project
#
set -e

# ============================
# CẤU HÌNH — CHỈNH SỬA Ở ĐÂY
# ============================
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="asia-southeast1"
SERVICE_NAME="glm-ocr-app"
REPO_NAME="glm-ocr"
# ============================

echo "═══════════════════════════════════════════"
echo "  GLM-OCR — Google Cloud Setup"
echo "═══════════════════════════════════════════"
echo ""
echo "  Project:  $PROJECT_ID"
echo "  Region:   $REGION"
echo ""

# Set project
gcloud config set project "$PROJECT_ID"

# Enable APIs
echo "📦 Enabling APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    drive.googleapis.com

# Create Artifact Registry repo
echo "📦 Creating Docker repository..."
gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker \
    --location="$REGION" \
    --description="GLM-OCR Docker images" \
    2>/dev/null || echo "   (Repository already exists)"

# Create Service Account for GitHub Actions
echo "🔑 Creating Service Account..."
SA_NAME="github-deploy"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$SA_NAME" \
    --display-name="GitHub Actions Deploy" \
    2>/dev/null || echo "   (Service Account already exists)"

# Grant roles
echo "🔑 Granting roles..."
for ROLE in \
    roles/run.admin \
    roles/storage.admin \
    roles/artifactregistry.writer \
    roles/iam.serviceAccountUser; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$ROLE" \
        --quiet
done

# Create key
echo "🔑 Creating Service Account key..."
KEY_FILE="/tmp/gcp-sa-key.json"
gcloud iam service-accounts keys create "$KEY_FILE" \
    --iam-account="$SA_EMAIL"

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════"
echo ""
echo "  TIẾP THEO — Cấu hình GitHub Secrets:"
echo ""
echo "  1. Vào GitHub repo → Settings → Secrets → Actions"
echo ""
echo "  2. Thêm các secrets sau:"
echo "     GCP_PROJECT_ID = $PROJECT_ID"
echo "     GCP_SA_KEY     = (nội dung file $KEY_FILE)"
echo "     ZHIPU_API_KEY  = (API key từ open.bigmodel.cn)"
echo "     APP_PASSWORD   = (mật khẩu đăng nhập app)"
echo ""
echo "  3. (Tùy chọn) Nếu dùng Google Drive:"
echo "     GOOGLE_DRIVE_ENABLED   = true"
echo "     DRIVE_INPUT_FOLDER_ID  = (ID folder Drive input)"
echo "     DRIVE_OUTPUT_FOLDER_ID = (ID folder Drive output)"
echo "     DRIVE_CREDENTIALS_JSON = (base64 encode credentials.json)"
echo ""
echo "  4. Push code lên GitHub:"
echo "     git init && git add . && git commit -m 'init'"
echo "     git remote add origin https://github.com/YOUR/REPO.git"
echo "     git push -u origin main"
echo ""
echo "  → GitHub Actions sẽ tự động build & deploy!"
echo ""
echo "  💡 Hoặc deploy thủ công:"
echo "     gcloud run deploy $SERVICE_NAME \\"
echo "       --source . --region $REGION"
echo ""
