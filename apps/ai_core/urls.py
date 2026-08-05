from django.urls import path

from .views import enterprise_ai_assistant


app_name = "ai_core"


urlpatterns = [
    path(
        "",
        enterprise_ai_assistant,
        name="assistant",
    ),
]
