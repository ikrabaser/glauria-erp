from decimal import Decimal
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from apps.core.models import BaseModel
from apps.crm.models import Customer
from apps.organizations.models import Company
from apps.sales.models import Invoice


class CustomerAccount(BaseModel):
    """
    Bir müşterinin, bir şirketteki cari hesabını temsil eder.
    Bakiye ayrı bir alan olarak tutulmaz; hareketlerden hesaplanır.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="customer_accounts",
        verbose_name="Şirket",
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
        verbose_name="Müşteri",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif mi?",
    )

    class Meta:
        ordering = ["customer__name"]
        verbose_name = "Cari hesap"
        verbose_name_plural = "Cari hesaplar"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "customer", "currency"],
                name="unique_customer_account_per_currency",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "customer"]),
            models.Index(fields=["company", "is_active"]),
        ]

    def __str__(self):
        return f"{self.customer.name} · {self.currency}"

    @property
    def debit_total(self):
        return (
            self.transactions.filter(
                status=CustomerAccountTransaction.Status.ACTIVE,
                direction=CustomerAccountTransaction.Direction.DEBIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

    @property
    def credit_total(self):
        return (
            self.transactions.filter(
                status=CustomerAccountTransaction.Status.ACTIVE,
                direction=CustomerAccountTransaction.Direction.CREDIT,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

    @property
    def balance(self):
        return self.debit_total - self.credit_total


class CustomerAccountTransaction(BaseModel):
    """
    Cari hesap hareketi.
    Borç müşterinin şirkete olan borcunu artırır;
    alacak ise tahsilat gibi hareketlerle azaltır.
    """

    class Direction(models.TextChoices):
        DEBIT = "debit", "Borç"
        CREDIT = "credit", "Alacak"

    class TransactionType(models.TextChoices):
        SALES_INVOICE = "sales_invoice", "Satış faturası"
        COLLECTION = "collection", "Tahsilat"
        MANUAL_DEBIT = "manual_debit", "Manuel borç"
        MANUAL_CREDIT = "manual_credit", "Manuel alacak"
        ADJUSTMENT = "adjustment", "Bakiye düzeltmesi"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        REVERSED = "reversed", "Ters kayıt"
        CANCELLED = "cancelled", "İptal"

    account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Cari hesap",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="customer_account_transactions",
        verbose_name="Şirket",
    )

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        related_name="customer_account_transaction",
        null=True,
        blank=True,
        verbose_name="Kaynak satış faturası",
    )

    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="Hareket yönü",
    )

    transaction_type = models.CharField(
        max_length=30,
        choices=TransactionType.choices,
        verbose_name="Hareket tipi",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Durum",
    )

    transaction_date = models.DateField(
        default=timezone.localdate,
        verbose_name="İşlem tarihi",
    )

    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vade tarihi",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Tutar",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Açıklama",
    )

    reference_number = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Referans numarası",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_customer_account_transactions",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Cari hesap hareketi"
        verbose_name_plural = "Cari hesap hareketleri"
        indexes = [
            models.Index(fields=["company", "transaction_date"]),
            models.Index(fields=["account", "status"]),
            models.Index(fields=["company", "transaction_type"]),
            models.Index(fields=["due_date", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="customer_account_transaction_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} · {self.amount} {self.currency}"

class FinancialAccount(BaseModel):
    """
    Şirketin kasa veya banka hesabını temsil eder.
    Bakiye hareketlerden hesaplanır.
    """

    class AccountType(models.TextChoices):
        CASH = "cash", "Kasa"
        BANK = "bank", "Banka"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="financial_accounts",
        verbose_name="Şirket",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Hesap adı",
    )

    account_type = models.CharField(
        max_length=10,
        choices=AccountType.choices,
        verbose_name="Hesap tipi",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    bank_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="Banka adı",
    )

    iban = models.CharField(
        max_length=34,
        blank=True,
        verbose_name="IBAN",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif mi?",
    )

    class Meta:
        ordering = ["account_type", "name"]
        verbose_name = "Kasa / banka hesabı"
        verbose_name_plural = "Kasa / banka hesapları"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name", "currency"],
                name="unique_financial_account_name_per_currency",
            ),
        ]

    def __str__(self):
        return f"{self.name} · {self.currency}"

    @property
    def balance(self):
        incoming = (
            self.transactions.filter(
                direction=FinancialAccountTransaction.Direction.IN,
                status=FinancialAccountTransaction.Status.ACTIVE,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        outgoing = (
            self.transactions.filter(
                direction=FinancialAccountTransaction.Direction.OUT,
                status=FinancialAccountTransaction.Status.ACTIVE,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        return incoming - outgoing


class FinancialAccountTransaction(BaseModel):
    """
    Kasa veya banka hesabındaki para giriş-çıkış hareketi.
    """

    class Direction(models.TextChoices):
        IN = "in", "Giriş"
        OUT = "out", "Çıkış"

    class TransactionType(models.TextChoices):
        COLLECTION = "collection", "Tahsilat"
        PAYMENT = "payment", "Ödeme"
        MANUAL_IN = "manual_in", "Manuel giriş"
        MANUAL_OUT = "manual_out", "Manuel çıkış"

    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        REVERSED = "reversed", "Ters kayıt"
        CANCELLED = "cancelled", "İptal"

    account = models.ForeignKey(
        FinancialAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name="Kasa / banka hesabı",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="financial_account_transactions",
        verbose_name="Şirket",
    )

    customer_account_transaction = models.OneToOneField(
        CustomerAccountTransaction,
        on_delete=models.PROTECT,
        related_name="financial_account_transaction",
        null=True,
        blank=True,
        verbose_name="Bağlı cari hareket",
    )

    direction = models.CharField(
        max_length=5,
        choices=Direction.choices,
        verbose_name="Hareket yönü",
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        verbose_name="Hareket tipi",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="Durum",
    )

    transaction_date = models.DateField(
        default=timezone.localdate,
        verbose_name="İşlem tarihi",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Tutar",
    )

    description = models.CharField(
        max_length=255,
        verbose_name="Açıklama",
    )

    reference_number = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Referans numarası",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_financial_account_transactions",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        verbose_name = "Kasa / banka hareketi"
        verbose_name_plural = "Kasa / banka hareketleri"
        indexes = [
            models.Index(fields=["company", "transaction_date"]),
            models.Index(fields=["account", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="financial_account_transaction_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_transaction_type_display()} "
            f"· {self.amount} {self.account.currency}"
        )

class FinanceBudget(BaseModel):
    """
    Şirketin belirli mali yıl için oluşturduğu bütçe planı.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        PENDING_APPROVAL = "pending_approval", "Onay bekliyor"
        ACTIVE = "active", "Aktif"
        CLOSED = "closed", "Kapandı"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="finance_budgets",
        verbose_name="Şirket",
    )

    name = models.CharField(
        max_length=120,
        verbose_name="Bütçe adı",
    )

    fiscal_year = models.PositiveSmallIntegerField(
        verbose_name="Mali yıl",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Açıklama",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_finance_budgets",
        verbose_name="Oluşturan kullanıcı",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_finance_budgets",
        verbose_name="Onaya gönderen kullanıcı",
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onaya gönderim zamanı",
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_finance_budgets",
        verbose_name="Onaylayan kullanıcı",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Onay zamanı",
    )
    source_budget = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="revisions",
        verbose_name="Kaynak bütçe",
    )

    revision_number = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Revizyon numarası",
    )

    class Meta:
        ordering = ["-fiscal_year", "-created_at"]
        verbose_name = "Finans bütçesi"
        verbose_name_plural = "Finans bütçeleri"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name", "fiscal_year"],
                name="unique_finance_budget_name_per_year",
            ),
            models.UniqueConstraint(
                fields=[
                    "source_budget",
                    "revision_number",
                ],
                name="unique_finance_budget_revision",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "fiscal_year", "status"]),
        ]

    def __str__(self):
        return f"{self.name} · {self.fiscal_year}"


class FinanceBudgetLine(BaseModel):
    """
    Bütçenin aylık gelir ve gider hedef satırı.
    Gerçekleşenler, kasa/banka hareketlerinden hesaplanacaktır.
    """

    budget = models.ForeignKey(
        FinanceBudget,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Bütçe",
    )

    period_month = models.DateField(
        verbose_name="Bütçe ayı",
    )

    category = models.CharField(
        max_length=100,
        verbose_name="Bütçe kalemi",
    )

    planned_inflow = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Planlanan nakit girişi",
    )

    planned_outflow = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Planlanan nakit çıkışı",
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Not",
    )

    class Meta:
        ordering = ["period_month", "category"]
        verbose_name = "Finans bütçe satırı"
        verbose_name_plural = "Finans bütçe satırları"
        constraints = [
            models.UniqueConstraint(
                fields=["budget", "period_month", "category"],
                name="unique_finance_budget_line_per_month",
            ),
            models.CheckConstraint(
                condition=(
                    Q(planned_inflow__gt=0)
                    | Q(planned_outflow__gt=0)
                ),
                name="finance_budget_line_has_planned_amount",
            ),
        ]
        indexes = [
            models.Index(fields=["budget", "period_month"]),
        ]

    def __str__(self):
        return (
            f"{self.budget} · {self.category} · "
            f"{self.period_month:%m.%Y}"
        )

def generate_payment_plan_number():
    return (
        f"PP-{timezone.localdate():%Y}-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )


class PaymentPlan(BaseModel):
    """
    Bir cari hesap için oluşturulan taksitli tahsilat planı.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        ACTIVE = "active", "Aktif"
        COMPLETED = "completed", "Tamamlandı"
        CANCELLED = "cancelled", "İptal"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="payment_plans",
        verbose_name="Şirket",
    )

    customer_account = models.ForeignKey(
        CustomerAccount,
        on_delete=models.PROTECT,
        related_name="payment_plans",
        verbose_name="Cari hesap",
    )

    plan_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_payment_plan_number,
        editable=False,
        verbose_name="Plan numarası",
    )

    total_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Toplam tutar",
    )

    currency = models.CharField(
        max_length=3,
        default="TRY",
        verbose_name="Para birimi",
    )

    installment_count = models.PositiveSmallIntegerField(
        verbose_name="Taksit sayısı",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Durum",
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Açıklama",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_plans",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Ödeme planı"
        verbose_name_plural = "Ödeme planları"
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["customer_account", "status"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(total_amount__gt=0),
                name="payment_plan_total_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(installment_count__gt=0),
                name="payment_plan_installment_count_positive",
            ),
        ]

    def __str__(self):
        return f"{self.plan_number} · {self.customer_account}"


class PaymentPlanInstallment(BaseModel):
    """
    Ödeme planının tekil vade/taksit kaydı.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        PARTIALLY_PAID = "partially_paid", "Kısmi tahsil edildi"
        PAID = "paid", "Tahsil edildi"
        OVERDUE = "overdue", "Vadesi geçti"
        CANCELLED = "cancelled", "İptal"

    payment_plan = models.ForeignKey(
        PaymentPlan,
        on_delete=models.PROTECT,
        related_name="installments",
        verbose_name="Ödeme planı",
    )

    installment_number = models.PositiveSmallIntegerField(
        verbose_name="Taksit sıra numarası",
    )

    due_date = models.DateField(
        verbose_name="Vade tarihi",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Taksit tutarı",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Durum",
    )

    class Meta:
        ordering = ["due_date", "installment_number"]
        verbose_name = "Ödeme planı taksiti"
        verbose_name_plural = "Ödeme planı taksitleri"
        indexes = [
            models.Index(fields=["due_date", "status"]),
            models.Index(fields=["payment_plan", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["payment_plan", "installment_number"],
                name="unique_payment_plan_installment_number",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_plan_installment_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.payment_plan.plan_number} · "
            f"{self.installment_number}. taksit"
        )


class PaymentPlanAllocation(BaseModel):
    """
    Tahsilatın hangi taksite ne kadar uygulandığını tutar.
    """

    installment = models.ForeignKey(
        PaymentPlanInstallment,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name="Taksit",
    )

    collection_transaction = models.ForeignKey(
        CustomerAccountTransaction,
        on_delete=models.PROTECT,
        related_name="payment_plan_allocations",
        verbose_name="Tahsilat hareketi",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Eşleştirilen tutar",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_payment_plan_allocations",
        verbose_name="Oluşturan kullanıcı",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Tahsilat eşleştirmesi"
        verbose_name_plural = "Tahsilat eşleştirmeleri"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "installment",
                    "collection_transaction",
                ],
                name="unique_installment_collection_allocation",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_plan_allocation_amount_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.installment} · "
            f"₺{self.amount:.2f}"
        )

class FinanceAIAnalysis(BaseModel):
    """
    Finans verilerinden üretilen, yalnızca okuma amaçlı AI analizi.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Analiz bekliyor"
        PROCESSING = "processing", "Analiz ediliyor"
        COMPLETED = "completed", "Analiz tamamlandı"
        FAILED = "failed", "Analiz başarısız"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Düşük"
        MEDIUM = "medium", "Orta"
        HIGH = "high", "Yüksek"

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="finance_ai_analyses",
        verbose_name="Şirket",
    )

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_finance_ai_analyses",
        verbose_name="Analizi isteyen kullanıcı",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="AI analiz durumu",
    )

    snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Finans veri özeti",
    )

    executive_summary = models.TextField(
        blank=True,
        verbose_name="Yönetici özeti",
    )

    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        blank=True,
        verbose_name="Risk seviyesi",
    )

    risks = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tespit edilen riskler",
    )

    recommended_actions = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Önerilen aksiyonlar",
    )

    ai_error = models.TextField(
        blank=True,
        verbose_name="AI analiz hatası",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Finans AI analizi"
        verbose_name_plural = "Finans AI analizleri"
        indexes = [
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.company} · "
            f"{self.get_status_display()} · "
            f"{self.created_at:%d.%m.%Y %H:%M}"
        )

class FinanceAIConversation(BaseModel):
    """
    Kullanıcının kendi şirket verileriyle yürüttüğü Finans AI sohbeti.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="finance_ai_conversations",
        verbose_name="Şirket",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="finance_ai_conversations",
        verbose_name="Kullanıcı",
    )

    title = models.CharField(
        max_length=160,
        default="Yeni Finans Sohbeti",
        verbose_name="Sohbet başlığı",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif",
    )

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Finans AI sohbeti"
        verbose_name_plural = "Finans AI sohbetleri"
        indexes = [
            models.Index(
                fields=[
                    "company",
                    "user",
                    "is_active",
                ],
            ),
        ]

    def __str__(self):
        return f"{self.company} · {self.title}"


class FinanceAIMessage(BaseModel):
    """
    Finans AI sohbetindeki kullanıcı ve asistan mesajı.
    """

    class Role(models.TextChoices):
        USER = "user", "Kullanıcı"
        ASSISTANT = "assistant", "Finans AI"

    class Status(models.TextChoices):
        PENDING = "pending", "Bekliyor"
        PROCESSING = "processing", "Yanıt hazırlanıyor"
        COMPLETED = "completed", "Tamamlandı"
        FAILED = "failed", "Başarısız"

    conversation = models.ForeignKey(
        FinanceAIConversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Sohbet",
    )

    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        verbose_name="Mesaj sahibi",
    )

    content = models.TextField(
        verbose_name="Mesaj içeriği",
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.COMPLETED,
        verbose_name="Yanıt durumu",
    )

    context_snapshot = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Kullanılan finans bağlamı",
    )

    ai_error = models.TextField(
        blank=True,
        verbose_name="AI yanıt hatası",
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Finans AI mesajı"
        verbose_name_plural = "Finans AI mesajları"
        indexes = [
            models.Index(
                fields=[
                    "conversation",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "role",
                    "status",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.conversation} · "
            f"{self.get_role_display()} · "
            f"{self.created_at:%d.%m.%Y %H:%M}"
        )

