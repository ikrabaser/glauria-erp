from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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