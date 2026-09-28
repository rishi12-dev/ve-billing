from datetime import date, datetime, timedelta
import shutil

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract, func, or_
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from models import db
from models.core import (
    CompanySetting,
    Customer,
    GSTRecord,
    Invoice,
    InvoiceItem,
    InvoiceNumberHistory,
    InvoiceNumberSetting,
    Payment,
    Quotation,
    QuotationItem,
    SupportingQuotation,
    SupportingQuotationItem,
    User,
)
from services.audit import log_action
from services.export_service import export_rows
from services.numbering import generate_invoice_number
from services.pdf_service import generate_document_pdf
from utils.money import amount_in_words, calculate_item, dec, money, whole_rupees

main_bp = Blueprint("main", __name__)

QUOTATION_DEFAULT_TERMS = """Validity: This quotation shall remain valid for 90 days from the date of issue, unless otherwise specified.
Payment: Payment shall be made as per the agreed terms and conditions of the Purchase Order / Work Order.
Scope of Work: Any work or service outside the approved scope shall be undertaken only with prior approval and shall be charged separately, wherever applicable.
Force Majeure: Any delay arising due to circumstances beyond the reasonable control of the supplier, including natural calamities or government restrictions, shall be dealt with as per the applicable terms of the Purchase Order / Work Order."""


@main_bp.app_template_filter("money")
def money_filter(value):
    return money(value or 0)


@main_bp.app_template_filter("datefmt")
def datefmt(value):
    return value.strftime("%d-%m-%Y") if value else ""


@main_bp.context_processor
def inject_globals():
    return {"today": date.today(), "is_admin": current_user.is_authenticated and current_user.role == "admin"}


@main_bp.before_request
def enforce_login():
    if request.endpoint in ["main.manifest", "main.service_worker"]:
        return None
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))


def admin_required():
    if current_user.role != "admin":
        flash("Admin access required.", "warning")
        return False
    return True


def parse_date(value, fallback=None):
    if not value:
        return fallback or date.today()
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_window():
    preset = request.args.get("range", "month")
    today_value = date.today()
    if preset == "today":
        return today_value, today_value, preset
    if preset == "week":
        return today_value - timedelta(days=today_value.weekday()), today_value, preset
    if preset == "quarter":
        month = ((today_value.month - 1) // 3) * 3 + 1
        return date(today_value.year, month, 1), today_value, preset
    if preset == "fy":
        year = today_value.year if today_value.month >= 4 else today_value.year - 1
        return date(year, 4, 1), today_value, preset
    if preset == "custom":
        return parse_date(request.args.get("start"), today_value), parse_date(request.args.get("end"), today_value), preset
    return date(today_value.year, today_value.month, 1), today_value, "month"


def assign_item_values(item, interstate=False):
    result = calculate_item(item.quantity, item.rate, item.discount if hasattr(item, "discount") else 0, item.gst_rate, interstate)
    for key in ("taxable_amount", "cgst", "sgst", "igst", "total"):
        if hasattr(item, key):
            setattr(item, key, result[key])
    if not hasattr(item, "taxable_amount"):
        item.total = result["total"]
    return result


def apply_document_totals(document):
    taxable = dec(0)
    gst = dec(0)
    grand = dec(0)
    for item in document.items:
        result = assign_item_values(item)
        taxable += result["taxable_amount"]
        gst += result["total_gst"]
        grand += result["total"]
    document.taxable_amount = taxable
    document.total_gst = gst
    document.grand_total = grand
    if hasattr(document, "rounded_total"):
        document.rounded_total = whole_rupees(grand)
        document.amount_words = amount_in_words(document.rounded_total)
    if hasattr(document, "total_discount"):
        document.total_discount = sum((dec(item.discount) for item in document.items), dec(0))


def item_from_form(model):
    item = model(
        description=request.form.get("description", "").strip(),
        quantity=dec(request.form.get("quantity", "1")),
        rate=dec(request.form.get("rate", "0")),
        gst_rate=dec(request.form.get("gst_rate", "18")),
    )
    if hasattr(item, "hsn_code"):
        item.hsn_code = request.form.get("hsn_code", "").strip()
    if hasattr(item, "unit"):
        item.unit = request.form.get("unit", "Nos")
    if hasattr(item, "discount"):
        item.discount = dec(request.form.get("discount", "0"))
    return item


def items_from_form(model):
    descriptions = request.form.getlist("description[]") or request.form.getlist("description")
    hsn_codes = request.form.getlist("hsn_code[]")
    quantities = request.form.getlist("quantity[]") or request.form.getlist("quantity")
    units = request.form.getlist("unit[]") or request.form.getlist("unit")
    rates = request.form.getlist("rate[]") or request.form.getlist("rate")
    discounts = request.form.getlist("discount[]") or request.form.getlist("discount")
    gst_rates = request.form.getlist("gst_rate[]") or request.form.getlist("gst_rate")
    items = []
    for index, description in enumerate(descriptions):
        description = description.strip()
        if not description:
            continue
        item = model(
            description=description,
            quantity=dec(_list_value(quantities, index, "1")),
            rate=dec(_list_value(rates, index, "0")),
            gst_rate=dec(_list_value(gst_rates, index, "18")),
        )
        if hasattr(item, "hsn_code"):
            item.hsn_code = _list_value(hsn_codes, index, "").strip()
        if hasattr(item, "unit"):
            item.unit = _list_value(units, index, "Nos").strip() or "Nos"
        if hasattr(item, "discount"):
            item.discount = dec(_list_value(discounts, index, "0"))
        items.append(item)
    if not items:
        raise ValueError("Please add at least one item description.")
    return items


def _list_value(values, index, default):
    return values[index] if index < len(values) and values[index] not in (None, "") else default


def update_item_from_form(item):
    item.description = request.form.get("description", "").strip()
    item.quantity = dec(request.form.get("quantity", "1"))
    item.rate = dec(request.form.get("rate", "0"))
    item.gst_rate = dec(request.form.get("gst_rate", "18"))
    if hasattr(item, "hsn_code"):
        item.hsn_code = request.form.get("hsn_code", "").strip()
    if hasattr(item, "unit"):
        item.unit = request.form.get("unit", "Nos")
    if hasattr(item, "discount"):
        item.discount = dec(request.form.get("discount", "0"))
    return item


def resolve_customer_from_form():
    customer_id = request.form.get("customer_id", "").strip()
    customer_name = request.form.get("customer_name", "").strip()
    if customer_id:
        customer = db.session.get(Customer, int(customer_id))
        if customer:
            return customer.id
    if not customer_name:
        raise ValueError("Please enter customer details.")
    existing = Customer.query.filter(func.lower(Customer.customer_name) == customer_name.lower()).first()
    if existing:
        return existing.id
    customer = Customer(
        customer_name=customer_name,
        company_name=request.form.get("customer_company", "").strip(),
        ship_name=request.form.get("customer_ship", "").strip(),
        address=request.form.get("customer_address", "").strip(),
        gstin=request.form.get("customer_gstin", "").strip(),
        phone=request.form.get("customer_phone", "").strip(),
        email=request.form.get("customer_email", "").strip(),
    )
    db.session.add(customer)
    db.session.flush()
    log_action("Customer Created From Document", "Customer", customer.id)
    return customer.id


def next_quotation_number():
    year = date.today().year
    prefix = f"QTN/{year}/"
    used_numbers = []
    for row in Quotation.query.filter(Quotation.quotation_number.like(f"{prefix}%")).all():
        suffix = row.quotation_number.replace(prefix, "", 1)
        if suffix.isdigit():
            used_numbers.append(int(suffix))
    next_number = max(used_numbers, default=0) + 1
    while Quotation.query.filter_by(quotation_number=f"{prefix}{next_number:03d}").first():
        next_number += 1
    return f"{prefix}{next_number:03d}"


def friendly_integrity_error(exc, document_name):
    text = str(exc.orig).lower() if getattr(exc, "orig", None) else str(exc).lower()
    if "quotation.quotation_number" in text:
        return "Quotation number already exists. Please use the suggested next quotation number."
    if "invoice.invoice_number" in text:
        return "Invoice number already exists. Please generate or enter a different invoice number."
    return f"{document_name} could not be saved because a duplicate value already exists."


@main_bp.route("/dashboard")
@login_required
def dashboard():
    start, end, preset = date_window()
    invoices = Invoice.query.filter(Invoice.invoice_date.between(start, end)).all()
    quotations = Quotation.query.filter(Quotation.date.between(start, end)).all()
    paid_count = sum(1 for inv in invoices if inv.payment_status == "Paid")
    pending_count = sum(1 for inv in invoices if inv.payment_status in ("Pending", "Partially Paid"))
    cards = {
        "total_sales": sum((inv.rounded_total for inv in invoices), 0),
        "taxable_sales": sum((inv.taxable_amount for inv in invoices), dec(0)),
        "total_gst": sum((inv.total_gst for inv in invoices), dec(0)),
        "received": sum((inv.paid_amount for inv in invoices), 0),
        "pending": sum((inv.pending_amount for inv in invoices), 0),
        "paid_count": paid_count,
        "pending_count": pending_count,
        "quotation_count": len(quotations),
        "quotation_value": sum((q.rounded_total for q in quotations), 0),
        "accepted_quotations": sum(1 for q in quotations if q.status == "Accepted"),
        "pending_quotations": sum(1 for q in quotations if q.status in ("Draft", "Sent")),
        "invoice_count": len(invoices),
        "cancelled_count": sum(1 for inv in invoices if inv.payment_status == "Cancelled"),
    }
    monthly_rows = [
        [int(row[0]), int(row[1] or 0), int(row[2] or 0)]
        for row in (
            db.session.query(extract("month", Invoice.invoice_date), func.sum(Invoice.rounded_total), func.sum(Invoice.total_gst))
            .filter(extract("year", Invoice.invoice_date) == date.today().year)
            .group_by(extract("month", Invoice.invoice_date))
            .all()
        )
    ]
    recent_invoices = Invoice.query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(6).all()
    recent_quotations = Quotation.query.order_by(Quotation.date.desc(), Quotation.id.desc()).limit(6).all()
    return render_template(
        "dashboard.html",
        cards=cards,
        recent_invoices=recent_invoices,
        recent_quotations=recent_quotations,
        monthly_rows=monthly_rows,
        preset=preset,
        start=start,
        end=end,
    )


@main_bp.route("/customers", methods=["GET", "POST"])
@login_required
def customers():
    if request.method == "POST":
        customer = Customer(
            customer_name=request.form.get("customer_name", "").strip(),
            company_name=request.form.get("company_name", "").strip(),
            ship_name=request.form.get("ship_name", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            state=request.form.get("state", "").strip(),
            pin=request.form.get("pin", "").strip(),
            gstin=request.form.get("gstin", "").strip(),
            contact_person=request.form.get("contact_person", "").strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
        )
        if not customer.customer_name:
            flash("Please enter customer details.", "danger")
        else:
            db.session.add(customer)
            log_action("Customer Created", "Customer")
            db.session.commit()
            flash("Customer saved.", "success")
            return redirect(url_for("main.customers"))
    q = request.args.get("q", "")
    query = Customer.query
    if q:
        query = query.filter(or_(Customer.customer_name.contains(q), Customer.company_name.contains(q), Customer.ship_name.contains(q), Customer.gstin.contains(q)))
    return render_template("customers.html", customers=query.order_by(Customer.customer_name).all())


@main_bp.route("/quotations")
@login_required
def quotations():
    q = request.args.get("q", "")
    query = Quotation.query.join(Customer)
    if q:
        query = query.filter(or_(Quotation.quotation_number.contains(q), Customer.customer_name.contains(q), Customer.ship_name.contains(q), Quotation.subject.contains(q)))
    return render_template("quotations.html", quotations=query.order_by(Quotation.date.desc()).all())


@main_bp.route("/quotations/new", methods=["GET", "POST"])
@login_required
def new_quotation():
    customers = Customer.query.order_by(Customer.customer_name).all()
    number = next_quotation_number()
    if request.method == "POST":
        try:
            quotation = Quotation(
                quotation_number=request.form.get("quotation_number", "").strip() or next_quotation_number(),
                date=parse_date(request.form.get("date")),
                customer_id=resolve_customer_from_form(),
                subject=request.form.get("subject", "").strip(),
                notes=request.form.get("notes", "").strip(),
                terms=request.form.get("terms", "").strip() or QUOTATION_DEFAULT_TERMS,
                status=request.form.get("status", "Draft"),
            )
            quotation.items = items_from_form(QuotationItem)
            apply_document_totals(quotation)
            db.session.add(quotation)
            log_action("Quotation Created", "Quotation")
            db.session.commit()
            flash("Quotation saved.", "success")
            return redirect(url_for("main.quotations"))
        except IntegrityError as exc:
            db.session.rollback()
            flash(friendly_integrity_error(exc, "Quotation"), "danger")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("document_form.html", kind="Quotation", customers=customers, action=url_for("main.new_quotation"), number=number, document=None, item=None, mode="new", default_terms=QUOTATION_DEFAULT_TERMS)


@main_bp.route("/quotations/<int:quotation_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quotation(quotation_id):
    quotation = db.session.get(Quotation, quotation_id)
    if not quotation:
        flash("Quotation not found.", "danger")
        return redirect(url_for("main.quotations"))
    customers = Customer.query.order_by(Customer.customer_name).all()
    item = quotation.items[0] if quotation.items else None
    if request.method == "POST":
        try:
            quotation.date = parse_date(request.form.get("date"))
            quotation.customer_id = resolve_customer_from_form()
            quotation.subject = request.form.get("subject", "").strip()
            quotation.notes = request.form.get("notes", "").strip()
            quotation.terms = request.form.get("terms", "").strip()
            quotation.status = request.form.get("status", "Draft")
            quotation.items = items_from_form(QuotationItem)
            apply_document_totals(quotation)
            log_action("Quotation Edited", "Quotation", quotation.id)
            db.session.commit()
            flash("Quotation updated.", "success")
            return redirect(url_for("main.quotations"))
        except IntegrityError as exc:
            db.session.rollback()
            flash(friendly_integrity_error(exc, "Quotation"), "danger")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    item = quotation.items[0] if quotation.items else None
    return render_template("document_form.html", kind="Quotation", customers=customers, action=url_for("main.edit_quotation", quotation_id=quotation.id), number=quotation.quotation_number, document=quotation, item=item, mode="edit")


@main_bp.route("/quotations/<int:quotation_id>/convert")
@login_required
def convert_quotation(quotation_id):
    quotation = db.session.get(Quotation, quotation_id)
    if not quotation:
        flash("Quotation not found.", "danger")
        return redirect(url_for("main.quotations"))
    invoice = Invoice(invoice_number=generate_invoice_number(), invoice_date=date.today(), customer_id=quotation.customer_id, quotation_id=quotation.id, subject=quotation.subject)
    for qitem in quotation.items:
        invoice.items.append(InvoiceItem(description=qitem.description, hsn_code=qitem.hsn_code, quantity=qitem.quantity, unit=qitem.unit, rate=qitem.rate, discount=qitem.discount, gst_rate=qitem.gst_rate))
    apply_document_totals(invoice)
    quotation.status = "Converted to Invoice"
    db.session.add(invoice)
    db.session.flush()
    history = InvoiceNumberHistory.query.filter_by(invoice_number=invoice.invoice_number).first()
    if history:
        history.invoice_id = invoice.id
    log_action("Quotation Converted", "Quotation", quotation.id)
    db.session.commit()
    flash(f"Invoice {invoice.invoice_number} generated.", "success")
    return redirect(url_for("main.invoices"))


@main_bp.route("/invoices")
@login_required
def invoices():
    q = request.args.get("q", "")
    query = Invoice.query.join(Customer)
    if q:
        query = query.filter(or_(Invoice.invoice_number.contains(q), Customer.customer_name.contains(q), Customer.ship_name.contains(q), Customer.gstin.contains(q), Invoice.payment_status.contains(q)))
    return render_template("invoices.html", invoices=query.order_by(Invoice.invoice_date.desc()).all())


@main_bp.route("/invoices/new", methods=["GET", "POST"])
@login_required
def new_invoice():
    customers = Customer.query.order_by(Customer.customer_name).all()
    if request.method == "POST":
        try:
            invoice = Invoice(
                invoice_number=request.form.get("invoice_number") or generate_invoice_number(),
                invoice_date=parse_date(request.form.get("date")),
                customer_id=resolve_customer_from_form(),
                subject=request.form.get("subject", "").strip(),
                payment_status=request.form.get("payment_status", "Pending"),
            )
            invoice.items = items_from_form(InvoiceItem)
            apply_document_totals(invoice)
            db.session.add(invoice)
            db.session.flush()
            history = InvoiceNumberHistory.query.filter_by(invoice_number=invoice.invoice_number).first()
            if history:
                history.invoice_id = invoice.id
            else:
                db.session.add(InvoiceNumberHistory(invoice_number=invoice.invoice_number, invoice_id=invoice.id, generated_by=current_user.id))
            log_action("Invoice Created", "Invoice", invoice.id)
            db.session.commit()
            flash("Invoice saved.", "success")
            return redirect(url_for("main.invoices"))
        except IntegrityError as exc:
            db.session.rollback()
            flash(friendly_integrity_error(exc, "Invoice"), "danger")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    number = generate_invoice_number()
    db.session.commit()
    return render_template("document_form.html", kind="Invoice", customers=customers, action=url_for("main.new_invoice"), number=number, document=None, item=None, mode="new")


@main_bp.route("/invoices/<int:invoice_id>/edit", methods=["GET", "POST"])
@login_required
def edit_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for("main.invoices"))
    customers = Customer.query.order_by(Customer.customer_name).all()
    item = invoice.items[0] if invoice.items else None
    if request.method == "POST":
        try:
            invoice.invoice_date = parse_date(request.form.get("date"))
            invoice.customer_id = resolve_customer_from_form()
            invoice.subject = request.form.get("subject", "").strip()
            invoice.payment_status = request.form.get("payment_status", "Pending")
            invoice.items = items_from_form(InvoiceItem)
            apply_document_totals(invoice)
            log_action("Invoice Edited", "Invoice", invoice.id)
            db.session.commit()
            flash("Invoice updated.", "success")
            return redirect(url_for("main.invoices"))
        except IntegrityError as exc:
            db.session.rollback()
            flash(friendly_integrity_error(exc, "Invoice"), "danger")
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    item = invoice.items[0] if invoice.items else None
    return render_template("document_form.html", kind="Invoice", customers=customers, action=url_for("main.edit_invoice", invoice_id=invoice.id), number=invoice.invoice_number, document=invoice, item=item, mode="edit")


@main_bp.route("/invoices/<int:invoice_id>/delete", methods=["POST"])
@login_required
def delete_invoice(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash("Invoice not found.", "danger")
        return redirect(url_for("main.invoices"))
    number = invoice.invoice_number
    for history in InvoiceNumberHistory.query.filter_by(invoice_id=invoice.id).all():
        history.invoice_id = None
    log_action("Invoice Deleted", "Invoice", invoice.id, new_value=number)
    db.session.delete(invoice)
    db.session.commit()
    flash(f"Invoice {number} deleted.", "success")
    return redirect(url_for("main.invoices"))


@main_bp.route("/documents/<kind>/<int:doc_id>/pdf")
@login_required
def document_pdf(kind, doc_id):
    model = Invoice if kind == "invoice" else Quotation
    document = db.session.get(model, doc_id)
    if not document:
        flash("Document not found.", "danger")
        return redirect(url_for("main.dashboard"))
    path = generate_document_pdf(kind.title(), document, current_app.config["GENERATED_PDF_FOLDER"])
    preview = request.args.get("preview") == "1"
    response = send_file(path, as_attachment=not preview, download_name=path.name, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@main_bp.route("/payments", methods=["GET", "POST"])
@login_required
def payments():
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    if request.method == "POST":
        invoice = db.session.get(Invoice, int(request.form.get("invoice_id")))
        amount = int(request.form.get("amount_received", "0"))
        if not invoice:
            flash("Invoice not found.", "danger")
        elif amount <= 0 or amount > invoice.pending_amount:
            flash("Payment amount cannot exceed invoice balance.", "danger")
        else:
            payment = Payment(
                invoice_id=invoice.id,
                amount_received=amount,
                payment_date=parse_date(request.form.get("payment_date")),
                payment_mode=request.form.get("payment_mode"),
                transaction_ref=request.form.get("transaction_ref", "").strip(),
                notes=request.form.get("notes", "").strip(),
            )
            db.session.add(payment)
            remaining = invoice.pending_amount - amount
            invoice.payment_status = "Paid" if remaining == 0 else "Partially Paid"
            log_action("Payment Added", "Payment", invoice.id)
            db.session.commit()
            flash("Payment recorded.", "success")
            return redirect(url_for("main.payments"))
    return render_template("payments.html", invoices=invoices, payments=Payment.query.order_by(Payment.payment_date.desc()).all())


@main_bp.route("/gst", methods=["GET", "POST"])
@login_required
def gst_summary():
    if request.method == "POST":
        record = GSTRecord(
            return_period=request.form.get("return_period", "").strip(),
            gst_liability=dec(request.form.get("gst_liability")),
            gst_paid=dec(request.form.get("gst_paid")),
            payment_date=parse_date(request.form.get("payment_date")) if request.form.get("payment_date") else None,
            notes=request.form.get("notes", "").strip(),
        )
        db.session.add(record)
        log_action("GST Reconciliation Added", "GSTRecord")
        db.session.commit()
        flash("GST reconciliation saved.", "success")
        return redirect(url_for("main.gst_summary"))
    rows = {}
    for rate in ["0.00", "5.00", "12.00", "18.00", "28.00"]:
        items = InvoiceItem.query.filter(InvoiceItem.gst_rate == dec(rate)).all()
        rows[rate] = {
            "taxable": sum((item.taxable_amount for item in items), dec(0)),
            "cgst": sum((item.cgst for item in items), dec(0)),
            "sgst": sum((item.sgst for item in items), dec(0)),
            "igst": sum((item.igst for item in items), dec(0)),
        }
        rows[rate]["total"] = rows[rate]["cgst"] + rows[rate]["sgst"] + rows[rate]["igst"]
    return render_template("gst.html", rows=rows, records=GSTRecord.query.order_by(GSTRecord.created_at.desc()).all())


@main_bp.route("/reports")
@login_required
def reports():
    invoices = Invoice.query.order_by(Invoice.invoice_date.desc()).all()
    customers = Customer.query.order_by(Customer.customer_name).all()
    return render_template("reports.html", invoices=invoices, customers=customers)


@main_bp.route("/export/<dataset>")
@login_required
def export(dataset):
    rows = []
    if dataset == "invoices":
        rows = [{"Invoice": i.invoice_number, "Date": i.invoice_date, "Customer": i.customer.customer_name, "Taxable": i.taxable_amount, "GST": i.total_gst, "Total": i.rounded_total, "Paid": i.paid_amount, "Pending": i.pending_amount, "Status": i.payment_status} for i in Invoice.query.all()]
    elif dataset == "quotations":
        rows = [{"Quotation": q.quotation_number, "Date": q.date, "Customer": q.customer.customer_name, "Subject": q.subject, "Total": q.rounded_total, "Status": q.status} for q in Quotation.query.all()]
    elif dataset == "payments":
        rows = [{"Invoice": p.invoice.invoice_number, "Date": p.payment_date, "Amount": p.amount_received, "Mode": p.payment_mode, "Reference": p.transaction_ref} for p in Payment.query.all()]
    elif dataset == "customers":
        rows = [{"Customer": c.customer_name, "Company": c.company_name, "Ship": c.ship_name, "GSTIN": c.gstin, "Phone": c.phone, "Email": c.email} for c in Customer.query.all()]
    elif dataset == "gst":
        for rate in ["0.00", "5.00", "12.00", "18.00", "28.00"]:
            items = InvoiceItem.query.filter(InvoiceItem.gst_rate == dec(rate)).all()
            cgst = sum((item.cgst for item in items), dec(0))
            sgst = sum((item.sgst for item in items), dec(0))
            igst = sum((item.igst for item in items), dec(0))
            rows.append({
                "GST Rate": rate,
                "Taxable": sum((item.taxable_amount for item in items), dec(0)),
                "CGST": cgst,
                "SGST": sgst,
                "IGST": igst,
                "Total GST": cgst + sgst + igst,
            })
    elif dataset == "sales":
        rows = [{"Date": i.invoice_date, "Invoice": i.invoice_number, "Customer": i.customer.customer_name, "Taxable": i.taxable_amount, "GST": i.total_gst, "Total": i.rounded_total} for i in Invoice.query.all()]
    else:
        flash("Unknown export type.", "danger")
        return redirect(url_for("main.reports"))
    path = export_rows(f"{dataset}-{date.today().isoformat()}.xlsx", rows, current_app.config["BACKUP_FOLDER"])
    return send_file(path, as_attachment=True)


@main_bp.route("/supporting-quotations", methods=["GET", "POST"])
@login_required
def supporting_quotations():
    customers = Customer.query.order_by(Customer.customer_name).all()
    if request.method == "POST":
        try:
            sq = SupportingQuotation(
                vendor_company=request.form.get("vendor_company", "").strip(),
                quotation_number=request.form.get("quotation_number", "").strip(),
                date=parse_date(request.form.get("date")),
                customer_id=resolve_customer_from_form(),
                subject=request.form.get("subject", "").strip(),
            )
            sq.items.append(item_from_form(SupportingQuotationItem))
            apply_document_totals(sq)
            db.session.add(sq)
            log_action("Supporting Quotation Created", "SupportingQuotation")
            db.session.commit()
            flash("Supporting quotation saved.", "success")
            return redirect(url_for("main.supporting_quotations"))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), "danger")
    return render_template("supporting.html", records=SupportingQuotation.query.order_by(SupportingQuotation.date.desc()).all(), customers=customers)


@main_bp.route("/settings/company", methods=["GET", "POST"])
@login_required
def company_settings():
    if not admin_required():
        return redirect(url_for("main.dashboard"))
    company = CompanySetting.query.first() or CompanySetting()
    if request.method == "POST":
        for field in ("company_name", "address", "city", "state", "pin_code", "phone", "email", "gstin", "pan", "bank_name", "account_number", "ifsc", "branch", "terms", "signatory_name", "default_pdf_template"):
            setattr(company, field, request.form.get(field, ""))
        db.session.add(company)
        log_action("Company Settings Updated", "CompanySetting")
        db.session.commit()
        flash("Company settings saved.", "success")
        return redirect(url_for("main.company_settings"))
    return render_template("settings_company.html", company=company)


@main_bp.route("/settings/invoice-number", methods=["GET", "POST"])
@login_required
def invoice_number_settings():
    if not admin_required():
        return redirect(url_for("main.dashboard"))
    setting = InvoiceNumberSetting.query.first()
    if request.method == "POST":
        setting.prefix = request.form.get("prefix", "")
        setting.next_number = int(request.form.get("next_number", "1"))
        setting.padding = int(request.form.get("padding", "3"))
        log_action("Invoice Number Settings Updated", "InvoiceNumberSetting")
        db.session.commit()
        flash("Invoice numbering saved.", "success")
        return redirect(url_for("main.invoice_number_settings"))
    return render_template("settings_number.html", setting=setting, history=InvoiceNumberHistory.query.order_by(InvoiceNumberHistory.created_at.desc()).limit(50).all())


@main_bp.route("/settings/users", methods=["GET", "POST"])
@login_required
def users():
    if not admin_required():
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        user = User(
            name=request.form.get("name", "").strip(),
            username=request.form.get("username", "").strip(),
            email=request.form.get("email", "").strip(),
            role=request.form.get("role", "staff"),
            password_hash=generate_password_hash(request.form.get("password", "changeme")),
            active=True,
        )
        db.session.add(user)
        log_action("User Created", "User")
        db.session.commit()
        flash("User created.", "success")
        return redirect(url_for("main.users"))
    return render_template("users.html", users=User.query.order_by(User.name).all())


@main_bp.route("/backup")
@login_required
def backup():
    if not admin_required():
        return redirect(url_for("main.dashboard"))
    db_path = current_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    backup_path = current_app.config["BACKUP_FOLDER"] / f"billing-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(db_path, backup_path)
    return send_file(backup_path, as_attachment=True)


@main_bp.route("/manifest.json")
def manifest():
    return current_app.send_static_file("manifest.json")


@main_bp.route("/service-worker.js")
def service_worker():
    return current_app.send_static_file("service-worker.js")
