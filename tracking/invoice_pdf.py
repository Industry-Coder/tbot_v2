import os
from decimal import Decimal
from datetime import timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


RATE_PER_CBM = Decimal("235.00")
MIN_CBM = Decimal("0.005")
MIN_CHARGE = Decimal("2.00")


def money(x: Decimal) -> str:
    return f"${x.quantize(Decimal('0.01'))}"


def calc_line_amount(total_cbm: Decimal) -> Decimal:
    if total_cbm < MIN_CBM:
        total_cbm = MIN_CBM

    amount = (total_cbm * RATE_PER_CBM).quantize(Decimal("0.01"))

    if amount < MIN_CHARGE:
        amount = MIN_CHARGE

    return amount


def generate_invoice(invoice, start_date, packages, transit_days=50):

    from io import BytesIO
    buffer = BytesIO()

    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    table_left = 1 * inch
    table_right = width - 1 * inch
    row_height = 0.35 * inch
    bottom_margin = 1.2 * inch

    col_positions = [
        table_left,
        table_left + 2.1 * inch,
        table_left + 2.8 * inch,
        table_left + 3.7 * inch,
        table_left + 4.7 * inch,
        table_right
    ]

    total_cbm = Decimal("0")
    total_amount = Decimal("0")

    # ===============================
    # WATERMARK
    # ===============================
    def draw_watermark():
        c.saveState()
        c.setFont("Helvetica-Bold", 60)
        c.setFillColorRGB(0.92, 0.92, 0.92)
        c.translate(width / 2, height / 2)
        c.rotate(45)
        c.drawCentredString(0, 0, "PAYLESS LOGISTICS")
        c.restoreState()

    # ===============================
    # PAGE HEADER
    # ===============================
    def draw_page_header():
        y_header = height - 1.2 * inch

        c.setFont("Helvetica-Bold", 16)
        c.setFillColorRGB(0, 0, 0)
        c.drawString(1 * inch, y_header, "PAYLESS LOGISTICS")

        logo_path = os.path.join(
            os.path.dirname(__file__),
            "assets",
            "paylesslogo.png"
        )

        if os.path.exists(logo_path):
            logo_width = 2.2 * inch
            logo_height = 1.4 * inch

            c.drawImage(
                ImageReader(logo_path),
                width - 2.7 * inch,
                y_header - (logo_height / 2) + 0.2 * inch,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )

        return y_header - 0.8 * inch

    # ===============================
    # TABLE HEADER
    # ===============================
    def draw_table_header(current_y):

        c.setFillColorRGB(0.92, 0.92, 0.92)
        c.rect(
            table_left,
            current_y - row_height,
            table_right - table_left,
            row_height,
            fill=1,
            stroke=0
        )

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 12)

        headers = [
            "Tracking Number",
            "Qty",
            "CBM",
            "CBM x $235",
            "Amount ($)"
        ]

        for i, header in enumerate(headers):
            c.drawString(col_positions[i] + 5,
                         current_y - 0.22 * inch, header)

        c.line(table_left, current_y - row_height,
               table_right, current_y - row_height)

        return current_y - row_height

    # ===============================
    # FIRST PAGE
    # ===============================
    draw_watermark()
    y = draw_page_header()

    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        table_left,
        y,
        f"Customer: {invoice.customer_name} - {invoice.customer_phone}"
    )
    y -= 0.3 * inch

    c.drawString(
        table_left,
        y,
        f"Date Received (China Warehouse): {start_date.strftime('%B %d, %Y')}"
    )
    y -= 0.5 * inch

    y = draw_table_header(y)
    table_top = y + row_height
    c.setFont("Helvetica", 10)

    # ===============================
    # TABLE ROWS
    # ===============================
    for p in packages:

        if y < bottom_margin:
            # Draw border before breaking page
            table_bottom = y
            c.rect(
                table_left,
                table_bottom,
                table_right - table_left,
                table_top - table_bottom
            )
            for x in col_positions[1:-1]:
                c.line(x, table_bottom, x, table_top)

            c.showPage()
            draw_watermark()
            y = draw_page_header()
            y = draw_table_header(y)
            table_top = y + row_height
            c.setFont("Helvetica", 12)

        tracking = p["tracking_number"]
        quantity = p["quantity"]
        cbm = p["cbm"]

        amount = calc_line_amount(cbm)
        cbm_value = (cbm * RATE_PER_CBM).quantize(Decimal("0.01"))

        total_cbm += cbm
        total_amount += amount

        c.drawString(col_positions[0] + 5,
                     y - 0.22 * inch, str(tracking))
        c.drawString(col_positions[1] + 5,
                     y - 0.22 * inch, str(quantity))
        c.drawString(col_positions[2] + 5,
                     y - 0.22 * inch, str(cbm))

        c.drawRightString(col_positions[4] - 5,
                          y - 0.22 * inch, money(cbm_value))
        c.drawRightString(col_positions[5] - 5,
                          y - 0.22 * inch, money(amount))

        c.line(table_left, y - row_height,
               table_right, y - row_height)

        y -= row_height

    # Draw final table border
    table_bottom = y
    c.rect(
        table_left,
        table_bottom,
        table_right - table_left,
        table_top - table_bottom
    )

    for x in col_positions[1:-1]:
        c.line(x, table_bottom, x, table_top)

    # ===============================
    # TOTALS
    # ===============================
    y -= 0.4 * inch

    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(1, 0, 0)

    c.drawString(
        table_left,
        y,
        f"Total CBM {total_cbm.quantize(Decimal('0.001'))}"
    )

    c.drawRightString(
        table_right,
        y,
        f"Total {money(total_amount)}"
    )

    c.setFillColorRGB(0, 0, 0)
    y -= 0.6 * inch

    # ETA
    eta_date = start_date + timedelta(days=int(transit_days))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        table_left,
        y,
        f"Estimated Arrival Date: {eta_date.strftime('%d %B, %Y')}"
    )

    y -= 0.5 * inch

    # NOTE
    c.setFillColorRGB(1, 0, 0)
    c.drawString(
        table_left,
        y,
        "Note: Minimum CBM is 0.005 | Minimum Charge is $2"
    )

    c.setFillColorRGB(0, 0, 0)
    y -= 0.5 * inch

    # FINAL PARAGRAPH
    c.setFont("Helvetica-Bold", 12)
    c.drawString(
        table_left,
        y,
        "Please note, shipping fee will only be paid when your goods arrives in our"
    )
    y -= 0.25 * inch
    c.drawString(
        table_left,
        y,
        "Ghana warehouse and scheduled for delivery or pick up. CEDIS ONLY."
    )

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer
