FROM python:3.11-slim

# System deps:
#  - libreoffice + writer: docx -> pdf conversion via soffice --headless
#  - fonts-liberation / dejavu: sane default fonts for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        fonts-liberation \
        fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first so they cache when only app code changes
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend

# Render injects $PORT; default for local docker run
ENV PORT=10000
EXPOSE 10000

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]
