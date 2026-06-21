FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code + shared taxonomy/source files (config reads ../shared).
COPY app ./app
COPY ../shared /shared
ENV SATYA_SHARED_DIR=/shared

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
