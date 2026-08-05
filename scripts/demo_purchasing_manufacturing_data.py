from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.inventory.models import Product
from apps.manufacturing.models import (
    BillOfMaterial,
    BillOfMaterialLine,
)
from apps.organizations.models import Company
from apps.purchasing.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseOrderReceipt,
    PurchaseRequest,
    Supplier,
    SupplierInvoice,
    SupplierInvoiceLine,
)


COMPANY_NAME = "Glauria Demo A.Ş."
OWNER_USERNAME = "ikra"

company = Company.objects.get(name=COMPANY_NAME)
owner = get_user_model().objects.get(username=OWNER_USERNAME)


# ---------------------------------------------------------
# SATIN ALMA SİPARİŞİ VE TEDARİKÇİ FATURASI
# ---------------------------------------------------------

purchase_request = (
    PurchaseRequest.objects
    .filter(company=company)
    .prefetch_related("lines")
    .order_by("created_at")
    .first()
)

supplier = (
    Supplier.objects
    .filter(company=company, is_active=True)
    .order_by("code")
    .first()
)

if purchase_request is None:
    raise RuntimeError(
        "Demo şirkete ait satın alma talebi bulunamadı. "
        "Önce seed_demo komutunu çalıştır."
    )

if supplier is None:
    raise RuntimeError(
        "Demo şirkete ait aktif tedarikçi bulunamadı."
    )

request_line = purchase_request.lines.first()

if request_line is None:
    raise RuntimeError(
        "Demo satın alma talebine bağlı kalem bulunamadı."
    )


purchase_order, purchase_order_created = (
    PurchaseOrder.objects.update_or_create(
        purchase_request=purchase_request,
        defaults={
            "company": company,
            "supplier": supplier,
            "order_number": "PO-DEMO-2026-001",
            "status": "received",
            "currency": "TRY",
            "order_date": date.today() - timedelta(days=20),
            "expected_delivery_date": (
                date.today() - timedelta(days=7)
            ),
            "notes": (
                "Sunum demosu için oluşturulan ve teslim alınmış "
                "satın alma siparişi."
            ),
            "created_by": owner,
            "sent_by": owner,
            "sent_at": timezone.now() - timedelta(days=19),
            "confirmed_by": owner,
            "confirmed_at": timezone.now() - timedelta(days=18),
        },
    )
)


purchase_order_line, purchase_order_line_created = (
    PurchaseOrderLine.objects.update_or_create(
        purchase_request_line=request_line,
        defaults={
            "purchase_order": purchase_order,
            "budget_account": request_line.budget_account,
            "description": request_line.description,
            "quantity": request_line.quantity,
            "unit_price": request_line.unit_price,
            "received_quantity": request_line.quantity,
            "expected_delivery_date": (
                purchase_order.expected_delivery_date
            ),
        },
    )
)


receipt, receipt_created = (
    PurchaseOrderReceipt.objects.update_or_create(
        company=company,
        purchase_order_line=purchase_order_line,
        reference_number="GRN-DEMO-2026-001",
        defaults={
            "receipt_date": date.today() - timedelta(days=7),
            "quantity": purchase_order_line.quantity,
            "notes": (
                "Demo siparişin eksiksiz teslim alma kaydı."
            ),
            "received_by": owner,
        },
    )
)


supplier_invoice, supplier_invoice_created = (
    SupplierInvoice.objects.update_or_create(
        company=company,
        invoice_number="FTR-DEMO-2026-001",
        defaults={
            "purchase_order": purchase_order,
            "supplier": supplier,
            "invoice_date": date.today() - timedelta(days=6),
            "due_date": date.today() + timedelta(days=24),
            "currency": "TRY",
            "status": "approved",
            "notes": (
                "Teslim alınan demo satın alma siparişine bağlı "
                "tedarikçi faturası."
            ),
            "created_by": owner,
            "approved_by": owner,
            "approved_at": timezone.now() - timedelta(days=5),
        },
    )
)


supplier_invoice_line, supplier_invoice_line_created = (
    SupplierInvoiceLine.objects.update_or_create(
        supplier_invoice=supplier_invoice,
        purchase_order_line=purchase_order_line,
        defaults={
            "description": purchase_order_line.description,
            "quantity": purchase_order_line.quantity,
            "unit_price": purchase_order_line.unit_price,
        },
    )
)


# ---------------------------------------------------------
# ÜRÜN REÇETELERİ — BILL OF MATERIALS
# ---------------------------------------------------------

products = {
    product.sku: product
    for product in Product.objects.filter(company=company)
}

required_skus = {
    "SERUM-001",
    "KREM-001",
    "TONIK-001",
    "HAM-HA-001",
    "HAM-GLS-001",
    "AMB-SISE-30",
    "AMB-KUTU-01",
}

missing_skus = required_skus - set(products)

if missing_skus:
    raise RuntimeError(
        "Reçete için gerekli demo ürünleri bulunamadı: "
        + ", ".join(sorted(missing_skus))
    )


BOM_DATA = [
    {
        "finished_sku": "SERUM-001",
        "yield_quantity": Decimal("100.00"),
        "notes": (
            "100 adet Hyaluronik Asit Serumu üretim reçetesi."
        ),
        "lines": [
            (
                "HAM-HA-001",
                Decimal("0.020"),
                Decimal("2.00"),
            ),
            (
                "HAM-GLS-001",
                Decimal("0.010"),
                Decimal("1.50"),
            ),
            (
                "AMB-SISE-30",
                Decimal("1.000"),
                Decimal("1.00"),
            ),
            (
                "AMB-KUTU-01",
                Decimal("1.000"),
                Decimal("1.00"),
            ),
        ],
    },
    {
        "finished_sku": "KREM-001",
        "yield_quantity": Decimal("100.00"),
        "notes": (
            "100 adet Yoğun Nemlendirici Krem üretim reçetesi."
        ),
        "lines": [
            (
                "HAM-GLS-001",
                Decimal("0.035"),
                Decimal("2.00"),
            ),
            (
                "HAM-HA-001",
                Decimal("0.008"),
                Decimal("1.50"),
            ),
            (
                "AMB-KUTU-01",
                Decimal("1.000"),
                Decimal("1.00"),
            ),
        ],
    },
    {
        "finished_sku": "TONIK-001",
        "yield_quantity": Decimal("100.00"),
        "notes": (
            "100 adet Arındırıcı Yüz Toniği üretim reçetesi."
        ),
        "lines": [
            (
                "HAM-GLS-001",
                Decimal("0.015"),
                Decimal("1.50"),
            ),
            (
                "HAM-HA-001",
                Decimal("0.004"),
                Decimal("1.00"),
            ),
            (
                "AMB-SISE-30",
                Decimal("1.000"),
                Decimal("1.00"),
            ),
            (
                "AMB-KUTU-01",
                Decimal("1.000"),
                Decimal("1.00"),
            ),
        ],
    },
]


created_bom_count = 0
created_bom_line_count = 0

for bom_data in BOM_DATA:
    finished_product = products[bom_data["finished_sku"]]

    bom, bom_created = BillOfMaterial.objects.update_or_create(
        company=company,
        product=finished_product,
        version=1,
        defaults={
            "yield_quantity": bom_data["yield_quantity"],
            "is_active": True,
            "notes": bom_data["notes"],
        },
    )

    if bom_created:
        created_bom_count += 1

    for line_order, (
        component_sku,
        quantity_per_unit,
        scrap_rate,
    ) in enumerate(
        bom_data["lines"],
        start=1,
    ):
        component = products[component_sku]

        _, line_created = (
            BillOfMaterialLine.objects.update_or_create(
                bill_of_material=bom,
                component=component,
                defaults={
                    "quantity_per_unit": quantity_per_unit,
                    "scrap_rate": scrap_rate,
                    "line_order": line_order,
                },
            )
        )

        if line_created:
            created_bom_line_count += 1


print()
print("=" * 72)
print("SATIN ALMA VE ÜRETİM DEMO VERİLERİ HAZIR")
print("=" * 72)
print(
    "Satın alma siparişi:",
    PurchaseOrder.objects.filter(company=company).count(),
)
print(
    "Teslim alma kaydı:",
    PurchaseOrderReceipt.objects.filter(
        company=company
    ).count(),
)
print(
    "Tedarikçi faturası:",
    SupplierInvoice.objects.filter(company=company).count(),
)
print(
    "Ürün reçetesi:",
    BillOfMaterial.objects.filter(company=company).count(),
)
print(
    "Reçete kalemi:",
    BillOfMaterialLine.objects.filter(
        bill_of_material__company=company
    ).count(),
)
print("-" * 72)
print(
    "Yeni sipariş oluşturuldu:",
    purchase_order_created,
)
print(
    "Yeni sipariş kalemi oluşturuldu:",
    purchase_order_line_created,
)
print(
    "Yeni teslim alma kaydı oluşturuldu:",
    receipt_created,
)
print(
    "Yeni tedarikçi faturası oluşturuldu:",
    supplier_invoice_created,
)
print(
    "Yeni fatura kalemi oluşturuldu:",
    supplier_invoice_line_created,
)
print(
    "Yeni reçete sayısı:",
    created_bom_count,
)
print(
    "Yeni reçete kalemi sayısı:",
    created_bom_line_count,
)
print("=" * 72)


# ---------------------------------------------------------
# GENİŞLETİLMİŞ SATIN ALMA DEMO VERİLERİ
# ---------------------------------------------------------

from apps.finance.models import FinanceBudgetAccount
from apps.purchasing.models import PurchaseRequestLine


EXTRA_SUPPLIERS = [
    {
        "code": "TED-HAMMADDE-01",
        "name": "Anatolia Kimya Hammaddeleri",
        "legal_name": "Anatolia Kimya Hammaddeleri Sanayi A.Ş.",
        "tax_number": "5555555501",
        "tax_office": "Ostim",
        "contact_name": "Seda Akın",
        "email": "seda@anatoliakimya.demo",
        "phone": "+90 312 510 10 01",
        "address": "Ostim, Ankara",
        "payment_term_days": 30,
    },
    {
        "code": "TED-AMBALAJ-01",
        "name": "Prestij Ambalaj Çözümleri",
        "legal_name": "Prestij Ambalaj Sanayi ve Ticaret Ltd. Şti.",
        "tax_number": "5555555502",
        "tax_office": "İvedik",
        "contact_name": "Emre Can",
        "email": "emre@prestijambalaj.demo",
        "phone": "+90 312 510 10 02",
        "address": "İvedik OSB, Ankara",
        "payment_term_days": 45,
    },
    {
        "code": "TED-LOJISTIK-01",
        "name": "Başkent Lojistik Hizmetleri",
        "legal_name": "Başkent Lojistik ve Dağıtım A.Ş.",
        "tax_number": "5555555503",
        "tax_office": "Sincan",
        "contact_name": "Gökhan Arı",
        "email": "operasyon@baskentlojistik.demo",
        "phone": "+90 312 510 10 03",
        "address": "Sincan, Ankara",
        "payment_term_days": 20,
    },
    {
        "code": "TED-LAB-01",
        "name": "İleri Laboratuvar Sistemleri",
        "legal_name": "İleri Laboratuvar Cihazları Ltd. Şti.",
        "tax_number": "5555555504",
        "tax_office": "Çankaya",
        "contact_name": "Derya Koç",
        "email": "satis@ilerilab.demo",
        "phone": "+90 312 510 10 04",
        "address": "Çankaya, Ankara",
        "payment_term_days": 60,
    },
]


extra_suppliers = {}

for item in EXTRA_SUPPLIERS:
    supplier, _ = Supplier.objects.update_or_create(
        company=company,
        code=item["code"],
        defaults={
            **item,
            "is_active": True,
        },
    )
    extra_suppliers[item["code"]] = supplier


budget_account = (
    FinanceBudgetAccount.objects
    .filter(company=company)
    .order_by("code")
    .first()
)

if budget_account is None:
    raise RuntimeError(
        "Satın alma talepleri için bütçe hesabı bulunamadı."
    )


EXTRA_REQUESTS = [
    {
        "title": "Serum Şişesi ve Pompa Tedariki",
        "description": (
            "Yeni serum üretim planı için şişe ve pompa tedariki."
        ),
        "needed_by_date": date.today() + timedelta(days=18),
        "line_description": "30 ml serum şişesi ve pompa seti",
        "quantity": Decimal("1200.00"),
        "unit_price": Decimal("18.50"),
        "supplier_code": "TED-AMBALAJ-01",
        "order_status": "confirmed",
        "invoice_status": "pending_approval",
    },
    {
        "title": "Hyaluronik Asit Hammaddesi Alımı",
        "description": (
            "Üretim planı için yüksek saflıkta hyaluronik asit alımı."
        ),
        "needed_by_date": date.today() + timedelta(days=12),
        "line_description": "Kozmetik sınıf hyaluronik asit hammaddesi",
        "quantity": Decimal("40.00"),
        "unit_price": Decimal("2450.00"),
        "supplier_code": "TED-HAMMADDE-01",
        "order_status": "partially_received",
        "invoice_status": "approved",
    },
    {
        "title": "Bitkisel Gliserin Tedariki",
        "description": (
            "Krem ve tonik reçetelerinde kullanılmak üzere gliserin alımı."
        ),
        "needed_by_date": date.today() + timedelta(days=10),
        "line_description": "Bitkisel gliserin",
        "quantity": Decimal("120.00"),
        "unit_price": Decimal("310.00"),
        "supplier_code": "TED-HAMMADDE-01",
        "order_status": "received",
        "invoice_status": "paid",
    },
    {
        "title": "Kalite Kontrol Laboratuvar Ekipmanı",
        "description": (
            "Kalite kontrol süreçleri için pH metre ve hassas terazi alımı."
        ),
        "needed_by_date": date.today() + timedelta(days=35),
        "line_description": "Laboratuvar ölçüm cihazları paketi",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("68500.00"),
        "supplier_code": "TED-LAB-01",
        "order_status": "sent",
        "invoice_status": "draft",
    },
    {
        "title": "Ağustos Dağıtım ve Sevkiyat Hizmeti",
        "description": (
            "Ankara ve İstanbul bölgesi ürün dağıtım hizmeti."
        ),
        "needed_by_date": date.today() + timedelta(days=7),
        "line_description": "Aylık lojistik ve dağıtım hizmeti",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("42000.00"),
        "supplier_code": "TED-LOJISTIK-01",
        "order_status": "received",
        "invoice_status": "approved",
    },
]


for index, item in enumerate(EXTRA_REQUESTS, start=1):
    purchase_request, _ = PurchaseRequest.objects.update_or_create(
        company=company,
        title=item["title"],
        defaults={
            "currency": "TRY",
            "needed_by_date": item["needed_by_date"],
            "description": item["description"],
            "requested_by": owner,
        },
    )

    request_line, _ = PurchaseRequestLine.objects.update_or_create(
        purchase_request=purchase_request,
        description=item["line_description"],
        defaults={
            "budget_account": budget_account,
            "quantity": item["quantity"],
            "unit_price": item["unit_price"],
            "needed_by_date": item["needed_by_date"],
            "notes": "Genişletilmiş sunum demo verisi.",
        },
    )

    supplier = extra_suppliers[item["supplier_code"]]

    purchase_order, _ = PurchaseOrder.objects.update_or_create(
        purchase_request=purchase_request,
        defaults={
            "company": company,
            "supplier": supplier,
            "order_number": f"PO-DEMO-2026-{index + 1:03d}",
            "status": item["order_status"],
            "currency": "TRY",
            "order_date": date.today() - timedelta(days=14 - index),
            "expected_delivery_date": item["needed_by_date"],
            "notes": "Genişletilmiş demo satın alma siparişi.",
            "created_by": owner,
            "sent_by": owner,
            "sent_at": timezone.now() - timedelta(days=12 - index),
            "confirmed_by": (
                owner
                if item["order_status"] not in {"draft", "sent"}
                else None
            ),
            "confirmed_at": (
                timezone.now() - timedelta(days=10 - index)
                if item["order_status"] not in {"draft", "sent"}
                else None
            ),
        },
    )

    received_quantity = (
        item["quantity"]
        if item["order_status"] == "received"
        else (
            item["quantity"] / Decimal("2")
            if item["order_status"] == "partially_received"
            else Decimal("0.00")
        )
    )

    purchase_order_line, _ = PurchaseOrderLine.objects.update_or_create(
        purchase_request_line=request_line,
        defaults={
            "purchase_order": purchase_order,
            "budget_account": budget_account,
            "description": request_line.description,
            "quantity": request_line.quantity,
            "unit_price": request_line.unit_price,
            "received_quantity": received_quantity,
            "expected_delivery_date": item["needed_by_date"],
        },
    )

    if received_quantity > Decimal("0.00"):
        PurchaseOrderReceipt.objects.update_or_create(
            company=company,
            purchase_order_line=purchase_order_line,
            reference_number=f"GRN-DEMO-2026-{index + 1:03d}",
            defaults={
                "receipt_date": date.today() - timedelta(days=3),
                "quantity": received_quantity,
                "notes": "Genişletilmiş demo teslim alma kaydı.",
                "received_by": owner,
            },
        )

        supplier_invoice, _ = SupplierInvoice.objects.update_or_create(
            company=company,
            invoice_number=f"FTR-DEMO-2026-{index + 1:03d}",
            defaults={
                "purchase_order": purchase_order,
                "supplier": supplier,
                "invoice_date": date.today() - timedelta(days=2),
                "due_date": date.today() + timedelta(
                    days=supplier.payment_term_days
                ),
                "currency": "TRY",
                "status": item["invoice_status"],
                "notes": "Genişletilmiş sunum demo faturası.",
                "created_by": owner,
                "approved_by": (
                    owner
                    if item["invoice_status"] in {
                        "approved",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
                "approved_at": (
                    timezone.now()
                    if item["invoice_status"] in {
                        "approved",
                        "partially_paid",
                        "paid",
                    }
                    else None
                ),
            },
        )

        SupplierInvoiceLine.objects.update_or_create(
            supplier_invoice=supplier_invoice,
            purchase_order_line=purchase_order_line,
            defaults={
                "description": purchase_order_line.description,
                "quantity": received_quantity,
                "unit_price": purchase_order_line.unit_price,
            },
        )


print()
print("=" * 72)
print("GENİŞLETİLMİŞ SATIN ALMA VERİLERİ HAZIR")
print("=" * 72)
print(
    "Satın alma talebi:",
    PurchaseRequest.objects.filter(company=company).count(),
)
print(
    "Tedarikçi:",
    Supplier.objects.filter(company=company).count(),
)
print(
    "Satın alma siparişi:",
    PurchaseOrder.objects.filter(company=company).count(),
)
print(
    "Teslim alma kaydı:",
    PurchaseOrderReceipt.objects.filter(company=company).count(),
)
print(
    "Tedarikçi faturası:",
    SupplierInvoice.objects.filter(company=company).count(),
)
print("=" * 72)
