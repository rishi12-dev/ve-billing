from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash

from config import Config
from models import db
from sqlalchemy import inspect, text

from models.core import CompanySetting, InvoiceNumberSetting, User
from routes.auth import auth_bp
from routes.main import main_bp

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    for path in (
        app.config["UPLOAD_FOLDER"],
        app.config["GENERATED_PDF_FOLDER"],
        app.config["BACKUP_FOLDER"],
    ):
        path.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    @app.route("/")
    def root():
        if current_user.is_authenticated:
            return redirect(url_for("main.dashboard"))
        return redirect(url_for("auth.login"))

    with app.app_context():
        db.create_all()
        ensure_schema_compatibility()
        seed_defaults()

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def seed_defaults():
    if not User.query.filter_by(role="admin").first():
        db.session.add(
            User(
                name="Administrator",
                email="admin@example.com",
                username="admin",
                password_hash=generate_password_hash("admin123"),
                role="admin",
                active=True,
            )
        )
    if not InvoiceNumberSetting.query.first():
        db.session.add(InvoiceNumberSetting(prefix="VE/INV/2026/", next_number=1, padding=3))
    if not CompanySetting.query.first():
        db.session.add(
            CompanySetting(
                company_name="VISHWAKARMA ENTERPRISES",
                address="No.12/106, West Madha Church Street, Royapuram",
                city="Chennai",
                state="Tamil Nadu",
                pin_code="600013",
                phone="95141 27830, 72006 03698, 044-4666 5884",
                email="viswakarmaenterprises543@gmail.com",
                gstin="33QQIPS2785G1Z3",
                bank_name="State Bank of India",
                account_number="12345678901",
                ifsc="SBIN0001234",
                branch="Royapuram, Chennai",
                terms="Goods once sold will not be taken back.\nPrices are in Indian Rupees and are firm.\nGST as applicable has been charged.\nDelivery: Within 7-10 days from the date of PO.\nPayment: As per your terms.\nSubject to Chennai jurisdiction only.",
                signatory_name="Authorized Signatory",
            )
        )
    db.session.commit()


def ensure_schema_compatibility():
    inspector = inspect(db.engine)
    for table_name in ("quotation_item", "invoice_item"):
        if table_name in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "hsn_code" not in columns:
                db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN hsn_code VARCHAR(40) DEFAULT ''"))
    if {"quotation", "quotation_item"}.issubset(set(inspector.get_table_names())):
        db.session.execute(text("DELETE FROM quotation_item WHERE quotation_id NOT IN (SELECT id FROM quotation)"))
    if {"invoice", "invoice_item"}.issubset(set(inspector.get_table_names())):
        db.session.execute(text("DELETE FROM invoice_item WHERE invoice_id NOT IN (SELECT id FROM invoice)"))
    db.session.commit()


if __name__ == "__main__":
    create_app().run(debug=True, host="0.0.0.0", port=5000)
