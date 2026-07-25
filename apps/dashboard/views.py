from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def home(request):
    stats = [
        {
            "title": "Toplam Satış",
            "value": "₺2.450.000",
            "change": "+12,4%",
            "change_class": "positive",
            "description": "Geçen aya göre",
            "icon": "₺",
        },
        {
            "title": "Aktif Sipariş",
            "value": "1.284",
            "change": "+48",
            "change_class": "positive",
            "description": "Bu hafta eklenen",
            "icon": "↗",
        },
        {
            "title": "Kritik Stok",
            "value": "84",
            "change": "Dikkat",
            "change_class": "warning",
            "description": "Minimum seviyenin altında",
            "icon": "!",
        },
        {
            "title": "Üretim Emri",
            "value": "27",
            "change": "9 aktif",
            "change_class": "neutral",
            "description": "Planlanan iş emri",
            "icon": "◆",
        },
    ]

    context = {
        "stats": stats,
    }

    return render(request, "dashboard/home.html", context)