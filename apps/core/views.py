from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.organizations.models import CompanySubscription

from .models import Notification


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