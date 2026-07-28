import base64
from io import BytesIO

import qrcode
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML


def build_invoice_qr_data_uri(verification_url):
    qr_image = qrcode.make(verification_url)

    buffer = BytesIO()
    qr_image.save(buffer, format="PNG")

    encoded_image = base64.b64encode(
        buffer.getvalue()
    ).decode("ascii")

    return f"data:image/png;base64,{encoded_image}"


def render_invoice_pdf(invoice, verification_url):
    logo_uri = (
        settings.BASE_DIR
        / "static"
        / "images"
        / "brand"
        / "glauria-logo-light.png"
    ).resolve().as_uri()

    html_content = render_to_string(
        "sales/invoice_pdf.html",
        {
            "invoice": invoice,
            "verification_url": verification_url,
            "verification_qr_data_uri": (
                build_invoice_qr_data_uri(verification_url)
            ),
            "seller_logo_uri": logo_uri,
        },
    )

    return HTML(
        string=html_content,
        base_url=str(settings.BASE_DIR),
    ).write_pdf()