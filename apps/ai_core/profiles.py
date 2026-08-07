from dataclasses import dataclass


class AssistantProfileError(ValueError):
    """Geçersiz Glauria AI yanıt modu gönderildiğinde oluşur."""


@dataclass(frozen=True)
class AssistantProfile:
    key: str
    label: str
    model: str
    reasoning_effort: str | None = None


ASSISTANT_PROFILES = {
    "fast": AssistantProfile(
        key="fast",
        label="Hızlı",
        model="gpt-4o-mini",
        reasoning_effort=None,
    ),
    "deep": AssistantProfile(
        key="deep",
        label="Derin Analiz",
        model="gpt-5-mini",
        reasoning_effort="high",
    ),
}

DEFAULT_ASSISTANT_PROFILE = "fast"


def resolve_assistant_profile(
    profile_key: str | None,
) -> AssistantProfile:
    normalized_key = (
        profile_key or DEFAULT_ASSISTANT_PROFILE
    ).strip().lower()

    try:
        return ASSISTANT_PROFILES[normalized_key]
    except KeyError as error:
        raise AssistantProfileError(
            "Geçersiz Glauria AI yanıt modu."
        ) from error
