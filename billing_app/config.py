import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-before-production")
    _db_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'database' / 'billing.db'}")
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    GENERATED_PDF_FOLDER = BASE_DIR / "generated_pdfs"
    BACKUP_FOLDER = BASE_DIR / "backups"
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
