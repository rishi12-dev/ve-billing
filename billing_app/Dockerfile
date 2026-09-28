FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p database uploads generated_pdfs backups

CMD exec gunicorn --bind :${PORT} --workers 2 --threads 8 --timeout 120 "app:create_app()"
