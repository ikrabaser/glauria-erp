import uuid

from django.db import models
from django.utils import timezone
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Model kayıtlarının oluşturulma ve güncellenme zamanlarını tutar.
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Tarihi",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Güncellenme Tarihi",
    )

    class Meta:
        abstract = True


class UUIDModel(models.Model):
    """
    Modeller için UUID tabanlı birincil anahtar sağlar.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    class Meta:
        abstract = True


class ActivatableModel(models.Model):
    """
    Ana verilerin aktif veya pasif hale getirilebilmesini sağlar.
    """

    is_active = models.BooleanField(
        default=True,
        verbose_name="Aktif mi?",
    )

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """
    Soft delete uygulanmış kayıtlar için özel sorgu işlemlerini sağlar.
    """

    def delete(self):
        return super().update(
            is_deleted=True,
            deleted_at=timezone.now(),
        )

    def hard_delete(self):
        return super().delete()

    def active(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """
    Varsayılan olarak silinmemiş kayıtları döndürür.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(
            self.model,
            using=self._db,
        ).filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """
    Silinmiş ve silinmemiş bütün kayıtları döndürür.
    """

    def get_queryset(self):
        return SoftDeleteQuerySet(
            self.model,
            using=self._db,
        )


class SoftDeleteModel(models.Model):
    """
    Kaydı veritabanından fiziksel olarak silmeden pasifleştirir.
    """

    is_deleted = models.BooleanField(
        default=False,
        verbose_name="Silindi mi?",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Silinme Tarihi",
    )

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(
            using=using,
            update_fields=["is_deleted", "deleted_at"],
        )

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(
            update_fields=["is_deleted", "deleted_at"],
        )

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(
            using=using,
            keep_parents=keep_parents,
        )


class BaseModel(UUIDModel, TimeStampedModel):
    """
    ERP içerisindeki çoğu operasyonel model için ortak temel sınıftır.
    """

    class Meta:
        abstract = True


class MasterDataModel(
    UUIDModel,
    TimeStampedModel,
    ActivatableModel,
    SoftDeleteModel,
):
    """
    Ürün, tedarikçi, müşteri ve depo gibi ana veriler için temel sınıftır.
    """

    class Meta:
        abstract = True

class Notification(UUIDModel, TimeStampedModel):
    class NotificationType(models.TextChoices):
        INFO = "info", "Bilgi"
        SUCCESS = "success", "Başarılı"
        WARNING = "warning", "Uyarı"
        ERROR = "error", "Hata"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="Kullanıcı",
    )

    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        verbose_name="Bildirim tipi",
    )

    title = models.CharField(
        max_length=180,
        verbose_name="Başlık",
    )

    message = models.TextField(
        blank=True,
        verbose_name="Mesaj",
    )

    target_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Hedef bağlantı",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="Okundu mu?",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Okunma zamanı",
    )

    class Meta:
        ordering = ["is_read", "-created_at"]
        verbose_name = "Bildirim"
        verbose_name_plural = "Bildirimler"
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} · {self.title}"