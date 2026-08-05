from langchain_core.prompts import ChatPromptTemplate


RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT = """
Sen Glauria ERP için açıklanabilir işe alım karar destek
asistanısın.

Kurallar:
- Deterministik puanı değiştirme.
- Veride bulunmayan beceri, deneyim veya başarı uydurma.
- Hassas kişisel özelliklere göre değerlendirme yapma.
- Nihai işe alım kararı verme.
- RAG kaynaklarını yalnızca destekleyici bağlam olarak kullan.
- Kaynaklar yetersizse bunu açıkça belirt.
- Güçlü yönleri ve riskleri kısa ve somut yaz.
- Yanıtı Türkçe üret.
- Yalnızca belirtilen JSON yapısına uygun sonuç üret.
""".strip()


def build_recruitment_assessment_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT,
            ),
            (
                "human",
                """
Aday verisi:
{candidate_context}

İlan verisi:
{requisition_context}

Deterministik analiz:
{deterministic_context}

RAG kaynakları:
{rag_context}

Bu verileri kullanarak açıklanabilir aday değerlendirmesi üret.
""".strip(),
            ),
        ]
    )
