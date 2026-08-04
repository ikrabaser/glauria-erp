from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import (
    EmployeeGoal,
    PerformanceReview,
    PerformanceReviewCycle,
    PerformanceReviewEvent,
)


def normalize_rating(value, field_label):
    """
    Puanı Decimal değerine dönüştürür ve 1–5 aralığını doğrular.
    """

    try:
        rating = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            f"{field_label} geçerli bir sayı olmalıdır."
        )

    if rating < Decimal("1") or rating > Decimal("5"):
        raise ValidationError(
            f"{field_label} 1 ile 5 arasında olmalıdır."
        )

    return rating


def create_performance_review_event(
    *,
    review,
    event_type,
    changed_by,
    new_status,
    previous_status="",
    note="",
):
    """
    Performans değerlendirmesi için değiştirilemez işlem kaydı oluşturur.
    """

    return PerformanceReviewEvent.objects.create(
        review=review,
        company=review.company,
        event_type=event_type,
        previous_status=previous_status,
        new_status=new_status,
        changed_by=changed_by,
        note=note.strip(),
    )


@transaction.atomic
def create_performance_review(
    *,
    company,
    cycle,
    employee,
    manager,
    changed_by,
    note="",
):
    """
    Personel ve değerlendirme dönemi için performans kaydı oluşturur.

    Aynı personel ve dönem için kayıt zaten varsa yeni kayıt üretmez.
    """

    if cycle.company_id != company.id:
        raise ValidationError(
            "Değerlendirme dönemi seçilen şirkete ait olmalıdır."
        )

    if employee.company_id != company.id:
        raise ValidationError(
            "Değerlendirilen personel seçilen şirkete ait olmalıdır."
        )

    if manager.company_id != company.id:
        raise ValidationError(
            "Yönetici seçilen şirkete ait olmalıdır."
        )

    if employee.id == manager.id:
        raise ValidationError(
            "Personel kendi performans yöneticisi olamaz."
        )

    if cycle.status != PerformanceReviewCycle.Status.OPEN:
        raise ValidationError(
            "Performans değerlendirmesi yalnızca açık bir dönem "
            "için oluşturulabilir."
        )

    review, created = PerformanceReview.objects.get_or_create(
        company=company,
        cycle=cycle,
        employee=employee,
        defaults={
            "manager": manager,
            "status": PerformanceReview.Status.DRAFT,
        },
    )

    if created:
        create_performance_review_event(
            review=review,
            event_type=PerformanceReviewEvent.EventType.CREATED,
            changed_by=changed_by,
            new_status=PerformanceReview.Status.DRAFT,
            note=note,
        )

    return review, created


@transaction.atomic
def start_self_review(
    *,
    performance_review,
    changed_by,
    note="",
):
    """
    Taslak değerlendirmeyi çalışan öz değerlendirmesine açar.
    """

    locked_review = (
        PerformanceReview.objects
        .select_for_update()
        .select_related("cycle")
        .get(pk=performance_review.pk)
    )

    if locked_review.status != PerformanceReview.Status.DRAFT:
        raise ValidationError(
            "Yalnızca taslak değerlendirmeler öz değerlendirmeye "
            "açılabilir."
        )

    if (
        locked_review.cycle.status
        != PerformanceReviewCycle.Status.OPEN
    ):
        raise ValidationError(
            "Öz değerlendirme yalnızca açık bir değerlendirme "
            "döneminde başlatılabilir."
        )

    previous_status = locked_review.status
    locked_review.status = PerformanceReview.Status.SELF_REVIEW
    locked_review.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    create_performance_review_event(
        review=locked_review,
        event_type=(
            PerformanceReviewEvent.EventType.SELF_REVIEW_STARTED
        ),
        changed_by=changed_by,
        previous_status=previous_status,
        new_status=locked_review.status,
        note=note,
    )

    return locked_review


@transaction.atomic
def submit_self_review(
    *,
    performance_review,
    changed_by,
    employee_rating,
    employee_comment,
    note="",
):
    """
    Çalışanın öz değerlendirmesini kaydeder ve yönetici aşamasına geçirir.
    """

    locked_review = (
        PerformanceReview.objects
        .select_for_update()
        .get(pk=performance_review.pk)
    )

    if locked_review.status != PerformanceReview.Status.SELF_REVIEW:
        raise ValidationError(
            "Yalnızca öz değerlendirme aşamasındaki kayıtlar "
            "gönderilebilir."
        )

    normalized_comment = employee_comment.strip()

    if not normalized_comment:
        raise ValidationError(
            "Öz değerlendirme gönderilirken çalışan yorumu zorunludur."
        )

    normalized_rating = normalize_rating(
        employee_rating,
        "Çalışan öz değerlendirme puanı",
    )

    previous_status = locked_review.status
    locked_review.employee_rating = normalized_rating
    locked_review.employee_comment = normalized_comment
    locked_review.submitted_at = timezone.now()
    locked_review.status = PerformanceReview.Status.MANAGER_REVIEW

    locked_review.save(
        update_fields=[
            "employee_rating",
            "employee_comment",
            "submitted_at",
            "status",
            "updated_at",
        ]
    )

    create_performance_review_event(
        review=locked_review,
        event_type=(
            PerformanceReviewEvent.EventType.SELF_REVIEW_SUBMITTED
        ),
        changed_by=changed_by,
        previous_status=previous_status,
        new_status=locked_review.status,
        note=note,
    )

    return locked_review


@transaction.atomic
def complete_performance_review(
    *,
    performance_review,
    changed_by,
    manager_rating,
    overall_rating,
    manager_comment,
    development_plan="",
    note="",
):
    """
    Yönetici değerlendirmesini tamamlar ve kaydı kapatır.
    """

    locked_review = (
        PerformanceReview.objects
        .select_for_update()
        .get(pk=performance_review.pk)
    )

    if locked_review.status != PerformanceReview.Status.MANAGER_REVIEW:
        raise ValidationError(
            "Yalnızca yönetici değerlendirmesi aşamasındaki kayıtlar "
            "tamamlanabilir."
        )

    normalized_comment = manager_comment.strip()

    if not normalized_comment:
        raise ValidationError(
            "Değerlendirme tamamlanırken yönetici yorumu zorunludur."
        )

    normalized_manager_rating = normalize_rating(
        manager_rating,
        "Yönetici puanı",
    )
    normalized_overall_rating = normalize_rating(
        overall_rating,
        "Genel performans puanı",
    )

    previous_status = locked_review.status
    locked_review.manager_rating = normalized_manager_rating
    locked_review.overall_rating = normalized_overall_rating
    locked_review.manager_comment = normalized_comment
    locked_review.development_plan = development_plan.strip()
    locked_review.completed_at = timezone.now()
    locked_review.completed_by = changed_by
    locked_review.status = PerformanceReview.Status.COMPLETED

    locked_review.save(
        update_fields=[
            "manager_rating",
            "overall_rating",
            "manager_comment",
            "development_plan",
            "completed_at",
            "completed_by",
            "status",
            "updated_at",
        ]
    )

    create_performance_review_event(
        review=locked_review,
        event_type=PerformanceReviewEvent.EventType.COMPLETED,
        changed_by=changed_by,
        previous_status=previous_status,
        new_status=locked_review.status,
        note=note,
    )

    return locked_review


@transaction.atomic
def cancel_performance_review(
    *,
    performance_review,
    changed_by,
    cancellation_note,
):
    """
    Aktif performans değerlendirmesini gerekçesiyle iptal eder.
    """

    normalized_note = cancellation_note.strip()

    if not normalized_note:
        raise ValidationError(
            "Performans değerlendirmesi iptal edilirken gerekçe "
            "zorunludur."
        )

    locked_review = (
        PerformanceReview.objects
        .select_for_update()
        .get(pk=performance_review.pk)
    )

    if locked_review.status in {
        PerformanceReview.Status.COMPLETED,
        PerformanceReview.Status.CANCELLED,
    }:
        raise ValidationError(
            "Tamamlanmış veya iptal edilmiş değerlendirme yeniden "
            "iptal edilemez."
        )

    previous_status = locked_review.status
    locked_review.status = PerformanceReview.Status.CANCELLED
    locked_review.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    create_performance_review_event(
        review=locked_review,
        event_type=PerformanceReviewEvent.EventType.CANCELLED,
        changed_by=changed_by,
        previous_status=previous_status,
        new_status=locked_review.status,
        note=normalized_note,
    )

    return locked_review


@transaction.atomic
def update_employee_goal_progress(
    *,
    employee_goal,
    changed_by,
    progress_percentage,
    current_value=None,
    completion_note="",
):
    """
    Personel hedefinin ilerleme oranını ve yaşam döngüsü durumunu günceller.
    """

    del changed_by

    locked_goal = (
        EmployeeGoal.objects
        .select_for_update()
        .get(pk=employee_goal.pk)
    )

    if locked_goal.status == EmployeeGoal.Status.CANCELLED:
        raise ValidationError(
            "İptal edilmiş hedefin ilerlemesi güncellenemez."
        )

    try:
        normalized_progress = Decimal(str(progress_percentage))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(
            "İlerleme yüzdesi geçerli bir sayı olmalıdır."
        )

    if (
        normalized_progress < Decimal("0")
        or normalized_progress > Decimal("100")
    ):
        raise ValidationError(
            "İlerleme yüzdesi 0 ile 100 arasında olmalıdır."
        )

    locked_goal.progress_percentage = normalized_progress

    update_fields = [
        "progress_percentage",
        "status",
        "updated_at",
    ]

    if current_value is not None:
        try:
            locked_goal.current_value = Decimal(str(current_value))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError(
                "Mevcut hedef değeri geçerli bir sayı olmalıdır."
            )

        update_fields.append("current_value")

    if normalized_progress == Decimal("100"):
        locked_goal.status = EmployeeGoal.Status.COMPLETED
        locked_goal.completion_note = completion_note.strip()
        update_fields.append("completion_note")
    elif normalized_progress > Decimal("0"):
        locked_goal.status = EmployeeGoal.Status.IN_PROGRESS
        locked_goal.completion_note = ""
        update_fields.append("completion_note")
    else:
        locked_goal.status = EmployeeGoal.Status.DRAFT
        locked_goal.completion_note = ""
        update_fields.append("completion_note")

    locked_goal.save(
        update_fields=list(dict.fromkeys(update_fields))
    )

    return locked_goal
