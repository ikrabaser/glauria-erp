from django.urls import path

from .views import (
    ai_operations_dashboard,
    enterprise_ai_assistant,
    knowledge_base_home,
    knowledge_document_delete,
    knowledge_document_detail,
    knowledge_document_reindex,
    knowledge_document_update,
    knowledge_search_playground,
)


app_name = "ai_core"


urlpatterns = [
    path(
        "operations/",
        ai_operations_dashboard,
        name="operations",
    ),
    path(
        "knowledge/",
        knowledge_base_home,
        name="knowledge_base",
    ),
    path(
        "knowledge/search/",
        knowledge_search_playground,
        name="knowledge_search",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/",
        knowledge_document_detail,
        name="knowledge_document_detail",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/update/",
        knowledge_document_update,
        name="knowledge_document_update",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/reindex/",
        knowledge_document_reindex,
        name="knowledge_document_reindex",
    ),
    path(
        "knowledge/documents/<uuid:document_id>/delete/",
        knowledge_document_delete,
        name="knowledge_document_delete",
    ),
    path(
        "",
        enterprise_ai_assistant,
        name="assistant",
    ),
]
