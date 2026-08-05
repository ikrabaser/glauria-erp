from decimal import Decimal

from django.db.models import Sum

from apps.crm.models import Customer, Opportunity
from apps.finance.models import (
    CustomerAccount,
    PaymentPlan,
)
from apps.hr.models import (
    AbsenceRequest,
    Employee,
    JobRequisition,
)
from apps.inventory.models import (
    InventoryLot,
    Product,
    Warehouse,
)
from apps.manufacturing.models import ProductionOrder
from apps.purchasing.models import (
    PurchaseOrder,
    PurchaseRequest,
    Supplier,
)
from apps.sales.models import (
    Invoice,
    SalesOrder,
    SalesQuote,
)

# Projede aktif üyelik bu fonksiyon üzerinden çözülüyor.
from apps.finance.views import get_active_membership


class DashboardOverviewService:
    """
    Dashboard üzerindeki şirket kapsamlı KPI ve modül
    metriklerini gerçek ERP verilerinden üretir.
    """

    def __init__(self, request):
        self.request = request
        self.membership = get_active_membership(request.user)

    @property
    def company(self):
        if not self.membership:
            return None

        return self.membership.company

    def build_context(self):
        if not self.company:
            return {
                "stats": [],
                "dashboard_metrics": self._empty_metrics(),
            }

        critical_stock = self._critical_stock_count()

        return {
            "stats": self._build_stats(
                critical_stock=critical_stock,
            ),
            "dashboard_metrics": self._build_module_metrics(
                critical_stock=critical_stock,
            ),
        }

    def _build_stats(self, *, critical_stock):
        sales_orders = SalesOrder.objects.filter(
            company=self.company,
        )

        total_sales = (
            sales_orders.exclude(
                status=SalesOrder.Status.CANCELLED,
            ).aggregate(
                total=Sum("total_amount"),
            )["total"]
            or Decimal("0.00")
        )

        active_orders = sales_orders.exclude(
            status__in=[
                SalesOrder.Status.COMPLETED,
                SalesOrder.Status.CANCELLED,
            ],
        ).count()

        production_orders = ProductionOrder.objects.filter(
            company=self.company,
        )

        active_production = production_orders.exclude(
            status__in=[
                ProductionOrder.Status.COMPLETED,
                ProductionOrder.Status.CANCELLED,
            ],
        ).count()

        return [
            {
                "title": "Toplam Satış",
                "value": self._format_money(total_sales),
                "change": "Canlı",
                "change_class": "positive",
                "description": "İptal olmayan sipariş toplamı",
                "icon": "₺",
            },
            {
                "title": "Aktif Sipariş",
                "value": str(active_orders),
                "change": "Canlı",
                "change_class": "positive",
                "description": "Devam eden satış siparişleri",
                "icon": "↗",
            },
            {
                "title": "Kritik Stok",
                "value": str(critical_stock),
                "change": (
                    "Dikkat"
                    if critical_stock
                    else "Normal"
                ),
                "change_class": (
                    "warning"
                    if critical_stock
                    else "positive"
                ),
                "description": "Yeniden sipariş seviyesindeki ürün",
                "icon": "!",
            },
            {
                "title": "Üretim Emri",
                "value": str(active_production),
                "change": "Canlı",
                "change_class": "neutral",
                "description": "Devam eden üretim emirleri",
                "icon": "◆",
            },
        ]

    def _build_module_metrics(self, *, critical_stock):
        customers = Customer.objects.filter(
            company=self.company,
        )
        opportunities = Opportunity.objects.filter(
            company=self.company,
        )

        quotes = SalesQuote.objects.filter(
            company=self.company,
        )
        orders = SalesOrder.objects.filter(
            company=self.company,
        )
        invoices = Invoice.objects.filter(
            company=self.company,
        )

        suppliers = Supplier.objects.filter(
            company=self.company,
        )
        purchase_requests = PurchaseRequest.objects.filter(
            company=self.company,
        )
        purchase_orders = PurchaseOrder.objects.filter(
            company=self.company,
        )

        products = Product.objects.filter(
            company=self.company,
        )
        warehouses = Warehouse.objects.filter(
            company=self.company,
        )

        production_orders = ProductionOrder.objects.filter(
            company=self.company,
        )

        customer_accounts = CustomerAccount.objects.filter(
            company=self.company,
        )
        payment_plans = PaymentPlan.objects.filter(
            company=self.company,
        )

        employees = Employee.objects.filter(
            company=self.company,
        )
        absences = AbsenceRequest.objects.filter(
            company=self.company,
        )
        requisitions = JobRequisition.objects.filter(
            company=self.company,
        )

        active_orders = orders.exclude(
            status__in=[
                SalesOrder.Status.COMPLETED,
                SalesOrder.Status.CANCELLED,
            ],
        )

        monthly_sales = (
            orders.exclude(
                status=SalesOrder.Status.CANCELLED,
            ).aggregate(
                total=Sum("total_amount"),
            )["total"]
            or Decimal("0.00")
        )

        active_production = production_orders.exclude(
            status__in=[
                ProductionOrder.Status.COMPLETED,
                ProductionOrder.Status.CANCELLED,
            ],
        )

        return {
            "crm": {
                "customers": customers.count(),
                "active_customers": customers.filter(
                    status=Customer.Status.ACTIVE,
                ).count(),
                "opportunities": opportunities.exclude(
                    stage=Opportunity.Stage.LOST,
                ).count(),
            },
            "sales": {
                "quotes": quotes.count(),
                "orders": active_orders.count(),
                "sales_total": self._format_money(
                    monthly_sales,
                ),
            },
            "purchasing": {
                "suppliers": suppliers.count(),
                "requests": purchase_requests.count(),
                "orders": purchase_orders.count(),
            },
            "inventory": {
                "products": products.count(),
                "warehouses": warehouses.count(),
                "critical_stock": critical_stock,
            },
            "manufacturing": {
                "active": active_production.count(),
                "planned": production_orders.filter(
                    status=ProductionOrder.Status.PLANNED,
                ).count(),
                "completed": production_orders.filter(
                    status=ProductionOrder.Status.COMPLETED,
                ).count(),
            },
            "finance": {
                "open_invoices": invoices.exclude(
                    status__in=[
                        Invoice.Status.PAID,
                        Invoice.Status.CANCELLED,
                    ],
                ).count(),
                "customer_accounts": customer_accounts.count(),
                "payment_plans": payment_plans.count(),
            },
            "hr": {
                "employees": employees.count(),
                "absences": absences.count(),
                "requisitions": requisitions.count(),
            },
        }

    def _critical_stock_count(self):
        products = (
            Product.objects
            .filter(
                company=self.company,
                is_active=True,
                reorder_level__gt=0,
            )
            .prefetch_related("lots")
        )

        critical_count = 0

        for product in products:
            available_quantity = sum(
                (
                    lot.quantity_on_hand
                    - lot.quantity_reserved
                )
                for lot in product.lots.all()
                if lot.status == InventoryLot.Status.AVAILABLE
            )

            if available_quantity <= product.reorder_level:
                critical_count += 1

        return critical_count

    @staticmethod
    def _format_money(value):
        return f"₺{value:,.2f}"

    @staticmethod
    def _empty_metrics():
        return {
            "crm": {
                "customers": 0,
                "active_customers": 0,
                "opportunities": 0,
            },
            "sales": {
                "quotes": 0,
                "orders": 0,
                "sales_total": "₺0.00",
            },
            "purchasing": {
                "suppliers": 0,
                "requests": 0,
                "orders": 0,
            },
            "inventory": {
                "products": 0,
                "warehouses": 0,
                "critical_stock": 0,
            },
            "manufacturing": {
                "active": 0,
                "planned": 0,
                "completed": 0,
            },
            "finance": {
                "open_invoices": 0,
                "customer_accounts": 0,
                "payment_plans": 0,
            },
            "hr": {
                "employees": 0,
                "absences": 0,
                "requisitions": 0,
            },
        }
