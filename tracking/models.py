from django.db import models
from decimal import Decimal
from datetime import datetime


# ==========================
# CONSTANTS
# ==========================

MIN_CBM = Decimal("0.005")
MIN_CHARGE = Decimal("2.00")


# ==========================
# PACKAGE MODEL
# ==========================

class Package(models.Model):

    GOODS_TYPE_CHOICES = [
        ('NORMAL', 'Normal Goods'),
        ('SPECIAL', 'Special Goods'),
    ]

    tracking_number = models.CharField(max_length=100, unique=True)
    receiver_name = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=20)

    cbm = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("0.000")
    )

    quantity = models.PositiveIntegerField(default=1)

    goods_type = models.CharField(
        max_length=10,
        choices=GOODS_TYPE_CHOICES,
        default='NORMAL'
    )

    current_status = models.CharField(
        max_length=100,
        default="Received in China"
    )

    current_location = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    date_received = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Calculate total CBM (cbm × quantity)
    def total_cbm(self):
        return (self.cbm or Decimal("0")) * Decimal(self.quantity)

    # 🔥 NEW PRICING FUNCTION
    def get_rate(self):
        total_cbm = self.total_cbm()

        if self.goods_type == 'SPECIAL':
            return Decimal("280.00")

        # NORMAL GOODS
        if total_cbm >= Decimal("1.0"):
            return Decimal("240.00")
        else:
            return Decimal("245.00")

    # Calculate final charge
    def final_amount(self):
        total_cbm = self.total_cbm()

        effective_cbm = total_cbm if total_cbm >= MIN_CBM else MIN_CBM

        rate = self.get_rate()

        amount = effective_cbm * rate

        if amount < MIN_CHARGE:
            amount = MIN_CHARGE

        return amount.quantize(Decimal("0.01"))

    def __str__(self):
        return self.tracking_number

    class Meta:
        ordering = ["-created_at"]


# ==========================
# INVOICE MODEL
# ==========================

class Invoice(models.Model):

    STATUS_CHOICES = [
        ("UNPAID", "Unpaid"),
        ("PAID", "Paid"),
    ]

    invoice_number = models.CharField(max_length=50, unique=True)
    customer_phone = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=100)

    start_date = models.DateField()
    end_date = models.DateField()

    total_cbm = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("0.000")
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="UNPAID"
    )

    pdf_file = models.FileField(
        upload_to="invoices/",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Auto generate invoice number
    @staticmethod
    def generate_invoice_number():
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"PL-{now}"

    def __str__(self):
        return self.invoice_number

    class Meta:
        ordering = ["-created_at"]


# ==========================
# INVOICE ITEM MODEL
# ==========================

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        related_name="items",
        on_delete=models.CASCADE
    )

    tracking_number = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)

    cbm = models.DecimalField(
        max_digits=10,
        decimal_places=3
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.tracking_number} ({self.invoice.invoice_number})"

    class Meta:
        ordering = ["id"]