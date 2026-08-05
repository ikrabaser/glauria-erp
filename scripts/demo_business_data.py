from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.crm.models import Customer, Opportunity
from apps.inventory.models import InventoryLot, Product, Warehouse
from apps.organizations.models import Branch, Company
from apps.sales.models import Invoice, SalesOrder, SalesQuote


COMPANY_NAME = "Glauria Demo A.Ş."
OWNER_USERNAME = "ikra"


company = Company.objects.get(name=COMPANY_NAME)
owner = get_user_model().objects.get(username=OWNER_USERNAME)

branch = (
    Branch.objects.filter(company=company, code="DMO-HQ").first()
    or Branch.objects.filter(company=company).first()
)

if branch is None:
    raise RuntimeError(
        "Demo şirkete bağlı şube bulunamadı."
    )


CUSTOMER_DATA = [
    {
        "name": "Nova Kozmetik A.Ş.",
        "status": Customer.Status.ACTIVE,
        "city": "Ankara",
        "email": "satinalma@novakozmetik.demo",
        "phone": "+90 312 410 10 01",
        "tax_number": "4100000001",
        "tax_office": "Çankaya",
        "billing_address": "Çankaya, Ankara",
    },
    {
        "name": "Luna Beauty Ltd.",
        "status": Customer.Status.ACTIVE,
        "city": "İstanbul",
        "email": "finans@lunabeauty.demo",
        "phone": "+90 212 410 10 02",
        "tax_number": "4100000002",
        "tax_office": "Kadıköy",
        "billing_address": "Kadıköy, İstanbul",
    },
    {
        "name": "Aurelia Dermokozmetik",
        "status": Customer.Status.ACTIVE,
        "city": "İzmir",
        "email": "siparis@aurelia.demo",
        "phone": "+90 232 410 10 03",
        "tax_number": "4100000003",
        "tax_office": "Konak",
        "billing_address": "Konak, İzmir",
    },
    {
        "name": "Velora Kişisel Bakım",
        "status": Customer.Status.ACTIVE,
        "city": "Bursa",
        "email": "operasyon@velora.demo",
        "phone": "+90 224 410 10 04",
        "tax_number": "4100000004",
        "tax_office": "Nilüfer",
        "billing_address": "Nilüfer, Bursa",
    },
    {
        "name": "Elara Sağlık Ürünleri",
        "status": Customer.Status.ACTIVE,
        "city": "Antalya",
        "email": "tedarik@elara.demo",
        "phone": "+90 242 410 10 05",
        "tax_number": "4100000005",
        "tax_office": "Muratpaşa",
        "billing_address": "Muratpaşa, Antalya",
    },
    {
        "name": "Mira Organik Ürünler",
        "status": Customer.Status.ACTIVE,
        "city": "Eskişehir",
        "email": "info@miraorganik.demo",
        "phone": "+90 222 410 10 06",
        "tax_number": "4100000006",
        "tax_office": "Tepebaşı",
        "billing_address": "Tepebaşı, Eskişehir",
    },
    {
        "name": "Serena Profesyonel Bakım",
        "status": Customer.Status.ACTIVE,
        "city": "Kocaeli",
        "email": "satin-alma@serena.demo",
        "phone": "+90 262 410 10 07",
        "tax_number": "4100000007",
        "tax_office": "İzmit",
        "billing_address": "İzmit, Kocaeli",
    },
    {
        "name": "Oria E-Ticaret",
        "status": Customer.Status.ACTIVE,
        "city": "İstanbul",
        "email": "muhasebe@oria.demo",
        "phone": "+90 212 410 10 08",
        "tax_number": "4100000008",
        "tax_office": "Maslak",
        "billing_address": "Sarıyer, İstanbul",
    },
    {
        "name": "Lavinia Spa Grubu",
        "status": Customer.Status.LEAD,
        "city": "Muğla",
        "email": "yonetim@laviniaspa.demo",
        "phone": "+90 252 410 10 09",
        "tax_number": "4100000009",
        "tax_office": "Bodrum",
        "billing_address": "Bodrum, Muğla",
    },
    {
        "name": "Natura Klinik",
        "status": Customer.Status.LEAD,
        "city": "Ankara",
        "email": "klinik@naturaklinik.demo",
        "phone": "+90 312 410 10 10",
        "tax_number": "4100000010",
        "tax_office": "Yenimahalle",
        "billing_address": "Yenimahalle, Ankara",
    },
    {
        "name": "Armoni Güzellik Merkezleri",
        "status": Customer.Status.LEAD,
        "city": "Adana",
        "email": "merkez@armoniguzellik.demo",
        "phone": "+90 322 410 10 11",
        "tax_number": "4100000011",
        "tax_office": "Seyhan",
        "billing_address": "Seyhan, Adana",
    },
    {
        "name": "Purelia Kozmetik",
        "status": Customer.Status.INACTIVE,
        "city": "Konya",
        "email": "info@purelia.demo",
        "phone": "+90 332 410 10 12",
        "tax_number": "4100000012",
        "tax_office": "Selçuklu",
        "billing_address": "Selçuklu, Konya",
    },
]


customers = {}

for item in CUSTOMER_DATA:
    customer, _ = Customer.objects.update_or_create(
        company=company,
        name=item["name"],
        defaults={
            "customer_type": Customer.CustomerType.CORPORATE,
            "status": item["status"],
            "city": item["city"],
            "email": item["email"],
            "phone": item["phone"],
            "tax_number": item["tax_number"],
            "tax_office": item["tax_office"],
            "billing_address": item["billing_address"],
            "created_by": owner,
            "notes": "Glauria ERP sunum demosu için oluşturuldu.",
        },
    )
    customers[item["name"]] = customer


OPPORTUNITY_DATA = [
    (
        "Nova Kozmetik - Serum Tedarik Projesi",
        "Nova Kozmetik A.Ş.",
        Opportunity.Stage.NEGOTIATION,
        Opportunity.Priority.HIGH,
        Decimal("185000.00"),
    ),
    (
        "Luna Beauty - Yıllık Ürün Anlaşması",
        "Luna Beauty Ltd.",
        Opportunity.Stage.PROPOSAL,
        Opportunity.Priority.HIGH,
        Decimal("240000.00"),
    ),
    (
        "Aurelia - Özel Marka Üretimi",
        "Aurelia Dermokozmetik",
        Opportunity.Stage.CONTACTED,
        Opportunity.Priority.HIGH,
        Decimal("320000.00"),
    ),
    (
        "Velora - Nemlendirici Seri Alımı",
        "Velora Kişisel Bakım",
        Opportunity.Stage.WON,
        Opportunity.Priority.MEDIUM,
        Decimal("126000.00"),
    ),
    (
        "Elara - Klinik Bakım Setleri",
        "Elara Sağlık Ürünleri",
        Opportunity.Stage.PROPOSAL,
        Opportunity.Priority.MEDIUM,
        Decimal("98000.00"),
    ),
    (
        "Mira Organik - Doğal Seri Lansmanı",
        "Mira Organik Ürünler",
        Opportunity.Stage.NEGOTIATION,
        Opportunity.Priority.HIGH,
        Decimal("154000.00"),
    ),
    (
        "Serena - Profesyonel Salon Paketi",
        "Serena Profesyonel Bakım",
        Opportunity.Stage.CONTACTED,
        Opportunity.Priority.MEDIUM,
        Decimal("89000.00"),
    ),
    (
        "Oria - E-Ticaret Stok Anlaşması",
        "Oria E-Ticaret",
        Opportunity.Stage.WON,
        Opportunity.Priority.HIGH,
        Decimal("275000.00"),
    ),
    (
        "Lavinia - Spa Ürün Grubu",
        "Lavinia Spa Grubu",
        Opportunity.Stage.LEAD,
        Opportunity.Priority.MEDIUM,
        Decimal("73000.00"),
    ),
    (
        "Natura Klinik - Dermokozmetik Paket",
        "Natura Klinik",
        Opportunity.Stage.LEAD,
        Opportunity.Priority.HIGH,
        Decimal("112000.00"),
    ),
]


opportunities = []

for index, (
    title,
    customer_name,
    stage,
    priority,
    expected_amount,
) in enumerate(OPPORTUNITY_DATA, start=1):
    opportunity, _ = Opportunity.objects.update_or_create(
        company=company,
        customer=customers[customer_name],
        title=title,
        defaults={
            "stage": stage,
            "priority": priority,
            "quote_status": (
                Opportunity.QuoteStatus.ACCEPTED
                if stage == Opportunity.Stage.WON
                else Opportunity.QuoteStatus.DRAFT
            ),
            "expected_amount": expected_amount,
            "expected_close_date": (
                date.today() + timedelta(days=15 + index * 4)
            ),
            "labels": "Kozmetik, B2B, Demo",
            "owner": owner,
            "notes": "Sunum için örnek satış fırsatı.",
        },
    )
    opportunities.append(opportunity)


PRODUCT_DATA = [
    (
        "SERUM-001",
        "Hyaluronik Asit Serumu",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "20",
        "160",
        "12",
    ),
    (
        "KREM-001",
        "Yoğun Nemlendirici Krem",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "25",
        "18",
        "4",
    ),
    (
        "TONIK-001",
        "Arındırıcı Yüz Toniği",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "18",
        "95",
        "10",
    ),
    (
        "MASKE-001",
        "Kil Bazlı Yüz Maskesi",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "15",
        "14",
        "3",
    ),
    (
        "TEMIZ-001",
        "Nazik Yüz Temizleme Jeli",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "22",
        "120",
        "15",
    ),
    (
        "YAG-001",
        "Doğal Bakım Yağı",
        Product.ProductType.FINISHED_GOOD,
        "adet",
        "12",
        "60",
        "5",
    ),
    (
        "HAM-HA-001",
        "Hyaluronik Asit Hammaddesi",
        Product.ProductType.RAW_MATERIAL,
        "kg",
        "8",
        "35",
        "4",
    ),
    (
        "HAM-GLS-001",
        "Bitkisel Gliserin",
        Product.ProductType.RAW_MATERIAL,
        "kg",
        "10",
        "44",
        "6",
    ),
    (
        "AMB-SISE-30",
        "30 ml Serum Şişesi",
        Product.ProductType.PACKAGING,
        "adet",
        "100",
        "450",
        "40",
    ),
    (
        "AMB-KUTU-01",
        "Glauria Ürün Kutusu",
        Product.ProductType.PACKAGING,
        "adet",
        "120",
        "115",
        "10",
    ),
]


warehouse, _ = Warehouse.objects.update_or_create(
    company=company,
    branch=branch,
    code="DMO-MAIN",
    defaults={
        "name": "Glauria Merkez Depo",
        "location": "Ankara Merkez Lojistik Alanı",
        "is_active": True,
    },
)

secondary_warehouse, _ = Warehouse.objects.update_or_create(
    company=company,
    branch=branch,
    code="DMO-QUALITY",
    defaults={
        "name": "Kalite Kontrol Deposu",
        "location": "Ankara Üretim Tesisi",
        "is_active": True,
    },
)


products = {}

for (
    sku,
    name,
    product_type,
    unit,
    reorder_level,
    quantity,
    reserved,
) in PRODUCT_DATA:
    product, _ = Product.objects.update_or_create(
        company=company,
        sku=sku,
        defaults={
            "name": name,
            "product_type": product_type,
            "unit": unit,
            "reorder_level": Decimal(reorder_level),
            "is_active": True,
        },
    )
    products[sku] = product

    InventoryLot.objects.update_or_create(
        product=product,
        warehouse=warehouse,
        lot_number=f"DEMO-{sku}-MAIN",
        defaults={
            "quantity_on_hand": Decimal(quantity),
            "quantity_reserved": Decimal(reserved),
            "status": InventoryLot.Status.AVAILABLE,
            "expiry_date": date.today() + timedelta(days=365),
        },
    )

    InventoryLot.objects.update_or_create(
        product=product,
        warehouse=secondary_warehouse,
        lot_number=f"DEMO-{sku}-QC",
        defaults={
            "quantity_on_hand": Decimal("5.00"),
            "quantity_reserved": Decimal("0.00"),
            "status": InventoryLot.Status.QUARANTINED,
            "expiry_date": date.today() + timedelta(days=420),
        },
    )


QUOTE_DATA = [
    (
        "Nova Kozmetik Serum Teklifi",
        "Nova Kozmetik A.Ş.",
        SalesQuote.Status.ACCEPTED,
        Decimal("185000.00"),
    ),
    (
        "Luna Beauty Yıllık Alım Teklifi",
        "Luna Beauty Ltd.",
        SalesQuote.Status.SENT,
        Decimal("240000.00"),
    ),
    (
        "Aurelia Özel Marka Teklifi",
        "Aurelia Dermokozmetik",
        SalesQuote.Status.DRAFT,
        Decimal("320000.00"),
    ),
    (
        "Velora Nemlendirici Seri Teklifi",
        "Velora Kişisel Bakım",
        SalesQuote.Status.ACCEPTED,
        Decimal("126000.00"),
    ),
    (
        "Elara Klinik Set Teklifi",
        "Elara Sağlık Ürünleri",
        SalesQuote.Status.SENT,
        Decimal("98000.00"),
    ),
    (
        "Mira Organik Lansman Teklifi",
        "Mira Organik Ürünler",
        SalesQuote.Status.ACCEPTED,
        Decimal("154000.00"),
    ),
    (
        "Serena Profesyonel Paket Teklifi",
        "Serena Profesyonel Bakım",
        SalesQuote.Status.DRAFT,
        Decimal("89000.00"),
    ),
    (
        "Oria E-Ticaret Stok Teklifi",
        "Oria E-Ticaret",
        SalesQuote.Status.ACCEPTED,
        Decimal("275000.00"),
    ),
]


quotes = []

for index, (
    title,
    customer_name,
    status,
    total_amount,
) in enumerate(QUOTE_DATA, start=1):
    subtotal = total_amount / Decimal("1.20")
    tax_amount = total_amount - subtotal

    opportunity = next(
        (
            item
            for item in opportunities
            if item.customer_id == customers[customer_name].id
        ),
        None,
    )

    quote, _ = SalesQuote.objects.update_or_create(
        company=company,
        customer=customers[customer_name],
        title=title,
        defaults={
            "opportunity": opportunity,
            "status": status,
            "issue_date": date.today() - timedelta(days=index * 3),
            "valid_until": date.today() + timedelta(days=30),
            "subtotal": subtotal,
            "discount_amount": Decimal("0.00"),
            "taxable_amount": subtotal,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "notes": "Sunum için otomatik oluşturulan demo teklif.",
            "owner": owner,
        },
    )
    quotes.append(quote)


accepted_quotes = [
    quote
    for quote in quotes
    if quote.status == SalesQuote.Status.ACCEPTED
]

ORDER_STATUSES = [
    SalesOrder.Status.CONFIRMED,
    SalesOrder.Status.IN_PRODUCTION,
    SalesOrder.Status.READY_TO_SHIP,
    SalesOrder.Status.COMPLETED,
]

orders = []

for index, quote in enumerate(accepted_quotes):
    order, _ = SalesOrder.objects.update_or_create(
        quote=quote,
        defaults={
            "company": company,
            "customer": quote.customer,
            "status": ORDER_STATUSES[index % len(ORDER_STATUSES)],
            "order_date": date.today() - timedelta(days=12 - index),
            "planned_delivery_date": (
                date.today() + timedelta(days=8 + index * 3)
            ),
            "subtotal": quote.subtotal,
            "discount_amount": quote.discount_amount,
            "taxable_amount": quote.taxable_amount,
            "tax_amount": quote.tax_amount,
            "total_amount": quote.total_amount,
            "notes": "Sunum için oluşturulan demo satış siparişi.",
            "owner": owner,
        },
    )
    orders.append(order)


INVOICE_STATUSES = [
    Invoice.Status.SENT,
    Invoice.Status.OVERDUE,
    Invoice.Status.PARTIALLY_PAID,
    Invoice.Status.PAID,
]

for index, order in enumerate(orders):
    customer = order.customer
    invoice_status = INVOICE_STATUSES[
        index % len(INVOICE_STATUSES)
    ]

    issue_date = date.today() - timedelta(days=25 - index * 4)

    Invoice.objects.update_or_create(
        sales_order=order,
        defaults={
            "company": company,
            "customer": customer,
            "status": invoice_status,
            "currency": "TRY",
            "issue_date": issue_date,
            "due_date": issue_date + timedelta(days=15),
            "issued_at": timezone.now(),
            "sent_at": (
                timezone.now()
                if invoice_status != Invoice.Status.DRAFT
                else None
            ),
            "seller_name": company.name,
            "seller_legal_name": (
                getattr(company, "legal_name", "")
                or company.name
            ),
            "seller_tax_number": getattr(
                company,
                "tax_number",
                "",
            ),
            "seller_tax_office": getattr(
                company,
                "tax_office",
                "",
            ),
            "seller_email": getattr(company, "email", ""),
            "seller_phone": getattr(company, "phone", ""),
            "seller_address": getattr(company, "address", ""),
            "customer_name": customer.name,
            "customer_email": customer.email,
            "customer_phone": customer.phone,
            "customer_tax_number": customer.tax_number,
            "customer_tax_office": customer.tax_office,
            "customer_address": customer.billing_address,
            "subtotal": order.subtotal,
            "discount_amount": order.discount_amount,
            "taxable_amount": order.taxable_amount,
            "tax_amount": order.tax_amount,
            "total_amount": order.total_amount,
            "notes": "Glauria ERP sunum demo faturası.",
            "created_by": owner,
        },
    )


print()
print("=" * 68)
print("DEMO BUSINESS DATA HAZIR")
print("=" * 68)
print(
    "Müşteri:",
    Customer.objects.filter(company=company).count(),
)
print(
    "Satış fırsatı:",
    Opportunity.objects.filter(company=company).count(),
)
print(
    "Teklif:",
    SalesQuote.objects.filter(company=company).count(),
)
print(
    "Sipariş:",
    SalesOrder.objects.filter(company=company).count(),
)
print(
    "Fatura:",
    Invoice.objects.filter(company=company).count(),
)
print(
    "Ürün:",
    Product.objects.filter(company=company).count(),
)
print(
    "Depo:",
    Warehouse.objects.filter(company=company).count(),
)
print(
    "Stok lotu:",
    InventoryLot.objects.filter(
        warehouse__company=company,
    ).count(),
)
print("=" * 68)
