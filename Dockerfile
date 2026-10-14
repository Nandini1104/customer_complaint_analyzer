FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=5000
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Train the sentiment model at build time so the first start is fast
RUN python -m analysis.sentiment_analyzer --train

EXPOSE 5000
# Data lives in /app/database; mount a volume there to keep it between container re-creations
CMD ["python", "app.py"]
