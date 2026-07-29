from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from .models import Invoice
from .services import render_invoice_pdf


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def send_invoice_email(self, invoice_id):
    try:
        invoice = (
            Invoice.objects
            .select_related(
                "sales_order",
                "customer",
            )
            .prefetch_related("lines")
            .get(id=invoice_id)
        )
    except Invoice.DoesNotExist:
        return {
            "status": "skipped",
            "reason": "invoice_not_found",
        }

    if not invoice.customer_email:
        return {
            "status": "skipped",
            "reason": "customer_email_missing",
        }

    verification_path = reverse(
        "sales:invoice_verification",
        kwargs={
            "verification_code": invoice.verification_code,
        },
    )

    verification_url = (
        f"{settings.PUBLIC_BASE_URL}{verification_path}"
    )

    pdf_content = render_invoice_pdf(
        invoice,
        verification_url,
    )

    subject = (
        f"Faturanız hazır: {invoice.invoice_number}"
    )

    text_content = (
        f"Merhaba,\n\n"
        f"{invoice.invoice_number} numaralı satış faturanız "
        f"hazırlanmıştır.\n\n"
        f"Toplam tutar: ₺{invoice.total_amount:.2f}\n"
        f"Faturayı doğrulamak için: {verification_url}\n\n"
        f"Fatura PDF dosyası bu e-postaya eklenmiştir.\n\n"
        f"{invoice.seller_name}"
    )

    html_content = render_to_string(
        "sales/invoice_email.html",
        {
            "invoice": invoice,
            "verification_url": verification_url,
        },
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer_email],
    )

    email.attach_alternative(
        html_content,
        "text/html",
    )

    email.attach(
        f"{invoice.invoice_number}.pdf",
        pdf_content,
        "application/pdf",
    )

    sent_count = email.send(fail_silently=False)

    if sent_count != 1:
        raise RuntimeError(
            "Fatura e-postası SMTP sunucusu tarafından kabul edilmedi."
        )

    now = timezone.now()

    update_fields = [
        "sent_at",
        "updated_at",
    ]

    invoice.sent_at = now

    if not invoice.issued_at:
        invoice.issued_at = now
        update_fields.append("issued_at")

    if invoice.status in {
        Invoice.Status.DRAFT,
        Invoice.Status.ISSUED,
    }:
        invoice.status = Invoice.Status.SENT
        update_fields.append("status")

    invoice.save(update_fields=update_fields)

    return {
        "status": "sent",
        "invoice_number": invoice.invoice_number,
        "recipient": invoice.customer_email,
    }