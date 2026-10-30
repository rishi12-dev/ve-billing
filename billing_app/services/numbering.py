from flask_login import current_user

from models import db
from models.core import Invoice, InvoiceNumberHistory, InvoiceNumberSetting


def generate_invoice_number():
    setting = InvoiceNumberSetting.query.first()
    if not setting:
        setting = InvoiceNumberSetting(prefix="INV/", next_number=1, padding=3)
        db.session.add(setting)
        db.session.flush()
    while True:
        number = f"{setting.prefix}{str(setting.next_number).zfill(setting.padding)}"
        setting.next_number += 1
        duplicate = Invoice.query.filter_by(invoice_number=number).first() or InvoiceNumberHistory.query.filter_by(invoice_number=number).first()
        if not duplicate:
            db.session.add(
                InvoiceNumberHistory(
                    invoice_number=number,
                    generated_by=current_user.id if current_user.is_authenticated else None,
                )
            )
            return number


def peek_next_invoice_number():
    """Return the next available number without reserving it."""
    setting = InvoiceNumberSetting.query.first()
    if not setting:
        prefix, next_number, padding = "INV/", 1, 3
    else:
        prefix, next_number, padding = setting.prefix, setting.next_number, setting.padding

    while True:
        number = f"{prefix}{str(next_number).zfill(padding)}"
        used = (
            Invoice.query.filter_by(invoice_number=number).first()
            or InvoiceNumberHistory.query.filter_by(invoice_number=number).first()
        )
        if not used:
            return number
        next_number += 1
