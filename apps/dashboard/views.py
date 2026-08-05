from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse

from apps.dashboard.service_layer.overview import (
    DashboardOverviewService,
)


@login_required
def home(request):
    dashboard_context = DashboardOverviewService(
        request
    ).build_context()

    metrics = dashboard_context["dashboard_metrics"]

    module_cards = [
        {
            "title": "CRM",
            "eyebrow": "Müşteri Yönetimi",
            "description": (
                "Müşteri kayıtlarını, iletişim bilgilerini "
                "ve satış ilişkilerini yönetin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                    <circle cx="9" cy="7" r="4"></circle>
                    <path d="M22 21v-2a4 4 0 0 0-3-3.87"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("crm:home"),
            "metrics": [
                {
                    "label": "Toplam müşteri",
                    "value": str(
                        metrics["crm"]["customers"]
                    ),
                },
                {
                    "label": "Aktif müşteri",
                    "value": str(
                        metrics["crm"]["active_customers"]
                    ),
                },
                {
                    "label": "Açık fırsat",
                    "value": str(
                        metrics["crm"]["opportunities"]
                    ),
                },
            ],
        },
        {
            "title": "Satış Yönetimi",
            "eyebrow": "Satış Operasyonları",
            "description": (
                "Teklifleri, siparişleri ve satış süreçlerini "
                "tek merkezden takip edin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M3 3v18h18"></path>
                    <path d="m7 16 4-4 3 3 5-6"></path>
                    <path d="M15 9h4v4"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("sales:home"),
            "metrics": [
                {
                    "label": "Toplam teklif",
                    "value": str(
                        metrics["sales"]["quotes"]
                    ),
                },
                {
                    "label": "Aktif sipariş",
                    "value": str(
                        metrics["sales"]["orders"]
                    ),
                },
                {
                    "label": "Toplam satış",
                    "value": metrics["sales"]["sales_total"],
                },
            ],
        },
        {
            "title": "Satın Alma",
            "eyebrow": "Tedarik Yönetimi",
            "description": (
                "Tedarikçileri, satın alma taleplerini "
                "ve sipariş süreçlerini yönetin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="9" cy="20" r="1"></circle>
                    <circle cx="19" cy="20" r="1"></circle>
                    <path d="M3 4h2l2.4 11.2h11L22 8H7"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("purchasing:home"),
            "metrics": [
                {
                    "label": "Tedarikçi",
                    "value": str(
                        metrics["purchasing"]["suppliers"]
                    ),
                },
                {
                    "label": "Satın alma talebi",
                    "value": str(
                        metrics["purchasing"]["requests"]
                    ),
                },
                {
                    "label": "Satın alma siparişi",
                    "value": str(
                        metrics["purchasing"]["orders"]
                    ),
                },
            ],
        },
        {
            "title": "Stok Yönetimi",
            "eyebrow": "Depo ve Envanter",
            "description": (
                "Ürünleri, depoları, stok hareketlerini "
                "ve envanter seviyelerini izleyin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m21 8-9-5-9 5 9 5 9-5Z"></path>
                    <path d="m3 12 9 5 9-5"></path>
                    <path d="m3 16 9 5 9-5"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("inventory:home"),
            "metrics": [
                {
                    "label": "Toplam ürün",
                    "value": str(
                        metrics["inventory"]["products"]
                    ),
                },
                {
                    "label": "Depo",
                    "value": str(
                        metrics["inventory"]["warehouses"]
                    ),
                },
                {
                    "label": "Kritik stok",
                    "value": str(
                        metrics["inventory"]["critical_stock"]
                    ),
                },
            ],
        },
        {
            "title": "Üretim Yönetimi",
            "eyebrow": "Üretim Operasyonları",
            "description": (
                "Ürün reçetelerini, üretim emirlerini "
                "ve operasyon süreçlerini yönetin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="12" r="3"></circle>
                    <path d="M12 2v3M12 19v3M2 12h3M19 12h3"></path>
                    <path d="m4.9 4.9 2.1 2.1M17 17l2.1 2.1"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("manufacturing:home"),
            "metrics": [
                {
                    "label": "Aktif iş emri",
                    "value": str(
                        metrics["manufacturing"]["active"]
                    ),
                },
                {
                    "label": "Planlanan",
                    "value": str(
                        metrics["manufacturing"]["planned"]
                    ),
                },
                {
                    "label": "Tamamlanan",
                    "value": str(
                        metrics["manufacturing"]["completed"]
                    ),
                },
            ],
        },
        {
            "title": "Finans Yönetimi",
            "eyebrow": "Finansal Yönetim",
            "description": (
                "Gelir, gider, fatura, banka ve cari hesap "
                "süreçlerini takip edin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="2" y="5" width="20" height="14" rx="2"></rect>
                    <path d="M16 12h4"></path>
                    <path d="M2 10h20"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("finance:home"),
            "metrics": [
                {
                    "label": "Açık fatura",
                    "value": str(
                        metrics["finance"]["open_invoices"]
                    ),
                },
                {
                    "label": "Cari hesap",
                    "value": str(
                        metrics["finance"]["customer_accounts"]
                    ),
                },
                {
                    "label": "Ödeme planı",
                    "value": str(
                        metrics["finance"]["payment_plans"]
                    ),
                },
            ],
        },
        {
            "title": "İnsan Kaynakları",
            "eyebrow": "İnsan ve Organizasyon",
            "description": (
                "Personel, departman, izin ve performans "
                "süreçlerini yönetin."
            ),
            "icon": """
                <svg viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="8" r="4"></circle>
                    <path d="M4 21a8 8 0 0 1 16 0"></path>
                </svg>
            """,
            "badge": "Aktif",
            "url": reverse("hr:home"),
            "metrics": [
                {
                    "label": "Toplam personel",
                    "value": str(
                        metrics["hr"]["employees"]
                    ),
                },
                {
                    "label": "İzin talebi",
                    "value": str(
                        metrics["hr"]["absences"]
                    ),
                },
                {
                    "label": "İşe alım talebi",
                    "value": str(
                        metrics["hr"]["requisitions"]
                    ),
                },
            ],
        },
    ]

    return render(
        request,
        "dashboard/home.html",
        {
            "stats": dashboard_context["stats"],
            "module_cards": module_cards,
        },
    )
