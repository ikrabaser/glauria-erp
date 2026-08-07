import base64
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.db.models import Avg, Count, Max, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.ai_core.models import (
    AIConversation,
    AIKnowledgeChunk,
    AIKnowledgeDocument,
    AIRequestLog,
    AIConversationAttachment,
    AIConversationMessage,
)
from apps.ai_core.orchestration import (
    FunctionCallingArgumentError,
    FunctionCallingLimitError,
    FunctionCallingRuntime,
    FunctionCallingRuntimeError,
)
from apps.ai_core.services import (
    KnowledgeDocumentIngestionError,
    extract_document_text,
    semantic_search,
    AIConfigurationError,
    AIProviderError,
)
from apps.ai_core.tools import ERPToolError
from apps.ai_core.tasks import index_ai_knowledge_document

from .assistant import resolve_enterprise_ai_access
from .forms import (
    EnterpriseAIAssistantForm,
    KnowledgeDocumentUpdateForm,
    KnowledgeDocumentUploadForm,
)


def _build_image_input(uploaded_image):
    """
    Yüklenen görseli OpenAI girdisi için geçici base64
    data URL biçimine dönüştürür.
    """

    if uploaded_image is None:
        return None

    content_type = (
        getattr(uploaded_image, "content_type", "")
        or ""
    ).lower()

    encoded_content = base64.b64encode(
        uploaded_image.read()
    ).decode("ascii")

    return {
        "data_url": (
            f"data:{content_type};base64,"
            f"{encoded_content}"
        ),
        "detail": "high",
    }


def _conversation_title(message: str) -> str:
    """
    İlk kullanıcı mesajından sidebar için kısa bir sohbet başlığı
    oluşturur.
    """

    normalized_message = " ".join(
        (message or "").split()
    )

    if not normalized_message:
        return "Yeni sohbet"

    maximum_length = 72

    if len(normalized_message) <= maximum_length:
        return normalized_message

    return (
        normalized_message[:maximum_length - 1].rstrip()
        + "…"
    )


def _serialize_tool_calls(tool_calls) -> list[dict]:
    """
    FunctionCallingResult içindeki araç çağrılarını JSONField için
    güvenli sözlüklere dönüştürür.
    """

    serialized_calls = []

    for call in tool_calls:
        raw_output = getattr(
            call,
            "output",
            None,
        )

        serialized_output = json.loads(
            json.dumps(
                raw_output,
                ensure_ascii=False,
                default=str,
            )
        )

        serialized_calls.append(
            {
                "call_id": getattr(
                    call,
                    "call_id",
                    "",
                ),
                "tool_name": getattr(
                    call,
                    "tool_name",
                    "",
                ),
                "arguments": getattr(
                    call,
                    "arguments",
                    {},
                ),
                "output": serialized_output,
                "latency_ms": getattr(
                    call,
                    "latency_ms",
                    0,
                ),
            }
        )

    return serialized_calls


def _get_user_conversations(
    *,
    company,
    user,
):
    return (
        AIConversation.objects
        .filter(
            company=company,
            created_by=user,
            status=AIConversation.Status.ACTIVE,
        )
        .order_by(
            "-last_message_at",
            "-updated_at",
        )
    )


def _resolve_selected_conversation(
    *,
    conversations,
    requested_conversation_id,
):
    if requested_conversation_id:
        return conversations.filter(
            id=requested_conversation_id,
        ).first()

    return conversations.first()


def _can_manage_ai_knowledge(access_context) -> bool:
    """
    Knowledge Base ve chunk yönetim ekranlarını yalnızca
    yetkili yönetim kullanıcılarına açar.
    """

    if access_context is None:
        return False

    user = getattr(
        access_context.membership,
        "user",
        None,
    )

    if user and (
        user.is_superuser
        or user.is_staff
    ):
        return True

    role = str(
        getattr(
            access_context.membership,
            "role",
            "",
        )
        or ""
    ).strip().lower()

    return role in {
        "owner",
        "admin",
        "administrator",
        "company_owner",
    }


@login_required
def knowledge_base_home(request):
    """
    Aktif şirketin bilgi tabanı, chunk ve embedding
    istatistiklerini gösterir.
    """

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if access_context is None:
        return render(
            request,
            "ai_core/knowledge_base.html",
            {
                "current_membership": None,
                "access_error": (
                    "Aktif çalışma alanı üyeliğiniz bulunmuyor."
                ),
            },
            status=403,
        )

    if not _can_manage_ai_knowledge(
        access_context
    ):
        return render(
            request,
            "ai_core/knowledge_base.html",
            {
                "current_membership": (
                    access_context.membership
                ),
                "access_error": (
                    "Knowledge Base yönetimi yalnızca "
                    "şirket sahibi ve yöneticilere açıktır."
                ),
            },
            status=403,
        )

    company = access_context.company

    upload_form = KnowledgeDocumentUploadForm(
        request.POST or None,
        request.FILES or None,
    )

    if (
        request.method == "POST"
        and request.POST.get("action")
        == "upload_knowledge_document"
    ):
        if upload_form.is_valid():
            uploaded_file = (
                upload_form.cleaned_data["file"]
            )

            try:
                extracted = extract_document_text(
                    filename=uploaded_file.name,
                    content=uploaded_file.read(),
                )

                document = (
                    AIKnowledgeDocument.objects.create(
                        company=company,
                        title=upload_form.cleaned_data[
                            "title"
                        ],
                        document_type=(
                            upload_form.cleaned_data[
                                "document_type"
                            ]
                        ),
                        source_type=(
                            AIKnowledgeDocument
                            .SourceType
                            .FILE_UPLOAD
                        ),
                        source_reference=(
                            extracted.filename
                        ),
                        content_text=extracted.text,
                        metadata={
                            "filename": (
                                extracted.filename
                            ),
                            "extension": (
                                extracted.extension
                            ),
                            "uploaded_by": (
                                request.user.username
                            ),
                        },
                    )
                )

                index_ai_knowledge_document.delay(
                    str(document.id),
                    request.user.id,
                )

                messages.success(
                    request,
                    (
                        f"'{document.title}' bilgi tabanına "
                        "eklendi. İndeksleme işlemi kuyruğa alındı."
                    ),
                )

                return redirect(
                    "ai_core:knowledge_base"
                )

            except (
                KnowledgeDocumentIngestionError,
                ValueError,
            ) as error:
                messages.error(
                    request,
                    str(error),
                )

            except Exception:
                messages.error(
                    request,
                    (
                        "Doküman işlenirken beklenmeyen "
                        "bir hata oluştu."
                    ),
                )


    documents = (
        AIKnowledgeDocument.objects
        .filter(company=company)
        .annotate(
            chunk_total=Count("chunks"),
            embedded_chunk_total=Count(
                "chunks",
                filter=models.Q(
                    chunks__embedding__isnull=False
                ),
            ),
        )
        .order_by("-created_at")
    )

    chunk_statistics = (
        AIKnowledgeChunk.objects
        .filter(company=company)
        .aggregate(
            total_chunks=Count("id"),
            embedded_chunks=Count(
                "id",
                filter=models.Q(
                    embedding__isnull=False
                ),
            ),
            average_tokens=Avg("token_count"),
            latest_embedding=Max("embedded_at"),
        )
    )

    document_statistics = (
        AIKnowledgeDocument.objects
        .filter(company=company)
        .aggregate(
            total_documents=Count("id"),
            indexed_documents=Count(
                "id",
                filter=models.Q(
                    status=(
                        AIKnowledgeDocument.Status.INDEXED
                    )
                ),
            ),
            failed_documents=Count(
                "id",
                filter=models.Q(
                    status=(
                        AIKnowledgeDocument.Status.FAILED
                    )
                ),
            ),
            latest_indexing=Max("indexed_at"),
        )
    )

    return render(
        request,
        "ai_core/knowledge_base.html",
        {
            "current_membership": (
                access_context.membership
            ),
            "upload_form": upload_form,
            "documents": documents[:12],
            "document_statistics": (
                document_statistics
            ),
            "chunk_statistics": chunk_statistics,
            "access_error": "",
        },
    )


@login_required
def knowledge_document_detail(
    request,
    document_id,
):
    """
    Aktif şirkete ait tek bir bilgi dokümanını ve
    oluşturulmuş chunk kayıtlarını gösterir.
    """

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if access_context is None:
        return render(
            request,
            "ai_core/knowledge_document_detail.html",
            {
                "current_membership": None,
                "access_error": (
                    "Aktif çalışma alanı üyeliğiniz bulunmuyor."
                ),
            },
            status=403,
        )

    if not _can_manage_ai_knowledge(
        access_context
    ):
        return render(
            request,
            "ai_core/knowledge_document_detail.html",
            {
                "current_membership": (
                    access_context.membership
                ),
                "access_error": (
                    "Chunk Inspector yalnızca şirket "
                    "sahibi ve yöneticilere açıktır."
                ),
            },
            status=403,
        )

    document = get_object_or_404(
        AIKnowledgeDocument.objects.filter(
            company=access_context.company,
        ),
        id=document_id,
    )

    chunks = document.chunks.order_by(
        "chunk_index"
    )

    chunk_statistics = chunks.aggregate(
        total_chunks=Count("id"),
        total_tokens=Sum("token_count"),
        average_tokens=Avg("token_count"),
        embedded_chunks=Count(
            "id",
            filter=models.Q(
                embedding__isnull=False
            ),
        ),
        latest_embedding=Max("embedded_at"),
    )

    return render(
        request,
        "ai_core/knowledge_document_detail.html",
        {
            "current_membership": (
                access_context.membership
            ),
            "document": document,
            "update_form": KnowledgeDocumentUpdateForm(
                initial={
                    "title": document.title,
                    "document_type": document.document_type,
                }
            ),
            "chunks": chunks,
            "chunk_statistics": chunk_statistics,
            "access_error": "",
        },
    )


@login_required
def knowledge_document_update(
    request,
    document_id,
):
    """
    Knowledge Base dokümanının başlık, tür ve
    isteğe bağlı dosya içeriğini günceller.
    """

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if (
        access_context is None
        or not _can_manage_ai_knowledge(access_context)
    ):
        messages.error(
            request,
            "Bu işlem için yetkiniz bulunmuyor.",
        )
        return redirect("ai_core:knowledge_base")

    document = get_object_or_404(
        AIKnowledgeDocument.objects.filter(
            company=access_context.company,
        ),
        id=document_id,
    )

    if request.method != "POST":
        return redirect(
            "ai_core:knowledge_document_detail",
            document_id=document.id,
        )

    form = KnowledgeDocumentUpdateForm(
        request.POST,
        request.FILES,
        initial={
            "title": document.title,
            "document_type": document.document_type,
        },
    )

    if not form.is_valid():
        messages.error(
            request,
            "Doküman güncelleme bilgileri geçerli değil.",
        )
        return redirect(
            "ai_core:knowledge_document_detail",
            document_id=document.id,
        )

    uploaded_file = form.cleaned_data.get("file")

    try:
        document.title = form.cleaned_data["title"]
        document.document_type = (
            form.cleaned_data["document_type"]
        )

        if uploaded_file is not None:
            extracted = extract_document_text(
                filename=uploaded_file.name,
                content=uploaded_file.read(),
            )

            document.content_text = extracted.text
            document.source_type = (
                AIKnowledgeDocument.SourceType.FILE_UPLOAD
            )
            document.source_reference = extracted.filename

            metadata = dict(document.metadata or {})
            metadata.update(
                {
                    "filename": extracted.filename,
                    "extension": extracted.extension,
                    "updated_by": request.user.username,
                }
            )
            document.metadata = metadata

            # Yeni dosya geldiyse mevcut indeks geçersizdir.
            document.status = (
                AIKnowledgeDocument.Status.PENDING
            )
            document.content_hash = ""

        document.save()

        if uploaded_file is not None:
            index_ai_knowledge_document.delay(
                str(document.id),
                request.user.id,
            )

            messages.success(
                request,
                (
                    f"'{document.title}' güncellendi. "
                    "Yeniden indeksleme kuyruğa alındı."
                ),
            )
        else:
            messages.success(
                request,
                f"'{document.title}' güncellendi.",
            )

    except KnowledgeDocumentIngestionError as error:
        messages.error(
            request,
            str(error),
        )

    except Exception:
        messages.error(
            request,
            "Doküman güncellenirken beklenmeyen bir hata oluştu.",
        )

    return redirect(
        "ai_core:knowledge_document_detail",
        document_id=document.id,
    )


@login_required
def knowledge_document_reindex(
    request,
    document_id,
):
    """
    Aktif şirkete ait Knowledge Base dokümanını
    zorunlu olarak yeniden indeksler.
    """

    if request.method != "POST":
        return redirect("ai_core:knowledge_document_detail", document_id=document_id)

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if (
        access_context is None
        or not _can_manage_ai_knowledge(access_context)
    ):
        messages.error(
            request,
            "Bu işlem için yetkiniz bulunmuyor.",
        )
        return redirect("ai_core:knowledge_base")

    document = get_object_or_404(
        AIKnowledgeDocument.objects.filter(
            company=access_context.company,
        ),
        id=document_id,
    )

    try:
        # Mevcut indeksin reuse edilmesini engeller.
        document.status = AIKnowledgeDocument.Status.PENDING
        document.content_hash = ""
        document.save(
            update_fields=[
                "status",
                "content_hash",
                "updated_at",
            ]
        )

        index_ai_knowledge_document.delay(
            str(document.id),
            request.user.id,
        )

        messages.success(
            request,
            (
                f"'{document.title}' için yeniden indeksleme "
                "kuyruğa alındı."
            ),
        )

    except Exception:
        messages.error(
            request,
            "Doküman yeniden indekslenirken bir hata oluştu.",
        )

    return redirect(
        "ai_core:knowledge_document_detail",
        document_id=document.id,
    )


@login_required
def knowledge_document_delete(
    request,
    document_id,
):
    """
    Aktif şirkete ait Knowledge Base dokümanını siler.
    """

    if request.method != "POST":
        return redirect("ai_core:knowledge_document_detail", document_id=document_id)

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if (
        access_context is None
        or not _can_manage_ai_knowledge(access_context)
    ):
        messages.error(
            request,
            "Bu işlem için yetkiniz bulunmuyor.",
        )
        return redirect("ai_core:knowledge_base")

    document = get_object_or_404(
        AIKnowledgeDocument.objects.filter(
            company=access_context.company,
        ),
        id=document_id,
    )

    document_title = document.title
    document.delete()

    messages.success(
        request,
        f"'{document_title}' bilgi tabanından silindi.",
    )

    return redirect("ai_core:knowledge_base")


@login_required
def knowledge_search_playground(request):
    """
    Knowledge Base üzerinde semantic search sonuçlarını
    LLM çağrısından bağımsız olarak test eder.
    """

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if (
        access_context is None
        or not _can_manage_ai_knowledge(access_context)
    ):
        messages.error(
            request,
            "Semantic Search Playground için yetkiniz bulunmuyor.",
        )
        return redirect("ai_core:knowledge_base")

    query = (
        request.GET.get("q", "")
        or ""
    ).strip()

    results = []
    search_error = ""

    if query:
        try:
            matches = semantic_search(
                company=access_context.company,
                requested_by=request.user,
                query=query,
                limit=5,
            )

            results = [
                {
                    "document_id": str(
                        match.document.id
                    ),
                    "document_title": (
                        match.document.title
                    ),
                    "document_type": (
                        match.document
                        .get_document_type_display()
                    ),
                    "chunk_id": str(match.chunk.id),
                    "chunk_index": (
                        match.chunk.chunk_index
                    ),
                    "token_count": (
                        match.chunk.token_count
                    ),
                    "similarity": (
                        match.similarity
                    ),
                    "content": (
                        match.chunk.content
                    ),
                }
                for match in matches
            ]

        except Exception as error:
            search_error = str(error)

    return render(
        request,
        "ai_core/knowledge_search.html",
        {
            "current_membership": (
                access_context.membership
            ),
            "query": query,
            "results": results,
            "search_error": search_error,
        },
    )


@login_required
def ai_operations_dashboard(request):
    """
    Aktif şirkete ait AI isteklerinin operasyonel
    metriklerini ve son çalışma kayıtlarını gösterir.
    """

    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if access_context is None:
        return render(
            request,
            "ai_core/operations.html",
            {
                "current_membership": None,
                "access_error": (
                    "Aktif çalışma alanı üyeliğiniz bulunmuyor."
                ),
            },
            status=403,
        )

    if not _can_manage_ai_knowledge(
        access_context
    ):
        return render(
            request,
            "ai_core/operations.html",
            {
                "current_membership": (
                    access_context.membership
                ),
                "access_error": (
                    "AI operasyon kayıtları yalnızca şirket "
                    "sahibi ve yöneticilere açıktır."
                ),
            },
            status=403,
        )

    logs = AIRequestLog.objects.filter(
        company=access_context.company,
    )

    statistics = logs.aggregate(
        total_requests=Count("id"),
        completed_requests=Count(
            "id",
            filter=models.Q(
                status=AIRequestLog.Status.COMPLETED
            ),
        ),
        failed_requests=Count(
            "id",
            filter=models.Q(
                status=AIRequestLog.Status.FAILED
            ),
        ),
        processing_requests=Count(
            "id",
            filter=models.Q(
                status=AIRequestLog.Status.PROCESSING
            ),
        ),
        average_latency=Avg("latency_ms"),
        total_tokens=Sum("total_tokens"),
    )

    rag_logs = logs.filter(
        request_type=AIRequestLog.RequestType.RAG,
        feature="semantic_knowledge_retrieval",
    )

    rag_statistics = {
        "total_retrievals": rag_logs.count(),
        "average_latency": (
            rag_logs.aggregate(
                value=Avg("latency_ms")
            )["value"]
            or 0
        ),
    }

    rag_source_counts = [
        log.response_metadata.get("source_count", 0)
        for log in rag_logs.only("response_metadata")
    ]

    rag_highest_similarities = [
        log.response_metadata.get("highest_similarity")
        for log in rag_logs.only("response_metadata")
        if log.response_metadata.get(
            "highest_similarity"
        ) is not None
    ]

    rag_statistics["average_source_count"] = (
        sum(rag_source_counts) / len(rag_source_counts)
        if rag_source_counts
        else 0
    )

    rag_statistics["highest_similarity"] = (
        max(rag_highest_similarities)
        if rag_highest_similarities
        else 0
    )

    total_requests = (
        statistics["total_requests"]
        or 0
    )
    completed_requests = (
        statistics["completed_requests"]
        or 0
    )

    success_rate = (
        round(
            completed_requests
            / total_requests
            * 100,
            1,
        )
        if total_requests
        else 0
    )

    latest_logs = (
        logs
        .select_related("requested_by")
        .order_by("-created_at")[:30]
    )

    return render(
        request,
        "ai_core/operations.html",
        {
            "current_membership": (
                access_context.membership
            ),
            "statistics": statistics,
            "rag_statistics": rag_statistics,
            "success_rate": success_rate,
            "latest_logs": latest_logs,
            "access_error": "",
        },
    )


@login_required
def enterprise_ai_assistant(request):
    access_context = resolve_enterprise_ai_access(
        request.user
    )

    if access_context is None:
        return render(
            request,
            "ai_core/assistant.html",
            {
                "form": EnterpriseAIAssistantForm(),
                "current_membership": None,
                "allowed_modules": (),
                "conversations": (),
                "selected_conversation": None,
                "conversation_messages": (),
                "access_error": (
                    "Aktif çalışma alanı üyeliğiniz bulunmuyor."
                ),
            },
            status=403,
        )

    if not access_context.has_available_tools:
        return render(
            request,
            "ai_core/assistant.html",
            {
                "form": EnterpriseAIAssistantForm(),
                "current_membership": (
                    access_context.membership
                ),
                "allowed_modules": (),
                "conversations": (),
                "selected_conversation": None,
                "conversation_messages": (),
                "access_error": (
                    "Glauria AI tarafından kullanılabilen "
                    "bir ERP modülüne erişiminiz bulunmuyor."
                ),
            },
            status=403,
        )

    conversations = _get_user_conversations(
        company=access_context.company,
        user=request.user,
    )

    if (
        request.method == "POST"
        and request.POST.get("action")
        == "archive_conversation"
    ):
        conversation_id = (
            request.POST.get("conversation_id")
            or ""
        ).strip()

        conversation = conversations.filter(
            id=conversation_id,
        ).first()

        if conversation is None:
            messages.error(
                request,
                "Arşivlenecek sohbet bulunamadı.",
            )
        else:
            conversation.status = (
                AIConversation.Status.ARCHIVED
            )
            conversation.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            messages.success(
                request,
                "Sohbet başarıyla silindi.",
            )

        return redirect(
            "/ai/?new=1"
        )

    new_chat_requested = (
        request.GET.get("new") == "1"
    )

    requested_conversation_id = (
        request.POST.get("conversation_id")
        or request.GET.get("conversation")
        or ""
    ).strip()

    if (
        new_chat_requested
        and not requested_conversation_id
    ):
        selected_conversation = None
    else:
        selected_conversation = (
            _resolve_selected_conversation(
                conversations=conversations,
                requested_conversation_id=(
                    requested_conversation_id
                ),
            )
        )

    form = EnterpriseAIAssistantForm(
        request.POST or None,
        request.FILES or None,
    )

    if request.method == "POST" and form.is_valid():
        user_message = form.cleaned_data["message"].strip()
        uploaded_image = form.cleaned_data.get("image")
        image_input = _build_image_input(
            uploaded_image
        )

        if selected_conversation is None:
            selected_conversation = (
                AIConversation.objects.create(
                    company=access_context.company,
                    created_by=request.user,
                    title=_conversation_title(
                        user_message
                    ),
                    last_message_at=timezone.now(),
                )
            )

        try:
            with transaction.atomic():
                user_conversation_message = (
                    AIConversationMessage.objects.create(
                        conversation=selected_conversation,
                        company=access_context.company,
                        role=(
                            AIConversationMessage.Role.USER
                        ),
                        content=user_message,
                    )
                )

                if uploaded_image:
                    uploaded_image.seek(0)

                    AIConversationAttachment.objects.create(
                        message=user_conversation_message,
                        company=access_context.company,
                        attachment_type=(
                            AIConversationAttachment
                            .AttachmentType.IMAGE
                        ),
                        file=uploaded_image,
                        original_filename=(
                            uploaded_image.name
                        ),
                        content_type=(
                            uploaded_image.content_type
                        ),
                        file_size=uploaded_image.size,
                    )

                runtime = FunctionCallingRuntime(
                    company=access_context.company,
                    requested_by=request.user,
                    membership=(
                        access_context.membership
                    ),
                    allowed_modules=(
                        access_context.allowed_modules
                    ),
                )

                result = runtime.invoke(
                    user_message=user_message,
                    assistant_profile=(
                        form.cleaned_data[
                            "response_mode"
                        ]
                    ),
                    image_input=image_input,
                )

                AIConversationMessage.objects.create(
                    conversation=selected_conversation,
                    company=access_context.company,
                    role=(
                        AIConversationMessage.Role.ASSISTANT
                    ),
                    content=result.content,
                    model_name=getattr(result, 'model', ''),
                    response_id=getattr(result, 'response_id', ''),
                    round_count=result.round_count,
                    tool_calls=_serialize_tool_calls(
                        result.tool_calls
                    ),
                    knowledge_sources=[
                        {
                            "chunk_id": source.chunk_id,
                            "document_id": (
                                source.document_id
                            ),
                            "document_title": (
                                source.document_title
                            ),
                            "document_type": (
                                source.document_type
                            ),
                            "chunk_index": (
                                source.chunk_index
                            ),
                            "similarity": (
                                source.similarity
                            ),
                            "token_count": (
                                source.token_count
                            ),
                            "preview": source.preview,
                        }
                        for source in getattr(
                            result,
                            "knowledge_sources",
                            (),
                        )
                    ],
                    metadata={
                        "tool_call_count": len(
                            getattr(
                                result,
                                "tool_calls",
                                (),
                            )
                        ),
                        "response_mode": (
                            form.cleaned_data[
                                "response_mode"
                            ]
                        ),
                        "image": (
                            {
                                "name": uploaded_image.name,
                                "content_type": (
                                    uploaded_image.content_type
                                ),
                                "size": uploaded_image.size,
                            }
                            if uploaded_image
                            else None
                        ),
                    },
                )

                selected_conversation.last_response_id = (
                    getattr(result, 'response_id', '')
                )
                selected_conversation.last_message_at = (
                    timezone.now()
                )
                selected_conversation.save(
                    update_fields=[
                        "last_response_id",
                        "last_message_at",
                        "updated_at",
                    ]
                )

        except (
            AIConfigurationError,
            AIProviderError,
            ERPToolError,
            FunctionCallingArgumentError,
            FunctionCallingLimitError,
            FunctionCallingRuntimeError,
        ) as error:
            messages.error(
                request,
                str(error),
            )

        return redirect(
            (
                f"/ai/?conversation="
                f"{selected_conversation.id}"
            )
        )

    conversation_messages = (
        selected_conversation.messages.prefetch_related(
            "attachments"
        )
        if selected_conversation
        else AIConversationMessage.objects.none()
    )

    latest_assistant_message = (
        conversation_messages
        .filter(
            role=AIConversationMessage.Role.ASSISTANT,
        )
        .order_by("-created_at")
        .first()
    )

    latest_tool_calls = (
        latest_assistant_message.tool_calls
        if latest_assistant_message
        else []
    )

    return render(
        request,
        "ai_core/assistant.html",
        {
            "form": form,
            "can_manage_ai_knowledge": (
                _can_manage_ai_knowledge(
                    access_context
                )
            ),
            "current_membership": (
                access_context.membership
            ),
            "allowed_modules": tuple(
                sorted(
                    access_context.allowed_modules
                )
            ),
            "conversations": conversations,
            "selected_conversation": (
                selected_conversation
            ),
            "conversation_messages": (
                conversation_messages
            ),
            "assistant_answer": "",
            "assistant_error": "",
            "tool_calls": latest_tool_calls,
            "tool_call_count": len(
                latest_tool_calls
            ),
            "round_count": (
                latest_assistant_message.round_count
                if latest_assistant_message
                else 0
            ),
            "access_error": "",
        },
    )
