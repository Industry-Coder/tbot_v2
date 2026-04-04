from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django import forms
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from .models import Package, Invoice, InvoiceItem

import pytesseract
from PIL import Image
import re


MIN_CBM = Decimal("0.005")
MIN_CHARGE = Decimal("2.00")


# =====================================================
# BULK IMPORT FORM
# =====================================================

class BulkImportForm(forms.Form):
    image = forms.ImageField(label="Upload PNG File")


# =====================================================
# PACKAGE ADMIN
# =====================================================

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):

    change_list_template = "admin/package_changelist.html"

    list_display = (
        "tracking_number",
        "customer_phone",
        "quantity",
        "cbm",
        "goods_type",
        "display_total_cbm",
        "display_final_amount",
        "current_status",
        "date_received",
    )

    search_fields = (
        "tracking_number",
        "customer_phone",
        "receiver_name",
    )

    list_filter = (
        "current_status",
        "date_received",
        "goods_type",
    )

    readonly_fields = (
        "display_rate",
        "display_min_cbm",
        "display_min_charge",
        "display_total_cbm",
        "display_final_amount",
    )

    fieldsets = (
        (None, {
            "fields": (
                "tracking_number",
                "receiver_name",
                "customer_phone",
                "cbm",
                "quantity",
                "goods_type",
                "current_status",
                "current_location",
                "date_received",
            )
        }),
        ("Billing Info", {
            "fields": (
                "display_rate",
                "display_min_cbm",
                "display_min_charge",
                "display_total_cbm",
                "display_final_amount",
            )
        }),
    )

    # =====================================================
    # CUSTOM URL
    # =====================================================

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bulk-import/",
                self.admin_site.admin_view(self.bulk_import_view),
                name="bulk-import-packages",
            ),
        ]
        return custom_urls + urls

    # =====================================================
    # BULK IMPORT VIEW
    # =====================================================

    def bulk_import_view(self, request):
        if request.method == "POST":
            form = BulkImportForm(request.POST, request.FILES)

            if form.is_valid():
                try:
                    image = Image.open(form.cleaned_data["image"])
                    text = pytesseract.image_to_string(image)
                except Exception as e:
                    self.message_user(
                        request,
                        f"OCR Error: {str(e)}",
                        messages.ERROR,
                    )
                    return redirect("../")

                lines = text.split("\n")

                created = 0
                skipped = 0

                for line in lines:

                    tokens = line.strip().split()
                    if len(tokens) < 6:
                        continue

                    tracking = re.sub(r"[^\d]", "", tokens[-1])
                    if len(tracking) < 10:
                        continue

                    decimals = [
                        t for t in tokens[:-1]
                        if re.match(r"\d+\.\d+", t)
                    ]

                    if not decimals:
                        continue

                    try:
                        cbm = Decimal(decimals[-1])
                    except InvalidOperation:
                        continue

                    quantity = next(
                        (int(t) for t in tokens if t.isdigit()),
                        None
                    )

                    if not quantity:
                        continue

                    if not Package.objects.filter(tracking_number=tracking).exists():
                        Package.objects.create(
                            tracking_number=tracking,
                            quantity=quantity,
                            cbm=cbm,
                            date_received=timezone.now().date(),
                        )
                        created += 1
                    else:
                        skipped += 1

                self.message_user(
                    request,
                    f"Import Complete — Created: {created}, Skipped: {skipped}",
                    messages.SUCCESS,
                )

                return redirect("../")

        else:
            form = BulkImportForm()

        return render(
            request,
            "admin/bulk_import.html",
            {
                **self.admin_site.each_context(request),
                "form": form,
                "title": "Bulk Import Packages from PNG",
            },
        )

    # =====================================================
    # DISPLAY METHODS
    # =====================================================

    def display_rate(self, obj):
        if not obj.pk:
            return "Fill CBM & Goods Type → Save"

        total_cbm = obj.total_cbm()

        if obj.goods_type == "SPECIAL":
            return "$280 per CBM"

        if total_cbm >= Decimal("1"):
            return "$240 per CBM"
        else:
            return "$245 per CBM"

    display_rate.short_description = "Rate"

    def display_min_cbm(self, obj):
        return MIN_CBM

    display_min_cbm.short_description = "Minimum CBM"

    def display_min_charge(self, obj):
        return f"${MIN_CHARGE}"

    display_min_charge.short_description = "Minimum Charge ($)"

    def display_total_cbm(self, obj):
        return obj.total_cbm() if obj.pk else "-"

    display_total_cbm.short_description = "Total CBM"

    def display_final_amount(self, obj):
        if not obj.pk:
            return "Save to calculate"

        return f"${obj.final_amount()}"

    display_final_amount.short_description = "Final Charge ($)"


# =====================================================
# INVOICE ITEM INLINE
# =====================================================

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ("tracking_number", "quantity", "cbm", "amount")


# =====================================================
# INVOICE ADMIN
# =====================================================

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):

    list_display = (
        "invoice_number",
        "customer_name",
        "customer_phone",
        "start_date",
        "end_date",
        "total_cbm",
        "total_amount",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "start_date",
        "created_at",
    )

    search_fields = (
        "invoice_number",
        "customer_phone",
        "customer_name",
    )

    ordering = ("-created_at",)

    inlines = [InvoiceItemInline]

    actions = ["mark_as_paid", "mark_as_unpaid"]

    def mark_as_paid(self, request, queryset):
        queryset.update(status="PAID")

    mark_as_paid.short_description = "Mark selected invoices as PAID"

    def mark_as_unpaid(self, request, queryset):
        queryset.update(status="UNPAID")

    mark_as_unpaid.short_description = "Mark selected invoices as UNPAID"