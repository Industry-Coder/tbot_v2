import os
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from dotenv import load_dotenv

from django.core.management.base import BaseCommand
from asgiref.sync import sync_to_async

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

from tracking.models import Package, Invoice, InvoiceItem
from tracking.invoice_pdf import generate_invoice

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_STATE = {}


# ===============================
# MENU KEYBOARD
# ===============================

def main_menu_keyboard():
    keyboard = [
        ["📦 Track"],
        ["🧾 Generate Invoice"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


# ===============================
# SHOW MENU
# ===============================

async def show_menu(update: Update):
    USER_STATE.pop(update.effective_chat.id, None)

    await update.message.reply_text(
        "Welcome to Payless Logistics 📦\n\n"
        "Please choose an option:",
        reply_markup=main_menu_keyboard()
    )


# ===============================
# MAIN HANDLER
# ===============================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # ==========================
    # TRACK BUTTON
    # ==========================
    if text == "📦 Track":
        USER_STATE[chat_id] = "TRACK"
        await update.message.reply_text("Please send the tracking number.")
        return

    # ==========================
    # GENERATE INVOICE BUTTON
    # ==========================
    if text == "🧾 Generate Invoice":
        USER_STATE[chat_id] = "INVOICE"
        await update.message.reply_text(
            "Send customer phone number and invoice date.\n\n"
            "Example:\n0531500655 2026-02-20"
        )
        return

    # ==========================
    # TRACK MODE
    # ==========================
    if USER_STATE.get(chat_id) == "TRACK":

        package = await sync_to_async(
            Package.objects.filter(
                tracking_number__iexact=text
            ).first
        )()

        if not package:
            await update.message.reply_text("Tracking number not found ❌")
            return

        await update.message.reply_text(
            f"📦 Tracking: {package.tracking_number}\n"
            f"Qty: {package.quantity}\n"
            f"CBM per unit: {package.cbm}\n"
            f"Total CBM: {package.total_cbm()}\n"
            f"Final Charge: ${package.final_amount()}\n"
            f"Status: {package.current_status}\n"
            f"Location: {package.current_location or 'N/A'}"
        )

        USER_STATE.pop(chat_id, None)
        return

    # ==========================
    # INVOICE MODE
    # ==========================
    if USER_STATE.get(chat_id) == "INVOICE":

        try:
            phone, invoice_date_str = text.split()
            invoice_date = datetime.strptime(
                invoice_date_str, "%Y-%m-%d"
            ).date()
        except ValueError:
            await update.message.reply_text(
                "Invalid format ❌\n\nUse:\n0531500655 2026-02-20"
            )
            return

        start_date = invoice_date
        end_date = invoice_date + timedelta(days=5)

        packages = await sync_to_async(list)(
            Package.objects.filter(
                customer_phone=phone,
                date_received__range=(start_date, end_date)
            )
        )

        if not packages:
            await update.message.reply_text(
                "No packages found for this phone number within 5 days ❌"
            )
            return

        total_cbm = sum(
            [pkg.total_cbm() for pkg in packages],
            Decimal("0.000")
        )

        total_amount = sum(
            [pkg.final_amount() for pkg in packages],
            Decimal("0.00")
        )

        customer_name = packages[0].receiver_name or "Customer"

        invoice = await sync_to_async(Invoice.objects.create)(
            invoice_number=Invoice.generate_invoice_number(),
            customer_phone=phone,
            customer_name=customer_name,
            start_date=start_date,
            end_date=end_date,
            total_cbm=total_cbm,
            total_amount=total_amount,
        )

        for pkg in packages:
            await sync_to_async(InvoiceItem.objects.create)(
                invoice=invoice,
                tracking_number=pkg.tracking_number,
                quantity=pkg.quantity,
                cbm=pkg.total_cbm(),
                amount=pkg.final_amount(),
            )

        package_dicts = [
            {
                "tracking_number": pkg.tracking_number,
                "quantity": pkg.quantity,
                "cbm": pkg.total_cbm(),
                "amount": pkg.final_amount(),
            }
            for pkg in packages
        ]

        # ✅ MEMORY-BASED PDF (NO TEMP FILE)
        pdf_bytes = generate_invoice(
            invoice,
            start_date,
            package_dicts
        )

        await update.message.reply_document(
            document=pdf_bytes,
            filename=f"{invoice.invoice_number}.pdf"
        )

        USER_STATE.pop(chat_id, None)
        return

    # ==========================
    # DEFAULT
    # ==========================
    await show_menu(update)


# ===============================
# DJANGO COMMAND
# ===============================

class Command(BaseCommand):
    help = "Run Payless Telegram Bot"

    def handle(self, *args, **kwargs):
        load_dotenv()
        token = os.getenv("TELEGRAM_BOT_TOKEN")

        if not token:
            self.stdout.write(
                self.style.ERROR("TELEGRAM_BOT_TOKEN not found")
            )
            return

        app = ApplicationBuilder().token(token).build()

        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
        )

        self.stdout.write(self.style.SUCCESS("Bot running..."))
        app.run_polling()
