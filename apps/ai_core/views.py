import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.ai_core.models import (
    AIConversation,
    AIConversationMessage,
)
from apps.ai_core.orchestration import (
    FunctionCallingArgumentError,
    FunctionCallingLimitError,
    FunctionCallingRuntime,
    FunctionCallingRuntimeError,
)
from apps.ai_core.services import (
    AIConfigurationError,
    AIProviderError,
)
from apps.ai_core.tools import ERPToolError

from .assistant import resolve_enterprise_ai_access
from .forms import EnterpriseAIAssistantForm


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

    requested_conversation_id = (
        request.POST.get("conversation_id")
        or request.GET.get("conversation")
        or ""
    ).strip()

    selected_conversation = (
        _resolve_selected_conversation(
            conversations=conversations,
            requested_conversation_id=(
                requested_conversation_id
            ),
        )
    )

    form = EnterpriseAIAssistantForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():
        user_message = form.cleaned_data["message"].strip()

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
                AIConversationMessage.objects.create(
                    conversation=selected_conversation,
                    company=access_context.company,
                    role=(
                        AIConversationMessage.Role.USER
                    ),
                    content=user_message,
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
                    metadata={
                        "tool_call_count": len(
                            getattr(
                                result,
                                "tool_calls",
                                (),
                            )
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
        selected_conversation.messages.all()
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
