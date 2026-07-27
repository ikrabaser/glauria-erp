from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import OrganizationMembership
from apps.organizations.models import CompanySubscription

from .forms import SupportTicketForm, SupportTicketUpdateForm
from .models import Notification, SupportTicket
from .tasks import analyze_support_ticket


def get_active_membership(user):
    return (
        user.organization_memberships
        .filter(is_active=True)
        .order_by("-is_primary", "created_at")
        .first()
    )


def health_check(request):
    database_status = "ok"
    redis_status = "ok"

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_status = "error"

    try:
        cache.set("glauria_health_check", "ok", timeout=10)

        if cache.get("glauria_health_check") != "ok":
            redis_status = "error"
    except Exception:
        redis_status = "error"

    overall_status = (
        "ok"
        if database_status == "ok" and redis_status == "ok"
        else "error"
    )

    status_code = 200 if overall_status == "ok" else 503

    return JsonResponse(
        {
            "status": overall_status,
            "services": {
                "database": database_status,
                "redis": redis_status,
            },
        },
        status=status_code,
    )


@login_required
def settings_home(request):
    return render(
        request,
        "core/settings_home.html",
    )


@login_required
def billing_home(request):
    membership = (
        request.user.organization_memberships
        .filter(is_active=True)
        .select_related("company")
        .order_by("-is_primary", "created_at")
        .first()
    )

    subscription = None
    active_member_count = 0
    remaining_member_count = 0

    if membership:
        subscription = (
            CompanySubscription.objects
            .filter(company=membership.company)
            .first()
        )

        active_member_count = membership.company.memberships.filter(
            is_active=True
        ).count()

        if subscription:
            remaining_member_count = max(
                subscription.member_limit - active_member_count,
                0,
            )

    return render(
        request,
        "core/billing_home.html",
        {
            "current_membership": membership,
            "subscription": subscription,
            "active_member_count": active_member_count,
            "remaining_member_count": remaining_member_count,
        },
    )


@login_required
def notifications_home(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by(
        "is_read",
        "-created_at",
    )

    return render(
        request,
        "core/notifications_home.html",
        {
            "notifications": notifications,
        },
    )


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )

    return redirect("core:notifications")


@login_required
def help_center(request):
    return render(
        request,
        "core/help_center.html",
    )


@login_required
def support_tickets(request):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("dashboard:home")

    form = SupportTicketForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        ticket = form.save(commit=False)
        ticket.company = membership.company
        ticket.created_by = request.user
        ticket.save()

        analyze_support_ticket.delay(str(ticket.id))

        messages.success(
            request,
            "Destek talebiniz oluşturuldu. AI ilk değerlendirmesi hazırlanıyor.",
        )

        return redirect("core:support_tickets")

    tickets = (
        SupportTicket.objects
        .filter(
            company=membership.company,
            created_by=request.user,
        )
        .select_related("assigned_to")
        .order_by("-created_at")
    )

    return render(
        request,
        "core/support_tickets.html",
        {
            "form": form,
            "tickets": tickets,
            "current_membership": membership,
        },
    )


@login_required
def support_ticket_detail(request, ticket_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("dashboard:home")

    ticket = get_object_or_404(
        SupportTicket.objects.select_related(
            "created_by",
            "assigned_to",
            "company",
        ),
        id=ticket_id,
        company=membership.company,
    )

    is_support_manager = membership.role in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }

    is_ticket_creator = ticket.created_by_id == request.user.id

    if not is_support_manager and not is_ticket_creator:
        return HttpResponseForbidden(
            "Bu destek talebini görüntüleme yetkiniz bulunmuyor."
        )

    update_form = None

    if is_support_manager:
        update_form = SupportTicketUpdateForm(
            instance=ticket,
            company=membership.company,
        )

    return render(
        request,
        "core/support_ticket_detail.html",
        {
            "ticket": ticket,
            "current_membership": membership,
            "is_support_manager": is_support_manager,
            "update_form": update_form,
        },
    )


@login_required
@require_POST
def support_ticket_update(request, ticket_id):
    membership = get_active_membership(request.user)

    if not membership:
        return redirect("dashboard:home")

    if membership.role not in {
        OrganizationMembership.Role.OWNER,
        OrganizationMembership.Role.ADMIN,
    }:
        return HttpResponseForbidden(
            "Bu destek talebini güncelleme yetkiniz bulunmuyor."
        )

    ticket = get_object_or_404(
        SupportTicket,
        id=ticket_id,
        company=membership.company,
    )

    previous_assigned_to_id = ticket.assigned_to_id
    previous_status = ticket.status

    form = SupportTicketUpdateForm(
        request.POST,
        instance=ticket,
        company=membership.company,
    )

    if not form.is_valid():
        messages.error(
            request,
            "Destek talebi bilgileri güncellenemedi.",
        )

        return redirect(
            "core:support_ticket_detail",
            ticket_id=ticket.id,
        )

    ticket = form.save()

    if (
        ticket.assigned_to_id
        and ticket.assigned_to_id != previous_assigned_to_id
        and ticket.assigned_to_id != request.user.id
    ):
        Notification.objects.create(
            user=ticket.assigned_to,
            notification_type=Notification.NotificationType.INFO,
            title="Size destek talebi atandı",
            message=(
                f'"{ticket.subject}" başlıklı destek talebi '
                "sorumluluğunuza atandı."
            ),
            target_url=reverse(
                "core:support_ticket_detail",
                kwargs={"ticket_id": ticket.id},
            ),
        )

    if ticket.status != previous_status:
        Notification.objects.create(
            user=ticket.created_by,
            notification_type=Notification.NotificationType.INFO,
            title="Destek talebinizin durumu güncellendi",
            message=(
                f'"{ticket.subject}" başlıklı talebinizin durumu '
                f'"{ticket.get_status_display()}" olarak güncellendi.'
            ),
            target_url=reverse(
                "core:support_ticket_detail",
                kwargs={"ticket_id": ticket.id},
            ),
        )

    messages.success(
        request,
        "Destek talebi başarıyla güncellendi.",
    )

    return redirect(
        "core:support_ticket_detail",
        ticket_id=ticket.id,
    )