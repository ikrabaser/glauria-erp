from django.urls import path

from .views import (
    enterprise_ai_assistant,
    knowledge_base_home,
)


app_name = "ai_core"


urlpatterns = [
    path(
        "knowledge/",
        knowledge_base_home,
        name="knowledge_base",
    ),
    path(
        "",
        enterprise_ai_assistant,
        name="assistant",
    ),
]
