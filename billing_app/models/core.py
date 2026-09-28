from datetime import datetime

from flask_login import UserMixin

from models import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="staff", nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def is_active(self):
        return self.active


class CompanySetting(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(180), default="Your Company")
    logo_path = db.Column(db.String(255))
    address = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(80), default="")
    pin_code = db.Column(db.String(20), default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(160), default="")
    gstin = db.Column(db.String(30), default="")
    pan = db.Column(db.String(20), default="")
    bank_name = db.Column(db.String(120), default="")
    account_number = db.Column(db.String(60), default="")
    ifsc = db.Column(db.String(30), default="")
    branch = db.Column(db.String(120), default="")
    terms = db.Column(db.Text, default="")
    signatory_name = db.Column(db.String(120), default="")
    signature_path = db.Column(db.String(255))
    default_pdf_template = db.Column(db.String(80), default="standard")


class Customer(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(180), nullable=False)
    company_name = db.Column(db.String(180), default="")
    ship_name = db.Column(db.String(180), default="")
    address = db.Column(db.Text, default="")
    city = db.Column(db.String(80), default="")
    state = db.Column(db.String(80), default="")
    pin = db.Column(db.String(20), default="")
    gstin = db.Column(db.String(30), default="")
    contact_person = db.Column(db.String(120), default="")
    phone = db.Column(db.String(40), default="")
    email = db.Column(db.String(160), default="")


class Quotation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_number = db.Column(db.String(80), unique=True, nullable=False)
    date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    subject = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    terms = db.Column(db.Text, default="")
    status = db.Column(db.String(40), default="Draft", nullable=False)
    taxable_amount = db.Column(db.Numeric(12, 2), default=0)
    total_gst = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), default=0)
    rounded_total = db.Column(db.Integer, default=0)
    amount_words = db.Column(db.String(255), default="")
    customer = db.relationship("Customer")
    items = db.relationship("QuotationItem", cascade="all, delete-orphan", backref="quotation")


class QuotationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotation.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    hsn_code = db.Column(db.String(40), default="")
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit = db.Column(db.String(40), default="Nos")
    rate = db.Column(db.Numeric(12, 2), nullable=False)
    discount = db.Column(db.Numeric(12, 2), default=0)
    gst_rate = db.Column(db.Numeric(5, 2), default=18)
    taxable_amount = db.Column(db.Numeric(12, 2), default=0)
    cgst = db.Column(db.Numeric(12, 2), default=0)
    sgst = db.Column(db.Numeric(12, 2), default=0)
    igst = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)


class Invoice(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(80), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    quotation_id = db.Column(db.Integer, db.ForeignKey("quotation.id"))
    subject = db.Column(db.String(255), default="")
    payment_status = db.Column(db.String(40), default="Pending", nullable=False)
    taxable_amount = db.Column(db.Numeric(12, 2), default=0)
    total_discount = db.Column(db.Numeric(12, 2), default=0)
    total_gst = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), default=0)
    rounded_total = db.Column(db.Integer, default=0)
    amount_words = db.Column(db.String(255), default="")
    finalized = db.Column(db.Boolean, default=True, nullable=False)
    customer = db.relationship("Customer")
    quotation = db.relationship("Quotation")
    items = db.relationship("InvoiceItem", cascade="all, delete-orphan", backref="invoice")
    payments = db.relationship("Payment", cascade="all, delete-orphan", backref="invoice")

    @property
    def paid_amount(self):
        return sum((payment.amount_received for payment in self.payments), 0)

    @property
    def pending_amount(self):
        return max(int(self.rounded_total or 0) - int(self.paid_amount or 0), 0)


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    hsn_code = db.Column(db.String(40), default="")
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    unit = db.Column(db.String(40), default="Nos")
    rate = db.Column(db.Numeric(12, 2), nullable=False)
    discount = db.Column(db.Numeric(12, 2), default=0)
    gst_rate = db.Column(db.Numeric(5, 2), default=18)
    taxable_amount = db.Column(db.Numeric(12, 2), default=0)
    cgst = db.Column(db.Numeric(12, 2), default=0)
    sgst = db.Column(db.Numeric(12, 2), default=0)
    igst = db.Column(db.Numeric(12, 2), default=0)
    total = db.Column(db.Numeric(12, 2), default=0)


class Payment(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)
    amount_received = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    payment_mode = db.Column(db.String(40), nullable=False)
    transaction_ref = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")


class GSTRecord(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_period = db.Column(db.String(30), nullable=False)
    gst_liability = db.Column(db.Numeric(12, 2), default=0)
    gst_paid = db.Column(db.Numeric(12, 2), default=0)
    payment_date = db.Column(db.Date)
    notes = db.Column(db.Text, default="")


class InvoiceNumberSetting(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prefix = db.Column(db.String(80), nullable=False)
    next_number = db.Column(db.Integer, default=1, nullable=False)
    padding = db.Column(db.Integer, default=3, nullable=False)


class InvoiceNumberHistory(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(80), unique=True, nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"))
    generated_by = db.Column(db.Integer, db.ForeignKey("user.id"))


class SupportingQuotation(TimestampMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vendor_company = db.Column(db.String(180), nullable=False)
    quotation_number = db.Column(db.String(80), nullable=False)
    date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    subject = db.Column(db.String(255), default="")
    taxable_amount = db.Column(db.Numeric(12, 2), default=0)
    total_gst = db.Column(db.Numeric(12, 2), default=0)
    grand_total = db.Column(db.Numeric(12, 2), default=0)
    customer = db.relationship("Customer")
    items = db.relationship("SupportingQuotationItem", cascade="all, delete-orphan", backref="supporting_quotation")


class SupportingQuotationItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    supporting_quotation_id = db.Column(db.Integer, db.ForeignKey("supporting_quotation.id"), nullable=False)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Numeric(12, 2), nullable=False)
    rate = db.Column(db.Numeric(12, 2), nullable=False)
    gst_rate = db.Column(db.Numeric(5, 2), default=18)
    total = db.Column(db.Numeric(12, 2), default=0)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(120), nullable=False)
    record_type = db.Column(db.String(80), nullable=False)
    record_id = db.Column(db.Integer)
    old_value = db.Column(db.Text, default="")
    new_value = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user = db.relationship("User")
