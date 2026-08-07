from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
from apps.ai_core.tools import (
    ERPToolError,
)

from .assistant import resolve_enterprise_ai_access
from .forms import EnterpriseAIAssistantForm


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
                "access_error": (
                    "Glauria AI tarafından kullanılabilen "
                    "bir ERP modülüne erişiminiz bulunmuyor."
                ),
            },
            status=403,
        )

    form = EnterpriseAIAssistantForm(
        request.POST or None
    )

    assistant_answer = ""
    assistant_error = ""
    tool_calls = ()
    round_count = 0

    if request.method == "POST" and form.is_valid():
        try:
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
                user_message=form.cleaned_data[
                    "message"
                ],
            )

            assistant_answer = result.content
            tool_calls = result.tool_calls
            round_count = result.round_count

        except (
            AIConfigurationError,
            AIProviderError,
            ERPToolError,
            FunctionCallingArgumentError,
            FunctionCallingLimitError,
            FunctionCallingRuntimeError,
        ) as error:
            assistant_error = str(error)

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
            "assistant_answer": assistant_answer,
            "assistant_error": assistant_error,
            "tool_calls": tool_calls,
            "tool_call_count": len(tool_calls),
            "round_count": round_count,
            "access_error": "",
        },
    )
