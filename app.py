"""
GLM-OCR Web App — Flask server with MaaS API, Google Drive sync, job history.
Deployed on Google Cloud Run via GitHub Actions.
"""
import os
import time
import glob
import base64
import shutil
import threading
import traceback
from pathlib import Path
from functools import wraps

from flask import (
    Flask, request, jsonify, send_file, send_from_directory,
    session, redirect, url_for
)
from werkzeug.middleware.proxy_fix import ProxyFix
import fitz  # PyMuPDF

import config
import db
from drive_sync import start_sync_worker, get_drive_status

# === OCR State (real-time progress for current batch) ===
ocr_state = {
    "running": False, "current_file": "", "current_page": 0, "total_pages": 0,
    "files_done": 0, "files_total": 0, "results": [], "error": None, "start_time": 0
}
state_lock = threading.Lock()


# === Auth ===
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# === OCR via MaaS API ===
def pdf_to_images(pdf_path):
    """Convert PDF pages to PNG images."""
    doc = fitz.open(pdf_path)
    imgs = []
    td = f"/tmp/pdf_pages/{Path(pdf_path).stem}"
    os.makedirs(td, exist_ok=True)
    zoom = config.DPI / 72
    for i in range(len(doc)):
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        p = os.path.join(td, f"p_{i+1:04d}.png")
        pix.save(p)
        imgs.append(p)
    doc.close()
    return imgs


def ocr_page_maas(img_path):
    """OCR a single page image via Zhipu MaaS API."""
    from openai import OpenAI
    client = OpenAI(api_key=config.ZHIPU_API_KEY, base_url=config.ZHIPU_API_BASE)
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    resp = client.chat.completions.create(
        model=config.OCR_MODEL,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": "Text Recognition:"}
        ]}],
        max_tokens=8192, temperature=0.01
    )
    return resp.choices[0].message.content


def ocr_single_file(pdf_path, source="upload"):
    """Process a single PDF file: convert → OCR → save markdown. Returns output path."""
    pdf_name = Path(pdf_path).stem
    job_id = db.add_job(Path(pdf_path).name, source=source)

    try:
        # Convert PDF to images
        t0 = time.time()
        imgs = pdf_to_images(pdf_path)
        t_convert = time.time() - t0

        # OCR each page
        t1 = time.time()
        md_parts = []
        for i, img in enumerate(imgs):
            with state_lock:
                ocr_state["current_page"] = i + 1
            md_parts.append(ocr_page_maas(img))
        t_ocr = time.time() - t1

        # Save markdown
        md_text = "\n\n---\n\n".join(md_parts)
        out_path = os.path.join(config.OUTPUT_DIR, f"{pdf_name}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- OCR by GLM-OCR | {Path(pdf_path).name} -->\n\n{md_text}")

        # Update DB
        db.complete_job(job_id, len(imgs), t_convert, t_ocr, f"{pdf_name}.md")

        # Cleanup temp images
        shutil.rmtree(f"/tmp/pdf_pages/{pdf_name}", ignore_errors=True)

        return out_path

    except Exception as e:
        db.fail_job(job_id, str(e))
        traceback.print_exc()
        raise


def ocr_worker(pdfs):
    """Background worker: process multiple PDFs."""
    global ocr_state
    with state_lock:
        ocr_state.update({
            "running": True, "files_done": 0, "files_total": len(pdfs),
            "results": [], "error": None, "start_time": time.time()
        })

    for idx, pdf in enumerate(pdfs):
        with state_lock:
            ocr_state["current_file"] = Path(pdf).name
            ocr_state["current_page"] = 0
            ocr_state["total_pages"] = 0

        try:
            t0 = time.time()
            imgs = pdf_to_images(pdf)
            t_convert = time.time() - t0
            with state_lock:
                ocr_state["total_pages"] = len(imgs)

            t1 = time.time()
            md_parts = []
            for i, img in enumerate(imgs):
                with state_lock:
                    ocr_state["current_page"] = i + 1
                md_parts.append(ocr_page_maas(img))
            t_ocr = time.time() - t1

            pdf_name = Path(pdf).stem
            md_text = "\n\n---\n\n".join(md_parts)
            out_path = os.path.join(config.OUTPUT_DIR, f"{pdf_name}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- OCR by GLM-OCR | {Path(pdf).name} -->\n\n{md_text}")

            job_id = db.add_job(Path(pdf).name, source="upload")
            db.complete_job(job_id, len(imgs), t_convert, t_ocr, f"{pdf_name}.md")

            with state_lock:
                ocr_state["files_done"] = idx + 1
                ocr_state["results"].append({
                    "file": Path(pdf).name, "pages": len(imgs), "output": f"{pdf_name}.md",
                    "status": "ok", "time_ocr": round(t_ocr, 2),
                    "time_convert": round(t_convert, 2),
                    "avg_per_page": round(t_ocr / max(len(imgs), 1), 2)
                })

            shutil.rmtree(f"/tmp/pdf_pages/{pdf_name}", ignore_errors=True)

        except Exception as e:
            traceback.print_exc()
            with state_lock:
                ocr_state["files_done"] = idx + 1
                ocr_state["results"].append({
                    "file": Path(pdf).name, "pages": 0, "output": "",
                    "status": f"error: {str(e)[:100]}", "time_ocr": 0,
                    "time_convert": 0, "avg_per_page": 0
                })

    with state_lock:
        ocr_state["running"] = False
        ocr_state["current_file"] = ""


# === Flask App ===
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = config.SECRET_KEY
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024


# --- Auth Routes ---
@app.route("/login", methods=["GET"])
def login_page():
    return send_from_directory("static", "login.html")


@app.route("/login", methods=["POST"])
def login_submit():
    data = request.get_json(silent=True)
    pw = data.get("password", "") if data else request.form.get("password", "")
    if pw == config.APP_PASSWORD:
        session["authenticated"] = True
        session.permanent = True
        return jsonify({"ok": True})
    return jsonify({"error": "Mật khẩu sai"}), 401


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --- App Routes ---
@app.route("/")
@login_required
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/upload", methods=["POST"])
@login_required
def upload():
    ups = []
    for f in request.files.getlist("files"):
        if f.filename and f.filename.lower().endswith(".pdf"):
            dest = os.path.join(config.INPUT_DIR, f.filename)
            f.save(dest)
            ups.append({"name": f.filename, "size": os.path.getsize(dest)})
    return jsonify({"uploaded": ups})


@app.route("/api/files")
@login_required
def list_files():
    pdfs = [{"name": f, "size": os.path.getsize(os.path.join(config.INPUT_DIR, f))}
            for f in sorted(os.listdir(config.INPUT_DIR)) if f.lower().endswith(".pdf")]
    mds = [{"name": f, "size": os.path.getsize(os.path.join(config.OUTPUT_DIR, f))}
           for f in sorted(os.listdir(config.OUTPUT_DIR)) if f.lower().endswith(".md")]
    return jsonify({"pdfs": pdfs, "markdowns": mds})


@app.route("/api/ocr", methods=["POST"])
@login_required
def start_ocr():
    if ocr_state["running"]:
        return jsonify({"error": "OCR đang chạy"}), 409
    data = request.get_json(silent=True) or {}
    selected = data.get("files")
    if selected:
        pdfs = [os.path.join(config.INPUT_DIR, f) for f in selected
                if os.path.exists(os.path.join(config.INPUT_DIR, f))]
    else:
        pdfs = sorted(glob.glob(os.path.join(config.INPUT_DIR, "*.pdf")))
    if not pdfs:
        return jsonify({"error": "Không có file PDF"}), 400
    threading.Thread(target=ocr_worker, args=(pdfs,), daemon=True).start()
    return jsonify({"started": len(pdfs)})


@app.route("/api/status")
@login_required
def status():
    with state_lock:
        el = time.time() - ocr_state["start_time"] if ocr_state["start_time"] else 0
        return jsonify({**ocr_state, "elapsed": round(el, 1)})


@app.route("/api/preview/<fn>")
@login_required
def preview(fn):
    p = os.path.join(config.OUTPUT_DIR, fn)
    if not os.path.exists(p):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"content": open(p, "r", encoding="utf-8").read(), "name": fn})


@app.route("/api/download/<fn>")
@login_required
def download(fn):
    return send_from_directory(config.OUTPUT_DIR, fn, as_attachment=True)


@app.route("/api/download_all")
@login_required
def download_all():
    shutil.make_archive("/tmp/ocr_results", "zip", config.OUTPUT_DIR)
    return send_file("/tmp/ocr_results.zip", as_attachment=True, download_name="ocr_results.zip")


@app.route("/api/delete/<fn>", methods=["DELETE"])
@login_required
def delete_file(fn):
    for d in [config.INPUT_DIR, config.OUTPUT_DIR]:
        p = os.path.join(d, fn)
        if os.path.exists(p):
            os.remove(p)
    return jsonify({"deleted": fn})


# --- Dashboard API ---
@app.route("/api/dashboard")
@login_required
def dashboard():
    stats = db.get_stats()
    daily = db.get_daily_stats()
    recent = db.get_recent_jobs(limit=50)
    return jsonify({"stats": stats, "daily": daily, "recent": recent})


# --- Drive API ---
@app.route("/api/drive/status")
@login_required
def drive_status():
    return jsonify(get_drive_status())


@app.route("/api/drive/sync", methods=["POST"])
@login_required
def drive_sync_now():
    """Trigger manual Google Drive sync."""
    from drive_sync import sync_once
    if not config.GOOGLE_DRIVE_ENABLED:
        return jsonify({"error": "Google Drive not enabled"}), 400
    count = sync_once(lambda path, source: ocr_single_file(path, source))
    return jsonify({"synced": count})


# --- Health ---
@app.route("/health")
def health():
    return jsonify({"status": "ok", "ocr_running": ocr_state["running"]})


# === Startup ===
db.init_db()

# Start Drive sync if enabled
start_sync_worker(lambda path, source: ocr_single_file(path, source))

if __name__ == "__main__":
    print(f"🔐 Password: {config.APP_PASSWORD}")
    print(f"🌐 Starting on port {config.PORT}...")
    print(f"📁 Google Drive: {'enabled' if config.GOOGLE_DRIVE_ENABLED else 'disabled'}")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
