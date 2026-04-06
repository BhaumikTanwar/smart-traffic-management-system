FROM python:3.12-slim

WORKDIR /app

# System deps for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY dataset.csv ./
COPY yolov8n.pt ./

WORKDIR /app/backend

EXPOSE 7860

CMD ["python", "-m", "gunicorn", \
     "--worker-class", "eventlet", \
     "-w", "1", \
     "--bind", "0.0.0.0:7860", \
     "app:app"]