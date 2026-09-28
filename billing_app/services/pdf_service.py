from decimal import Decimal
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from models.core import CompanySetting
from utils.money import amount_in_words, whole_rupees

NAVY = colors.HexColor("#142446")
RED = colors.HexColor("#9c2f24")
LIGHT = colors.HexColor("#edf1f6")
GRID = colors.HexColor("#606875")
HEADER_IMAGE = Path(__file__).resolve().parents[1] / "static" / "images" / "vishwakarma_header.png"
QUOTATION_DEFAULT_TERMS = """Validity: This quotation shall remain valid for 90 days from the date of issue, unless otherwise specified.
Payment: Payment shall be made as per the agreed terms and conditions of the Purchase Order / Work Order.
Scope of Work: Any work or service outside the approved scope shall be undertaken only with prior approval and shall be charged separately, wherever applicable.
Force Majeure: Any delay arising due to circumstances beyond the reasonable control of the supplier, including natural calamities or government restrictions, shall be dealt with as per the applicable terms of the Purchase Order / Work Order."""


def _company():
    company = CompanySetting.query.first() or CompanySetting()
    return {
        "name": "VISHWAKARMA ENTERPRISES",
        "tagline": "ALL KINDS OF FURNITURE WORKS, SUPPLIER & REPAIRING WORK",
        "address": "No.12/106, West Madha Church Street, Royapuram",
        "city_line": "Chennai - 600 013",
        "gstin": "33QQIPS2785G1Z3",
        "phone": "95141 27830, 72006 03698, 044-4666 5884",
        "email": "viswakarmaenterprises543@gmail.com",
        "bank_name": company.bank_name or "State Bank of India",
        "account_number": company.account_number or "12345678901",
        "ifsc": company.ifsc or "SBIN0001234",
        "branch": company.branch or "Royapuram, Chennai",
        "terms": company.terms or "Goods once sold will not be taken back.\nPrices are in Indian Rupees and are firm.\nGST as applicable has been charged.\nDelivery: Within 7-10 days from the date of PO.\nPayment: As per your terms.\nSubject to Chennai jurisdiction only.",
        "signatory": company.signatory_name or "Authorized Signatory",
    }


def generate_document_pdf(kind, document, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    number = getattr(document, "invoice_number", None) or getattr(document, "quotation_number", "document")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    path = output_dir / f"{kind.lower()}-{number.replace('/', '-')}-{stamp}.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )
    styles = _styles()
    title = "TAX INVOICE" if kind == "Invoice" else "QUOTATION"
    story = [
        _header(styles),
        Spacer(1, 5),
        _title_block(title, styles),
        Spacer(1, 6),
        _party_block(kind, document, styles),
        Spacer(1, 7),
        _items_table(document, styles),
        _amount_words_block(document, styles),
        *_optional_terms(document, styles),
        Spacer(1, 12),
        _signature_block(styles),
        Spacer(1, 4),
        _footer_note(styles),
    ]
    doc.build(story)
    return path


def _styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle("Brand", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=25, leading=27, textColor=RED, alignment=TA_CENTER))
    base.add(ParagraphStyle("Tagline", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=NAVY, alignment=TA_CENTER))
    base.add(ParagraphStyle("SmallCenter", parent=base["Normal"], fontSize=8.5, leading=10.5, textColor=NAVY, alignment=TA_CENTER))
    base.add(ParagraphStyle("TitleBand", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=NAVY, alignment=TA_CENTER))
    base.add(ParagraphStyle("Cell", parent=base["Normal"], fontSize=8.6, leading=10.6))
    base.add(ParagraphStyle("CellBold", parent=base["Cell"], fontName="Helvetica-Bold"))
    base.add(ParagraphStyle("Terms", parent=base["Normal"], fontSize=8.2, leading=10.4))
    base.add(ParagraphStyle("Signature", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=10.5, leading=12, textColor=NAVY))
    return base


def _header(styles):
    if HEADER_IMAGE.exists():
        image = RLImage(str(HEADER_IMAGE), width=190 * mm, height=34.4 * mm)
        image.hAlign = "CENTER"
        return image

    company = _company()
    left_mark = Paragraph(
        "<b>V</b>",
        ParagraphStyle("MarkLeft", fontName="Helvetica-Bold", fontSize=30, textColor=colors.HexColor("#b05a47"), alignment=TA_CENTER),
    )
    right_mark = Paragraph(
        "<b>ANCHOR</b>",
        ParagraphStyle("MarkRight", fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#b05a47"), alignment=TA_CENTER),
    )
    center = [
        Paragraph(f"GSTIN: {company['gstin']}", ParagraphStyle("GST", fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY, alignment=TA_RIGHT)),
        Paragraph(company["name"], styles["Brand"]),
        Paragraph(company["tagline"], styles["Tagline"]),
        Paragraph(f"{company['address']}, {company['city_line']}", styles["SmallCenter"]),
        Paragraph(f"Email: {company['email']}  |  Mobile: {company['phone']}", styles["SmallCenter"]),
    ]
    table = Table([[left_mark, center, right_mark]], colWidths=[31 * mm, 124 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#d8c7a6")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7e8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#ead9bd")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#ead9bd")),
            ]
        )
    )
    return table


def _title_block(title, styles):
    data = [[Paragraph(title, styles["TitleBand"])]]
    if title == "TAX INVOICE":
        data.append([Paragraph("(ORIGINAL FOR RECIPIENT)", styles["SmallCenter"])])
    table = Table(data, colWidths=[88 * mm], hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), LIGHT),
                ("BOX", (0, 0), (0, 0), 0.4, colors.HexColor("#c8ced8")),
                ("PADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _party_block(kind, document, styles):
    customer = document.customer
    date_value = getattr(document, "invoice_date", None) or getattr(document, "date", "")
    doc_number = getattr(document, "invoice_number", None) or getattr(document, "quotation_number", "")
    left = [
        Paragraph("<b>Bill To :</b>", styles["CellBold"]),
        Paragraph(f"<b>{customer.customer_name}</b>", styles["Cell"]),
        Paragraph(f"<b>{customer.company_name or customer.ship_name or ''}</b>", styles["Cell"]),
        Paragraph(_address(customer), styles["Cell"]),
    ]
    if customer.gstin:
        left.append(Paragraph(f"GSTIN: {customer.gstin}", styles["Cell"]))
    label = "Invoice No." if kind == "Invoice" else "Quotation No."
    right_rows = [
        [label, ":", doc_number],
        ["Date", ":", date_value.strftime("%d-%m-%Y") if hasattr(date_value, "strftime") else date_value],
        ["Place of Supply", ":", customer.state or "Tamil Nadu"],
        ["Reverse Charge", ":", "No"],
        ["Payment Terms", ":", "As per your terms"],
        ["Dispatch Mode", ":", "By Hand / Transport"],
        ["Vehicle No.", ":", "-"],
    ]
    right = Table(right_rows, colWidths=[31 * mm, 4 * mm, 45 * mm])
    right.setStyle(TableStyle([("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("LEADING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    table = Table([[left, right]], colWidths=[109 * mm, 81 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, GRID),
                ("LINEBEFORE", (1, 0), (1, 0), 0.8, GRID),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _items_table(document, styles):
    rows = [[
        Paragraph("<b>S.No.</b>", styles["CellBold"]),
        Paragraph("<b>Description of Goods</b>", styles["CellBold"]),
        Paragraph("<b>HSN Code</b>", styles["CellBold"]),
        Paragraph("<b>Qty.</b>", styles["CellBold"]),
        Paragraph("<b>Unit</b>", styles["CellBold"]),
        Paragraph("<b>Rate</b>", styles["CellBold"]),
        Paragraph("<b>Amount</b>", styles["CellBold"]),
    ]]
    subtotal = Decimal("0.00")
    for index, item in enumerate(document.items, start=1):
        amount = Decimal(str(item.quantity or 0)) * Decimal(str(item.rate or 0))
        subtotal += amount
        rows.append([
            str(index),
            Paragraph(item.description, styles["Cell"]),
            getattr(item, "hsn_code", "") or "-",
            _number(item.quantity),
            getattr(item, "unit", "Nos") or "Nos",
            pdf_money(item.rate),
            pdf_money(amount),
        ])
    while len(rows) < 9:
        rows.append(["", "", "", "", "", "", ""])
    rows.extend(_tax_rows(document, subtotal))
    table = Table(rows, colWidths=[13 * mm, 64 * mm, 24 * mm, 18 * mm, 19 * mm, 27 * mm, 25 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.55, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "CENTER"),
                ("ALIGN", (5, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("SPAN", (0, -4), (4, -4)),
                ("SPAN", (0, -3), (4, -3)),
                ("SPAN", (0, -2), (4, -2)),
                ("SPAN", (0, -1), (4, -1)),
                ("BACKGROUND", (5, -1), (-1, -1), LIGHT),
                ("FONTNAME", (5, -4), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (5, -1), (-1, -1), 10),
            ]
        )
    )
    return table


def _tax_rows(document, subtotal):
    cgst = sum((Decimal(str(item.cgst or 0)) for item in document.items), Decimal("0.00"))
    sgst = sum((Decimal(str(item.sgst or 0)) for item in document.items), Decimal("0.00"))
    igst = sum((Decimal(str(item.igst or 0)) for item in document.items), Decimal("0.00"))
    rates = sorted({Decimal(str(item.gst_rate or 0)) for item in document.items})
    rate_label = _rate_label(rates)
    grand = getattr(document, "rounded_total", None) or whole_rupees(document.grand_total)
    if igst:
        return [
            ["", "", "", "", "", "Sub Total", pdf_money(subtotal)],
            ["", "", "", "", "", f"IGST {rate_label}", pdf_tax_money(igst)],
            ["", "", "", "", "", "Round Off", pdf_tax_money(Decimal(grand) - Decimal(str(document.grand_total)))],
            ["", "", "", "", "", "Grand Total", pdf_money(grand)],
        ]
    return [
        ["", "", "", "", "", "Sub Total", pdf_money(subtotal)],
        ["", "", "", "", "", f"CGST {rate_label}", pdf_tax_money(cgst)],
        ["", "", "", "", "", f"SGST {rate_label}", pdf_tax_money(sgst)],
        ["", "", "", "", "", "Grand Total", pdf_money(grand)],
    ]


def _amount_words_block(document, styles):
    total = getattr(document, "rounded_total", None) or whole_rupees(document.grand_total)
    words = getattr(document, "amount_words", "") or amount_in_words(total)
    table = Table(
        [[Paragraph("<b>Amount in Words :</b>", styles["CellBold"]), Paragraph(words, styles["CellBold"])]],
        colWidths=[36 * mm, 154 * mm],
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.55, GRID), ("PADDING", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return table


def _terms_block(document, styles):
    company = _company()
    is_quotation = hasattr(document, "quotation_number")
    terms_source = QUOTATION_DEFAULT_TERMS if is_quotation else (getattr(document, "terms", "") or company["terms"])
    terms = [line.strip() for line in terms_source.splitlines() if line.strip()]
    terms_rows = [[Paragraph("<b>Terms & Conditions :</b>", styles["CellBold"])]]
    for index, term in enumerate(terms, start=1):
        terms_rows.append([Paragraph(f"{index}. &nbsp; {term}", styles["Terms"])])
    terms_table = Table(terms_rows, colWidths=[190 * mm])
    terms_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.55, GRID),
                ("BACKGROUND", (0, 0), (0, 0), LIGHT),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("LEADING", (0, 0), (-1, -1), 10.5),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return terms_table


def _optional_terms(document, styles):
    if not hasattr(document, "quotation_number"):
        return []
    return [Spacer(1, 7), _terms_block(document, styles)]


def _signature_block(styles):
    company = _company()
    service = Paragraph("<i>Committed to Service</i>", ParagraphStyle("Service", fontName="Helvetica-Oblique", fontSize=10.5, textColor=NAVY, alignment=TA_RIGHT))
    left = [
        Paragraph(f"<b>For {company['name']}</b>", styles["Signature"]),
        Spacer(1, 42),
        Paragraph(company["signatory"], styles["CellBold"]),
        Paragraph("Authorized Signatory", styles["Cell"]),
    ]
    table = Table([[left, service]], colWidths=[95 * mm, 95 * mm])
    table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("PADDING", (0, 0), (-1, -1), 6), ("MINROWHEIGHT", (0, 0), (-1, -1), 34 * mm)]))
    return table


def _footer_note(styles):
    line = Table(
        [["", Paragraph("<i>Thank you for your business!</i>", styles["SmallCenter"]), ""]],
        colWidths=[70 * mm, 50 * mm, 70 * mm],
    )
    line.setStyle(TableStyle([("LINEABOVE", (0, 0), (0, 0), 0.8, NAVY), ("LINEABOVE", (2, 0), (2, 0), 0.8, NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return line


def _address(customer):
    parts = [customer.ship_name, customer.address, customer.city, customer.pin, customer.state]
    return "<br/>".join(part for part in parts if part)


def _number(value):
    if value is None:
        return ""
    value = Decimal(str(value))
    return str(int(value)) if value == value.to_integral() else str(value)


def _rate_label(rates):
    if len(rates) == 1:
        half = rates[0] / 2
        if half == half.to_integral():
            return f"@ {int(half)}%"
        return f"@ {half}%"
    return ""


def pdf_money(value):
    return f"Rs. {whole_rupees(value):,}"


def pdf_tax_money(value):
    value = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    if value == value.to_integral():
        return f"Rs. {int(value):,}"
    return f"Rs. {value:,.2f}"
