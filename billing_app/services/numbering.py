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
