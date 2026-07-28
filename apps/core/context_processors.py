from apps.accounts.permissions import get_module_access_context

from .models import Notification


def notification_context(request):
    if not request.user.is_authenticated:
        return {
            "unread_notification_count": 0,
            "recent_notifications": [],
        }

    notifications = Notification.objects.filter(
        user=request.user,
    )

    return {
        "unread_notification_count": notifications.filter(
            is_read=False,
        ).count(),
        "recent_notifications": notifications.order_by(
            "is_read",
            "-created_at",
        )[:5],
    }


def module_access_context(request):
    return get_module_access_context(request.user)