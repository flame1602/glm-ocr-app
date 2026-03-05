FROM python:3.12-slim

# Install system deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create data directory
RUN mkdir -p /data/input_pdfs /data/output_markdown

# Environment
ENV PORT=8080
ENV DATA_DIR=/data

EXPOSE 8080

CMD ["python", "app.py"]
