from django.urls import path

from .views import (
    enterprise_ai_assistant,
    knowledge_base_home,
    knowledge_document_detail,
)


app_name = "ai_core"


urlpatterns = [
    path(
        "knowledge/",
        knowledge_base_home,
        name="knowledge_base",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/",
        knowledge_document_detail,
        name="knowledge_document_detail",
    ),
    path(
        "",
        enterprise_ai_assistant,
        name="assistant",
    ),
]
