from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import InventoryLotForm, ProductForm, WarehouseForm
from .models import InventoryLot, Product, StockMovement, Warehouse


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


@login_required
def home(request):
    membership = get_active_membership(request.user)

    if membership:
        lots = (
            InventoryLot.objects.select_related(
                "product",
                "warehouse",
            )
            .filter(product__company=membership.company)
        )

        products_count = Product.objects.filter(
            company=membership.company,
            is_active=True,
        ).count()

        warehouses_count = Warehouse.objects.filter(
            company=membership.company,
            is_active=True,
        ).count()
    else:
        lots = InventoryLot.objects.none()
        products_count = 0
        warehouses_count = 0

    return render(
        request,
        "inventory/home.html",
        {
            "lots": lots,
            "products_count": products_count,
            "warehouses_count": warehouses_count,
            "current_membership": membership,
        },
    )


@login_required
def product_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("inventory:home")

    form = ProductForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        product = form.save(commit=False)
        product.company = membership.company
        product.save()

        return redirect("inventory:home")

    return render(
        request,
        "inventory/inventory_form.html",
        {
            "form": form,
            "eyebrow": "Inventory Catalog",
            "title": "Yeni Ürün",
            "description": "Stok, reçete ve üretim süreçlerinde kullanılacak ürün kartını oluşturun.",
            "section_title": "Ürün Bilgileri",
            "cancel_url": "inventory:home",
            "submit_text": "Ürünü Kaydet",
            "current_membership": membership,
        },
    )


@login_required
def warehouse_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("inventory:home")

    form = WarehouseForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        warehouse = form.save(commit=False)
        warehouse.company = membership.company
        warehouse.save()

        return redirect("inventory:home")

    return render(
        request,
        "inventory/inventory_form.html",
        {
            "form": form,
            "eyebrow": "Warehouse Management",
            "title": "Yeni Depo",
            "description": "Hammadde, ambalaj veya bitmiş ürün stoklarının tutulacağı depoyu tanımlayın.",
            "section_title": "Depo Bilgileri",
            "cancel_url": "inventory:home",
            "submit_text": "Depoyu Kaydet",
            "current_membership": membership,
        },
    )


@login_required
def lot_create(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("inventory:home")

    form = InventoryLotForm(request.POST or None)

    form.fields["product"].queryset = Product.objects.filter(
        company=membership.company,
        is_active=True,
    ).order_by("name")

    form.fields["warehouse"].queryset = Warehouse.objects.filter(
        company=membership.company,
        is_active=True,
    ).order_by("name")

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            lot = form.save()

            if lot.quantity_on_hand > 0:
                StockMovement.objects.create(
                    product=lot.product,
                    warehouse=lot.warehouse,
                    lot=lot,
                    movement_type=StockMovement.MovementType.RECEIPT,
                    quantity=lot.quantity_on_hand,
                    reference="Açılış stoğu",
                    created_by=request.user,
                )

        return redirect("inventory:home")

    return render(
        request,
        "inventory/inventory_form.html",
        {
            "form": form,
            "eyebrow": "Lot Traceability",
            "title": "Yeni Stok Lotu",
            "description": "Ürün, depo, lot numarası ve miktar bilgilerini kaydederek izlenebilir stok oluşturun.",
            "section_title": "Lot Bilgileri",
            "cancel_url": "inventory:home",
            "submit_text": "Lotu Kaydet",
            "current_membership": membership,
        },
    )