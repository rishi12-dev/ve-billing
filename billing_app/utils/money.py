from decimal import Decimal, ROUND_HALF_UP


GST_RATES = [Decimal("0"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28")]


def dec(value, default="0"):
    if value in (None, ""):
        value = default
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def whole_rupees(value):
    return int(dec(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_item(quantity, rate, discount, gst_rate, interstate=False):
    quantity = dec(quantity)
    rate = dec(rate)
    discount = dec(discount)
    gst_rate = dec(gst_rate)
    if quantity < 0 or rate < 0 or discount < 0:
        raise ValueError("Rate, quantity and discount cannot be negative.")
    if gst_rate not in GST_RATES:
        raise ValueError("GST percentage is invalid.")
    gross = quantity * rate
    taxable = max(gross - discount, Decimal("0.00"))
    gst = (taxable * gst_rate / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if interstate:
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        igst = gst
    else:
        cgst = (gst / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sgst = gst - cgst
        igst = Decimal("0.00")
    return {
        "taxable_amount": taxable.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_gst": gst,
        "total": (taxable + gst).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }


def amount_in_words(number):
    number = int(number)
    if number == 0:
        return "Zero Rupees Only"
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def words_below_1000(n):
        out = []
        if n >= 100:
            out.append(ones[n // 100] + " Hundred")
            n %= 100
        if 10 <= n <= 19:
            out.append(teens[n - 10])
        else:
            if n >= 20:
                out.append(tens[n // 10])
                n %= 10
            if n:
                out.append(ones[n])
        return " ".join(out)

    parts = []
    for divisor, label in ((10000000, "Crore"), (100000, "Lakh"), (1000, "Thousand")):
        value = number // divisor
        if value:
            parts.append(words_below_1000(value) + " " + label)
            number %= divisor
    if number:
        parts.append(words_below_1000(number))
    return " ".join(parts) + " Rupees Only"


def money(value):
    return f"₹{whole_rupees(value):,}"
