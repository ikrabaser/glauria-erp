from unittest.mock import patch
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.models import Company

from .models import (
    AIProviderConfiguration,
    AIRequestLog,
)


class AICoreModelTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="AI Core Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="ai.test.user",
            email="ai.test@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

    def test_provider_configuration_has_safe_defaults(self):
        configuration = AIProviderConfiguration.objects.create(
            company=self.company,
        )

        self.assertEqual(
            configuration.provider,
            AIProviderConfiguration.Provider.OPENAI,
        )
        self.assertEqual(
            configuration.default_model,
            "gpt-5.6-sol",
        )
        self.assertEqual(
            configuration.embedding_model,
            "text-embedding-3-small",
        )
        self.assertTrue(configuration.is_enabled)
        self.assertTrue(
            configuration.structured_output_enabled
        )

    def test_company_can_have_only_one_provider_configuration(self):
        AIProviderConfiguration.objects.create(
            company=self.company,
        )

        with self.assertRaises(Exception):
            AIProviderConfiguration.objects.create(
                company=self.company,
            )

    def test_ai_request_log_stores_observability_metadata(self):
        log = AIRequestLog.objects.create(
            company=self.company,
            requested_by=self.user,
            provider=(
                AIProviderConfiguration.Provider.OPENAI
            ),
            model_name="gpt-5.6-sol",
            module="recruitment",
            feature="candidate_matching",
            request_type=AIRequestLog.RequestType.STRUCTURED,
            status=AIRequestLog.Status.COMPLETED,
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            latency_ms=1450,
            request_metadata={
                "candidate_count": 10,
            },
            response_metadata={
                "result_count": 5,
            },
        )

        self.assertEqual(
            log.total_tokens,
            200,
        )
        self.assertEqual(
            log.module,
            "recruitment",
        )
        self.assertEqual(
            log.status,
            AIRequestLog.Status.COMPLETED,
        )
        self.assertEqual(
            log.request_metadata["candidate_count"],
            10,
        )

    def test_failed_request_can_store_error_without_prompt_data(self):
        log = AIRequestLog.objects.create(
            company=self.company,
            requested_by=self.user,
            module="finance",
            feature="executive_summary",
            request_type=AIRequestLog.RequestType.STRUCTURED,
            status=AIRequestLog.Status.FAILED,
            error_type="ProviderTimeoutError",
            error_message="AI sağlayıcısı zaman aşımına uğradı.",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.FAILED,
        )
        self.assertEqual(
            log.error_type,
            "ProviderTimeoutError",
        )
        self.assertNotIn(
            "prompt",
            log.request_metadata,
        )


class FakeUsage:
    input_tokens = 120
    output_tokens = 45
    total_tokens = 165


class FakeResponse:
    def __init__(self, output_text):
        self.id = "resp_ai_core_test"
        self.output_text = output_text
        self.usage = FakeUsage()


class FakeResponsesAPI:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.output_text)


class FakeOpenAIClient:
    def __init__(self, output_text):
        self.responses = FakeResponsesAPI(output_text)


class AICoreProviderTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.services import OpenAIProvider

        self.provider_class = OpenAIProvider

        self.company = Company.objects.create(
            name="AI Provider Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="provider.test.user",
            email="provider.test@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

    def test_generate_text_creates_completed_request_log(self):
        client = FakeOpenAIClient(
            "Aday teknik görüşmeye alınabilir."
        )

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="recruitment",
            feature="candidate_summary",
            client=client,
        )

        result = provider.generate_text(
            instructions="Kısa bir aday özeti üret.",
            input_text="Python ve Django deneyimi bulunuyor.",
        )

        self.assertEqual(
            result.content,
            "Aday teknik görüşmeye alınabilir.",
        )
        self.assertEqual(result.usage.total_tokens, 165)

        log = AIRequestLog.objects.get(
            company=self.company,
            feature="candidate_summary",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.COMPLETED,
        )
        self.assertEqual(log.prompt_tokens, 120)
        self.assertEqual(log.completion_tokens, 45)
        self.assertEqual(log.total_tokens, 165)
        self.assertEqual(
            log.response_metadata["response_id"],
            "resp_ai_core_test",
        )

    def test_generate_structured_returns_dictionary(self):
        client = FakeOpenAIClient(
            '{"score": 87, "recommendation": "interview"}'
        )

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="recruitment",
            feature="candidate_matching",
            client=client,
        )

        result = provider.generate_structured(
            instructions="Aday uyumunu değerlendir.",
            input_text="Aday ve ilan verileri.",
            schema_name="candidate_matching",
            schema={
                "type": "object",
                "properties": {
                    "score": {
                        "type": "integer",
                    },
                    "recommendation": {
                        "type": "string",
                    },
                },
                "required": [
                    "score",
                    "recommendation",
                ],
                "additionalProperties": False,
            },
        )

        self.assertEqual(result.data["score"], 87)
        self.assertEqual(
            result.data["recommendation"],
            "interview",
        )

        request_call = client.responses.calls[0]

        self.assertEqual(
            request_call["text"]["format"]["type"],
            "json_schema",
        )
        self.assertTrue(
            request_call["text"]["format"]["strict"]
        )

    def test_invalid_structured_response_is_logged_as_failed(self):
        from apps.ai_core.services import (
            AIStructuredOutputError,
        )

        client = FakeOpenAIClient("geçerli-json-değil")

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="finance",
            feature="risk_summary",
            client=client,
        )

        with self.assertRaises(AIStructuredOutputError):
            provider.generate_structured(
                instructions="Risk özeti üret.",
                input_text="Finans verileri.",
                schema_name="risk_summary",
                schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            )

        log = AIRequestLog.objects.get(
            company=self.company,
            feature="risk_summary",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.FAILED,
        )
        self.assertEqual(
            log.error_type,
            "AIStructuredOutputError",
        )

    def test_provider_failure_is_standardized_and_logged(self):
        from apps.ai_core.services import AIProviderError

        class FailingResponsesAPI:
            def create(self, **kwargs):
                raise TimeoutError("Provider timeout")

        class FailingClient:
            responses = FailingResponsesAPI()

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="sales",
            feature="quote_summary",
            client=FailingClient(),
        )

        with self.assertRaises(AIProviderError):
            provider.generate_text(
                instructions="Teklifi özetle.",
                input_text="Teklif verileri.",
            )

        log = AIRequestLog.objects.get(
            company=self.company,
            feature="quote_summary",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.FAILED,
        )
        self.assertEqual(
            log.error_type,
            "TimeoutError",
        )

    def test_disabled_company_configuration_blocks_provider(self):
        from apps.ai_core.services import AIConfigurationError

        AIProviderConfiguration.objects.create(
            company=self.company,
            is_enabled=False,
        )

        with self.assertRaises(AIConfigurationError):
            self.provider_class(
                company=self.company,
                requested_by=self.user,
                module="hr",
                feature="performance_summary",
                client=FakeOpenAIClient("Yanıt"),
            )

        self.assertFalse(
            AIRequestLog.objects.filter(
                company=self.company,
            ).exists()
        )


class AIKnowledgeModelTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.models import (
            AIKnowledgeChunk,
            AIKnowledgeDocument,
        )

        self.chunk_model = AIKnowledgeChunk
        self.document_model = AIKnowledgeDocument

        self.company = Company.objects.create(
            name="AI Knowledge Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="knowledge.test.user",
            email="knowledge.test@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

    def test_knowledge_document_has_pending_default_status(self):
        document = self.document_model.objects.create(
            company=self.company,
            created_by=self.user,
            document_type=(
                self.document_model
                .DocumentType
                .CANDIDATE_RESUME
            ),
            source_type=(
                self.document_model
                .SourceType
                .ERP_RECORD
            ),
            title="Demo Aday CV",
            source_reference="candidate:demo-id",
            content_text="Python ve Django deneyimi.",
        )

        self.assertEqual(
            document.status,
            self.document_model.Status.PENDING,
        )
        self.assertEqual(
            document.metadata,
            {},
        )

    def test_document_can_have_ordered_chunks(self):
        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.ERP_HELP
            ),
            title="ERP Kullanım Rehberi",
        )

        second = self.chunk_model.objects.create(
            document=document,
            company=self.company,
            chunk_index=1,
            content="İkinci bilgi parçası.",
        )

        first = self.chunk_model.objects.create(
            document=document,
            company=self.company,
            chunk_index=0,
            content="Birinci bilgi parçası.",
        )

        self.assertEqual(
            list(document.chunks.all()),
            [
                first,
                second,
            ],
        )

    def test_chunk_can_store_1536_dimension_embedding(self):
        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model
                .DocumentType
                .JOB_REQUISITION
            ),
            title="Backend Developer İlanı",
        )

        chunk = self.chunk_model.objects.create(
            document=document,
            company=self.company,
            chunk_index=0,
            content="Python ve Django deneyimi gereklidir.",
            embedding_model="text-embedding-3-small",
            embedding=[0.0] * 1536,
        )

        chunk.refresh_from_db()

        self.assertEqual(
            len(chunk.embedding),
            1536,
        )
        self.assertEqual(
            chunk.embedding_model,
            "text-embedding-3-small",
        )

    def test_duplicate_chunk_index_is_rejected(self):
        from django.db import IntegrityError

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.HR_POLICY
            ),
            title="İK Politikası",
        )

        self.chunk_model.objects.create(
            document=document,
            company=self.company,
            chunk_index=0,
            content="İlk parça.",
        )

        with self.assertRaises(IntegrityError):
            self.chunk_model.objects.bulk_create(
                [
                    self.chunk_model(
                        document=document,
                        company=self.company,
                        chunk_index=0,
                        content="Tekrar eden parça.",
                    )
                ]
            )

    def test_cross_company_chunk_is_rejected(self):
        from django.core.exceptions import ValidationError

        other_company = Company.objects.create(
            name="Başka Knowledge Şirketi",
        )

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.OTHER
            ),
            title="Şirket Dokümanı",
        )

        with self.assertRaises(ValidationError):
            self.chunk_model.objects.create(
                document=document,
                company=other_company,
                chunk_index=0,
                content="Yanlış şirkete ait parça.",
            )

    def test_empty_chunk_content_is_rejected(self):
        from django.core.exceptions import ValidationError

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.OTHER
            ),
            title="Boş İçerik Testi",
        )

        with self.assertRaises(ValidationError):
            self.chunk_model.objects.create(
                document=document,
                company=self.company,
                chunk_index=0,
                content="   ",
            )


class AIHashingAndChunkingTestCase(TestCase):
    def test_hash_ignores_redundant_whitespace(self):
        from apps.ai_core.utils import sha256_text

        self.assertEqual(
            sha256_text("Python   ve\nDjango"),
            sha256_text("Python ve Django"),
        )

    def test_chunk_text_returns_ordered_overlapping_chunks(self):
        from apps.ai_core.utils import chunk_text

        content = " ".join(
            f"kelime-{index}"
            for index in range(300)
        )

        chunks = chunk_text(
            content,
            chunk_size=80,
            overlap=20,
        )

        self.assertGreater(len(chunks), 1)

        self.assertEqual(
            [chunk.index for chunk in chunks],
            list(range(len(chunks))),
        )

        self.assertTrue(
            all(chunk.token_count <= 80 for chunk in chunks)
        )

        self.assertTrue(
            all(len(chunk.content_hash) == 64 for chunk in chunks)
        )

    def test_empty_text_returns_no_chunks(self):
        from apps.ai_core.utils import chunk_text

        self.assertEqual(
            chunk_text("   "),
            [],
        )

    def test_invalid_overlap_is_rejected(self):
        from apps.ai_core.utils import chunk_text

        with self.assertRaises(ValueError):
            chunk_text(
                "Demo içerik",
                chunk_size=100,
                overlap=100,
            )


class FakeEmbeddingUsage:
    prompt_tokens = 24
    total_tokens = 24


class FakeEmbeddingItem:
    def __init__(self, index, embedding):
        self.index = index
        self.embedding = embedding


class FakeEmbeddingResponse:
    id = "emb_response_test"
    usage = FakeEmbeddingUsage()

    def __init__(self, embeddings):
        self.data = [
            FakeEmbeddingItem(index, embedding)
            for index, embedding in enumerate(embeddings)
        ]


class FakeEmbeddingsAPI:
    def __init__(self, embeddings):
        self.embeddings = embeddings
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        return FakeEmbeddingResponse(
            self.embeddings
        )


class FakeEmbeddingClient:
    def __init__(self, embeddings):
        self.embeddings = FakeEmbeddingsAPI(
            embeddings
        )


class AIEmbeddingProviderTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.services import OpenAIProvider

        self.provider_class = OpenAIProvider

        self.company = Company.objects.create(
            name="Embedding Provider Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="embedding.test.user",
            email="embedding.test@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

    def test_generate_embeddings_returns_vectors_and_log(self):
        client = FakeEmbeddingClient(
            [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ]
        )

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="ai_core",
            feature="knowledge_embedding",
            client=client,
        )

        result = provider.generate_embeddings(
            texts=[
                "Python ve Django",
                "Finansal raporlama",
            ],
            dimensions=3,
        )

        self.assertEqual(result.count, 2)
        self.assertEqual(result.dimensions, 3)
        self.assertEqual(
            result.embeddings[0],
            (0.1, 0.2, 0.3),
        )
        self.assertEqual(
            result.usage.total_tokens,
            24,
        )

        log = AIRequestLog.objects.get(
            company=self.company,
            feature="knowledge_embedding",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.COMPLETED,
        )
        self.assertEqual(
            log.request_type,
            AIRequestLog.RequestType.EMBEDDING,
        )
        self.assertEqual(
            log.response_metadata["embedding_count"],
            2,
        )
        self.assertEqual(
            log.response_metadata["dimensions"],
            3,
        )

        call = client.embeddings.calls[0]

        self.assertEqual(
            call["model"],
            "text-embedding-3-small",
        )
        self.assertEqual(
            call["dimensions"],
            3,
        )

    def test_empty_embedding_input_is_rejected_without_log(self):
        from apps.ai_core.services import AIConfigurationError

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="ai_core",
            feature="empty_embedding",
            client=FakeEmbeddingClient([]),
        )

        with self.assertRaises(AIConfigurationError):
            provider.generate_embeddings(
                texts=[],
            )

        self.assertFalse(
            AIRequestLog.objects.filter(
                feature="empty_embedding",
            ).exists()
        )

    def test_invalid_embedding_dimension_is_logged_as_failed(self):
        from apps.ai_core.services import AIProviderError

        provider = self.provider_class(
            company=self.company,
            requested_by=self.user,
            module="ai_core",
            feature="invalid_embedding",
            client=FakeEmbeddingClient(
                [
                    [0.1, 0.2],
                ]
            ),
        )

        with self.assertRaises(AIProviderError):
            provider.generate_embeddings(
                texts=["Demo"],
                dimensions=3,
            )

        log = AIRequestLog.objects.get(
            feature="invalid_embedding",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.FAILED,
        )
        self.assertEqual(
            log.error_type,
            "AIProviderError",
        )


class FakeKnowledgeEmbeddingProvider:
    call_count = 0

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def generate_embeddings(
        self,
        *,
        texts,
        model=None,
        dimensions=1536,
    ):
        from apps.ai_core.services import (
            AIEmbeddingResult,
            AIUsage,
        )

        type(self).call_count += 1

        vectors = []

        for index, _ in enumerate(texts):
            vector = [0.0] * dimensions
            vector[index % dimensions] = 1.0
            vectors.append(tuple(vector))

        return AIEmbeddingResult(
            embeddings=tuple(vectors),
            model=model or "text-embedding-3-small",
            usage=AIUsage(
                input_tokens=10,
                total_tokens=10,
            ),
        )


class FixedQueryEmbeddingProvider:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def generate_embeddings(
        self,
        *,
        texts,
        model=None,
        dimensions=1536,
    ):
        from apps.ai_core.services import (
            AIEmbeddingResult,
            AIUsage,
        )

        vector = [0.0] * dimensions
        vector[0] = 1.0

        return AIEmbeddingResult(
            embeddings=(tuple(vector),),
            model=model or "text-embedding-3-small",
            usage=AIUsage(),
        )


class AIKnowledgeIndexingTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.models import (
            AIKnowledgeDocument,
        )

        self.document_model = AIKnowledgeDocument

        self.company = Company.objects.create(
            name="Knowledge Index Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="knowledge.index.user",
            email="knowledge.index@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        FakeKnowledgeEmbeddingProvider.call_count = 0

    def test_document_is_chunked_embedded_and_indexed(self):
        from apps.ai_core.services import (
            index_knowledge_document,
        )

        document = self.document_model.objects.create(
            company=self.company,
            created_by=self.user,
            document_type=(
                self.document_model.DocumentType.HR_POLICY
            ),
            source_type=(
                self.document_model.SourceType.MANUAL
            ),
            title="İK Yetkinlik Politikası",
            content_text=(
                "Python ve Django deneyimi önemlidir. "
                * 500
            ),
        )

        result = index_knowledge_document(
            document=document,
            requested_by=self.user,
            provider_class=FakeKnowledgeEmbeddingProvider,
        )

        document.refresh_from_db()

        self.assertEqual(
            document.status,
            self.document_model.Status.INDEXED,
        )
        self.assertTrue(document.content_hash)
        self.assertIsNotNone(document.indexed_at)
        self.assertGreater(result.chunk_count, 1)
        self.assertEqual(
            document.chunks.count(),
            result.chunk_count,
        )

        first_chunk = document.chunks.first()

        self.assertEqual(
            len(first_chunk.embedding),
            1536,
        )
        self.assertEqual(
            first_chunk.embedding_model,
            "text-embedding-3-small",
        )

    def test_unchanged_document_reuses_existing_index(self):
        from apps.ai_core.services import (
            index_knowledge_document,
        )

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.ERP_HELP
            ),
            title="ERP Yardım",
            content_text="Satış siparişi ve fatura yönetimi.",
        )

        first = index_knowledge_document(
            document=document,
            provider_class=FakeKnowledgeEmbeddingProvider,
        )

        document.refresh_from_db()

        second = index_knowledge_document(
            document=document,
            provider_class=FakeKnowledgeEmbeddingProvider,
        )

        self.assertFalse(first.reused_existing_index)
        self.assertTrue(second.reused_existing_index)
        self.assertEqual(
            FakeKnowledgeEmbeddingProvider.call_count,
            1,
        )

    def test_content_change_replaces_existing_chunks(self):
        from apps.ai_core.services import (
            index_knowledge_document,
        )

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.OTHER
            ),
            title="Değişen Doküman",
            content_text="İlk içerik.",
        )

        index_knowledge_document(
            document=document,
            provider_class=FakeKnowledgeEmbeddingProvider,
        )

        first_hash = document.chunks.get().content_hash

        document.content_text = (
            "Tamamen güncellenmiş ikinci içerik."
        )
        document.save(
            update_fields=[
                "content_text",
                "updated_at",
            ]
        )

        index_knowledge_document(
            document=document,
            provider_class=FakeKnowledgeEmbeddingProvider,
        )

        document.refresh_from_db()

        self.assertEqual(document.chunks.count(), 1)
        self.assertNotEqual(
            document.chunks.get().content_hash,
            first_hash,
        )
        self.assertEqual(
            FakeKnowledgeEmbeddingProvider.call_count,
            2,
        )

    def test_empty_document_is_rejected(self):
        from apps.ai_core.services import (
            index_knowledge_document,
        )

        document = self.document_model.objects.create(
            company=self.company,
            document_type=(
                self.document_model.DocumentType.OTHER
            ),
            title="Boş Doküman",
            content_text="",
        )

        with self.assertRaises(ValueError):
            index_knowledge_document(
                document=document,
                provider_class=FakeKnowledgeEmbeddingProvider,
            )


class AIKnowledgeSemanticSearchTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.models import (
            AIKnowledgeChunk,
            AIKnowledgeDocument,
        )

        self.chunk_model = AIKnowledgeChunk
        self.document_model = AIKnowledgeDocument

        self.company = Company.objects.create(
            name="Semantic Search Test Şirketi",
        )

        self.other_company = Company.objects.create(
            name="Semantic Search Diğer Şirket",
        )

    def create_indexed_document(
        self,
        *,
        company,
        title,
        content,
        vector,
        document_type=None,
    ):
        document = self.document_model.objects.create(
            company=company,
            document_type=(
                document_type
                or self.document_model.DocumentType.OTHER
            ),
            title=title,
            content_text=content,
            content_hash="a" * 64,
            status=self.document_model.Status.INDEXED,
            indexed_at=timezone.now(),
        )

        self.chunk_model.objects.create(
            document=document,
            company=company,
            chunk_index=0,
            content=content,
            content_hash="b" * 64,
            token_count=10,
            embedding_model="text-embedding-3-small",
            embedding=vector,
            embedded_at=timezone.now(),
        )

        return document

    def test_semantic_search_orders_by_cosine_distance(self):
        from apps.ai_core.services import semantic_search

        close_vector = [0.0] * 1536
        close_vector[0] = 1.0

        distant_vector = [0.0] * 1536
        distant_vector[1] = 1.0

        close_document = self.create_indexed_document(
            company=self.company,
            title="Python Backend Rehberi",
            content="Python ve Django backend geliştirme.",
            vector=close_vector,
        )

        self.create_indexed_document(
            company=self.company,
            title="Finans Rehberi",
            content="Bütçe ve nakit akışı yönetimi.",
            vector=distant_vector,
        )

        results = semantic_search(
            company=self.company,
            query="Backend geliştirme",
            limit=2,
            provider_class=FixedQueryEmbeddingProvider,
        )

        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0].document,
            close_document,
        )
        self.assertGreater(
            results[0].similarity,
            results[1].similarity,
        )

    def test_semantic_search_is_company_isolated(self):
        from apps.ai_core.services import semantic_search

        matching_vector = [0.0] * 1536
        matching_vector[0] = 1.0

        own_document = self.create_indexed_document(
            company=self.company,
            title="Şirket İçi Belge",
            content="Şirket içi bilgi.",
            vector=matching_vector,
        )

        self.create_indexed_document(
            company=self.other_company,
            title="Başka Şirket Belgesi",
            content="Başka şirkete ait bilgi.",
            vector=matching_vector,
        )

        results = semantic_search(
            company=self.company,
            query="Şirket bilgisi",
            limit=5,
            provider_class=FixedQueryEmbeddingProvider,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].document,
            own_document,
        )

    def test_semantic_search_can_filter_document_type(self):
        from apps.ai_core.services import semantic_search

        vector = [0.0] * 1536
        vector[0] = 1.0

        resume = self.create_indexed_document(
            company=self.company,
            title="Aday CV",
            content="Python geliştirici öz geçmişi.",
            vector=vector,
            document_type=(
                self.document_model
                .DocumentType
                .CANDIDATE_RESUME
            ),
        )

        self.create_indexed_document(
            company=self.company,
            title="Finans Politikası",
            content="Finans politikası.",
            vector=vector,
            document_type=(
                self.document_model
                .DocumentType
                .FINANCE_POLICY
            ),
        )

        results = semantic_search(
            company=self.company,
            query="Python geliştirici",
            document_types=[
                self.document_model
                .DocumentType
                .CANDIDATE_RESUME
            ],
            limit=5,
            provider_class=FixedQueryEmbeddingProvider,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].document,
            resume,
        )


class FakeLangChainStructuredResult:
    def __init__(self, data):
        self.data = data


class FakeLangChainProvider:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def generate_structured(self, **kwargs):
        type(self).calls.append(kwargs)

        return FakeLangChainStructuredResult(
            {
                "overall_score": 88,
                "strengths": [
                    "Backend geliştirme deneyimi güçlü.",
                ],
                "risks": [
                    "Bulut deneyimi doğrulanmalıdır.",
                ],
                "matched_skills": [
                    "python",
                    "django",
                ],
                "missing_skills": [
                    "aws",
                ],
                "recommendation": "strong_interview",
                "summary": (
                    "Aday teknik görüşme için güçlüdür."
                ),
            }
        )


class AILangChainOrchestrationTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.orchestration import (
            RecruitmentAssessmentChain,
        )

        self.chain_class = RecruitmentAssessmentChain

        self.company = Company.objects.create(
            name="LangChain Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="langchain.test.user",
            email="langchain.test@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        FakeLangChainProvider.calls = []

    def test_recruitment_chain_uses_prompt_and_provider(self):
        chain = self.chain_class(
            company=self.company,
            requested_by=self.user,
            provider_class=FakeLangChainProvider,
        )

        result = chain.invoke(
            candidate_context={
                "full_name": "Selin Test",
                "current_title": "Backend Developer",
            },
            requisition_context={
                "title": "Kıdemli Backend Developer",
            },
            deterministic_context={
                "overall_score": 88,
            },
            rag_context={
                "source_count": 1,
                "sources": [
                    {
                        "chunk_id": "chunk-test-1",
                        "content": (
                            "Python ve Django deneyimi."
                        ),
                    }
                ],
            },
            schema_name="candidate_assessment",
            schema={
                "type": "object",
                "properties": {
                    "overall_score": {
                        "type": "integer",
                    },
                },
                "required": [
                    "overall_score",
                ],
                "additionalProperties": True,
            },
        )

        self.assertEqual(
            result.data["overall_score"],
            88,
        )
        self.assertEqual(result.source_count, 1)
        self.assertEqual(
            result.source_ids,
            ("chunk-test-1",),
        )

        self.assertEqual(
            len(FakeLangChainProvider.calls),
            1,
        )

        call = FakeLangChainProvider.calls[0]

        self.assertIn(
            "Selin Test",
            call["input_text"],
        )
        self.assertIn(
            "Kıdemli Backend Developer",
            call["input_text"],
        )
        self.assertIn(
            "Python ve Django",
            call["input_text"],
        )

    def test_prompt_contains_recruitment_safety_rules(self):
        from apps.ai_core.orchestration import (
            RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT,
        )

        self.assertIn(
            "Deterministik puanı değiştirme",
            RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Hassas kişisel özelliklere",
            RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT,
        )
        self.assertIn(
            "Nihai işe alım kararı verme",
            RECRUITMENT_ASSESSMENT_SYSTEM_PROMPT,
        )


class ERPToolRegistryTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import ERPToolRegistry

        self.registry = ERPToolRegistry()

    @staticmethod
    def demo_handler(*, context, customer_id):
        return {
            "company_id": str(context.company.id),
            "customer_id": customer_id,
        }

    def build_definition(
        self,
        *,
        name="get_customer_summary",
        module="crm",
        is_read_only=True,
    ):
        from apps.ai_core.tools import ERPToolDefinition

        return ERPToolDefinition(
            name=name,
            description="Müşteri özetini getirir.",
            module=module,
            input_schema={
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                    },
                },
                "required": [
                    "customer_id",
                ],
                "additionalProperties": False,
            },
            handler=self.demo_handler,
            is_read_only=is_read_only,
        )

    def test_registry_registers_and_exports_tool(self):
        definition = self.build_definition()

        self.registry.register(definition)

        self.assertEqual(
            self.registry.get(definition.name),
            definition,
        )

        tools = self.registry.as_openai_tools()

        self.assertEqual(len(tools), 1)
        self.assertEqual(
            tools[0]["name"],
            "get_customer_summary",
        )
        self.assertTrue(tools[0]["strict"])

    def test_duplicate_tool_name_is_rejected(self):
        from apps.ai_core.tools import (
            ERPToolValidationError,
        )

        definition = self.build_definition()

        self.registry.register(definition)

        with self.assertRaises(
            ERPToolValidationError
        ):
            self.registry.register(definition)

    def test_registry_can_filter_by_module(self):
        self.registry.register(
            self.build_definition(
                name="get_customer_summary",
                module="crm",
            )
        )
        self.registry.register(
            self.build_definition(
                name="get_stock_level",
                module="inventory",
            )
        )

        definitions = self.registry.list_tools(
            modules=["inventory"],
        )

        self.assertEqual(len(definitions), 1)
        self.assertEqual(
            definitions[0].name,
            "get_stock_level",
        )


class ERPToolExecutorTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolDefinition,
            ERPToolExecutionContext,
            ERPToolExecutor,
            ERPToolRegistry,
        )

        self.context_class = ERPToolExecutionContext

        self.company = Company.objects.create(
            name="ERP Tool Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="erp.tool.user",
            email="erp.tool@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.registry = ERPToolRegistry()
        self.executor = ERPToolExecutor(
            registry=self.registry,
        )

        def stock_handler(
            *,
            context,
            sku,
        ):
            return {
                "company_id": str(context.company.id),
                "sku": sku,
                "available_quantity": "120.00",
            }

        self.registry.register(
            ERPToolDefinition(
                name="get_stock_level",
                description=(
                    "Şirkete ait ürünün stok seviyesini getirir."
                ),
                module="inventory",
                input_schema={
                    "type": "object",
                    "properties": {
                        "sku": {
                            "type": "string",
                        },
                    },
                    "required": [
                        "sku",
                    ],
                    "additionalProperties": False,
                },
                handler=stock_handler,
                is_read_only=True,
            )
        )

        self.context = self.context_class(
            company=self.company,
            user=self.user,
            allowed_modules=frozenset(
                {
                    "inventory",
                }
            ),
        )

    def test_executor_runs_tool_and_creates_log(self):
        result = self.executor.execute(
            tool_name="get_stock_level",
            arguments={
                "sku": "COS-1009",
            },
            context=self.context,
        )

        self.assertEqual(
            result.output["sku"],
            "COS-1009",
        )
        self.assertEqual(
            result.output["company_id"],
            str(self.company.id),
        )

        log = AIRequestLog.objects.get(
            feature="get_stock_level",
        )

        self.assertEqual(
            log.status,
            AIRequestLog.Status.COMPLETED,
        )
        self.assertEqual(
            log.request_type,
            AIRequestLog.RequestType.TOOL_CALL,
        )
        self.assertEqual(
            log.request_metadata["argument_names"],
            ["sku"],
        )

    def test_executor_rejects_module_without_access(self):
        from apps.ai_core.tools import (
            ERPToolPermissionError,
        )

        context = self.context_class(
            company=self.company,
            user=self.user,
            allowed_modules=frozenset(),
        )

        with self.assertRaises(
            ERPToolPermissionError
        ):
            self.executor.execute(
                tool_name="get_stock_level",
                arguments={
                    "sku": "COS-1009",
                },
                context=context,
            )

        self.assertFalse(
            AIRequestLog.objects.filter(
                feature="get_stock_level",
            ).exists()
        )

    def test_executor_validates_required_arguments(self):
        from apps.ai_core.tools import (
            ERPToolValidationError,
        )

        with self.assertRaises(
            ERPToolValidationError
        ):
            self.executor.execute(
                tool_name="get_stock_level",
                arguments={},
                context=self.context,
            )

    def test_write_tool_requires_explicit_permission(self):
        from apps.ai_core.tools import (
            ERPToolDefinition,
            ERPToolPermissionError,
        )

        self.registry.register(
            ERPToolDefinition(
                name="create_stock_adjustment",
                description="Stok düzeltme kaydı oluşturur.",
                module="inventory",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                handler=lambda *, context: {
                    "created": True,
                },
                is_read_only=False,
            )
        )

        with self.assertRaises(
            ERPToolPermissionError
        ):
            self.executor.execute(
                tool_name="create_stock_adjustment",
                arguments={},
                context=self.context,
            )


class ERPInventoryToolDefinitionTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )

        self.context_class = ERPToolExecutionContext

        self.company = Company.objects.create(
            name="Inventory Tool Test Şirketi",
        )

        from apps.organizations.models import Branch
        from apps.inventory.models import (
            InventoryLot,
            Product,
            Warehouse,
        )

        self.product = Product.objects.create(
            company=self.company,
            sku="SERUM-001",
            name="Anti Aging Serum",
            unit="adet",
            reorder_level=Decimal("20.00"),
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="INV-TOOL-HQ",
            name="Inventory Tool Merkez",
        )

        self.warehouse = Warehouse.objects.create(
            company=self.company,
            branch=self.branch,
            code="INV-MAIN",
            name="Ana Depo",
        )

        InventoryLot.objects.create(
            product=self.product,
            warehouse=self.warehouse,
            lot_number="LOT-001",
            quantity_on_hand=Decimal("100.00"),
            quantity_reserved=Decimal("25.00"),
        )

        self.context = self.context_class(
            company=self.company,
            allowed_modules=frozenset(
                {
                    "inventory",
                }
            ),
        )

    def test_stock_tool_returns_company_stock_summary(self):
        from apps.ai_core.tools.definitions.inventory import (
            get_stock_level,
        )

        result = get_stock_level(
            context=self.context,
            sku="SERUM-001",
        )

        self.assertTrue(result["found"])
        self.assertEqual(
            result["product_name"],
            "Anti Aging Serum",
        )
        self.assertEqual(
            result["quantity_on_hand"],
            "100.00",
        )
        self.assertEqual(
            result["quantity_reserved"],
            "25.00",
        )
        self.assertEqual(
            result["available_quantity"],
            "75.00",
        )
        self.assertFalse(
            result["below_reorder_level"]
        )

    def test_stock_tool_is_company_isolated(self):
        from apps.ai_core.tools.definitions.inventory import (
            get_stock_level,
        )

        other_company = Company.objects.create(
            name="Başka Inventory Tool Şirketi",
        )

        context = self.context_class(
            company=other_company,
            allowed_modules=frozenset(
                {
                    "inventory",
                }
            ),
        )

        result = get_stock_level(
            context=context,
            sku="SERUM-001",
        )

        self.assertFalse(result["found"])


class ERPHRToolDefinitionTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )
        from apps.organizations.models import (
            Branch,
            Department,
        )
        from apps.hr.models import (
            Candidate,
            Employee,
            JobApplication,
            JobRequisition,
            Position,
        )

        self.context_class = ERPToolExecutionContext

        self.company = Company.objects.create(
            name="HR Tool Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="HR-TOOL-HQ",
            name="HR Tool Merkez",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            code="HR-TOOL-TECH",
            name="Bilgi Teknolojileri",
        )

        self.position = Position.objects.create(
            company=self.company,
            department=self.department,
            code="HR-TOOL-BE",
            title="Backend Developer",
        )

        self.manager = Employee.objects.create(
            company=self.company,
            employee_number="HR-TOOL-001",
            first_name="Mehmet",
            last_name="Yönetici",
            work_email="manager.hrtool@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.recruiter = Employee.objects.create(
            company=self.company,
            employee_number="HR-TOOL-002",
            first_name="Ayşe",
            last_name="Recruiter",
            work_email="recruiter.hrtool@example.com",
            hire_date=date(2024, 1, 1),
        )

        self.requisition = JobRequisition.objects.create(
            company=self.company,
            department=self.department,
            position=self.position,
            requisition_number="REQ-TOOL-001",
            title="Backend Developer",
            description="Backend geliştirme.",
            requirements="Python ve Django.",
            hiring_manager=self.manager,
            recruiter=self.recruiter,
            status=JobRequisition.Status.OPEN,
            opened_at=timezone.now(),
            headcount=2,
        )

        self.candidate = Candidate.objects.create(
            company=self.company,
            first_name="Selin",
            last_name="Araç",
            email="selin.tool@example.com",
        )

        JobApplication.objects.create(
            company=self.company,
            requisition=self.requisition,
            candidate=self.candidate,
            assigned_recruiter=self.recruiter,
            stage=JobApplication.Stage.INTERVIEW,
        )

        self.context = self.context_class(
            company=self.company,
            allowed_modules=frozenset(
                {
                    "hr",
                }
            ),
        )

    def test_hr_tool_returns_pipeline_summary(self):
        from apps.ai_core.tools.definitions.hr import (
            get_recruitment_pipeline_summary,
        )

        result = get_recruitment_pipeline_summary(
            context=self.context,
        )

        self.assertTrue(result["found"])
        self.assertEqual(
            result["open_requisitions"],
            1,
        )
        self.assertEqual(
            result["active_applications"],
            1,
        )
        self.assertEqual(
            result["stage_counts"]["interview"],
            1,
        )

    def test_hr_tool_can_filter_requisition_number(self):
        from apps.ai_core.tools.definitions.hr import (
            get_recruitment_pipeline_summary,
        )

        result = get_recruitment_pipeline_summary(
            context=self.context,
            requisition_number="REQ-TOOL-001",
        )

        self.assertTrue(result["found"])
        self.assertEqual(
            result["scope"],
            "requisition",
        )
        self.assertEqual(
            result["requisition"]["title"],
            "Backend Developer",
        )


class CoreERPToolRegistrationTestCase(TestCase):
    def test_core_definitions_are_registered_once(self):
        from apps.ai_core.tools import ERPToolRegistry
        from apps.ai_core.tools.definitions import (
            register_core_erp_tools,
        )

        registry = ERPToolRegistry()

        register_core_erp_tools(
            registry=registry,
        )
        register_core_erp_tools(
            registry=registry,
        )

        names = {
            definition.name
            for definition in registry.list_tools()
        }

        self.assertEqual(
            names,
            {
                "get_customer_summary",
                "get_customer_balance",
                "get_open_invoices",
                "get_stock_level",
                "get_critical_stock_products",
                "get_recruitment_pipeline_summary",
                "get_active_job_applications",
            },
        )


class ERPCRMToolDefinitionTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )
        from apps.crm.models import Customer, Opportunity

        self.context_class = ERPToolExecutionContext

        self.company = Company.objects.create(
            name="CRM Tool Test Şirketi",
        )

        self.customer = Customer.objects.create(
            company=self.company,
            name="Luméa Cosmetics A.Ş.",
            customer_type=Customer.CustomerType.CORPORATE,
            status=Customer.Status.ACTIVE,
            email="finance@lumea.example",
            phone="+90 312 000 00 00",
            city="Ankara",
        )

        Opportunity.objects.create(
            company=self.company,
            customer=self.customer,
            title="Anti Aging Serum Satışı",
            stage=Opportunity.Stage.NEGOTIATION,
            expected_amount=Decimal("25000.00"),
        )

        self.context = self.context_class(
            company=self.company,
            allowed_modules=frozenset({"crm"}),
        )

    def test_customer_summary_returns_crm_data(self):
        from apps.ai_core.tools.definitions.crm import (
            get_customer_summary,
        )

        result = get_customer_summary(
            context=self.context,
            customer_name="Luméa Cosmetics A.Ş.",
        )

        self.assertTrue(result["found"])
        self.assertEqual(
            result["customer"]["name"],
            "Luméa Cosmetics A.Ş.",
        )
        self.assertEqual(
            result["crm"]["active_opportunities"],
            1,
        )
        self.assertEqual(
            result["crm"]["total_expected_amount"],
            "25000.00",
        )

    def test_customer_summary_is_company_isolated(self):
        from apps.ai_core.tools.definitions.crm import (
            get_customer_summary,
        )

        other_company = Company.objects.create(
            name="Başka CRM Tool Şirketi",
        )

        context = self.context_class(
            company=other_company,
            allowed_modules=frozenset({"crm"}),
        )

        result = get_customer_summary(
            context=context,
            customer_id=str(self.customer.id),
        )

        self.assertFalse(result["found"])


class ERPFinanceToolDefinitionTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )
        from apps.crm.models import Customer
        from apps.finance.models import (
            CustomerAccount,
            CustomerAccountTransaction,
        )

        self.context_class = ERPToolExecutionContext
        self.transaction_model = (
            CustomerAccountTransaction
        )

        self.company = Company.objects.create(
            name="Finance Tool Test Şirketi",
        )

        self.customer = Customer.objects.create(
            company=self.company,
            name="Nova Kozmetik A.Ş.",
            status=Customer.Status.ACTIVE,
        )

        self.account = CustomerAccount.objects.create(
            company=self.company,
            customer=self.customer,
            currency="TRY",
        )

        CustomerAccountTransaction.objects.create(
            account=self.account,
            company=self.company,
            direction=(
                CustomerAccountTransaction
                .Direction
                .DEBIT
            ),
            transaction_type=(
                CustomerAccountTransaction
                .TransactionType
                .SALES_INVOICE
            ),
            amount=Decimal("20000.00"),
            currency="TRY",
            description="Satış faturası",
        )

        CustomerAccountTransaction.objects.create(
            account=self.account,
            company=self.company,
            direction=(
                CustomerAccountTransaction
                .Direction
                .CREDIT
            ),
            transaction_type=(
                CustomerAccountTransaction
                .TransactionType
                .COLLECTION
            ),
            amount=Decimal("7500.00"),
            currency="TRY",
            description="Kısmi tahsilat",
        )

        self.context = self.context_class(
            company=self.company,
            allowed_modules=frozenset({"finance"}),
        )

    def test_customer_balance_returns_ledger_balance(self):
        from apps.ai_core.tools.definitions.finance import (
            get_customer_balance,
        )

        result = get_customer_balance(
            context=self.context,
            customer_id=str(self.customer.id),
            currency="TRY",
        )

        self.assertTrue(result["found"])
        self.assertTrue(result["has_account"])
        self.assertEqual(
            result["debit_total"],
            "20000.00",
        )
        self.assertEqual(
            result["credit_total"],
            "7500.00",
        )
        self.assertEqual(
            result["balance"],
            "12500.00",
        )
        self.assertEqual(
            result["balance_position"],
            "customer_owes_company",
        )

    def test_customer_balance_is_company_isolated(self):
        from apps.ai_core.tools.definitions.finance import (
            get_customer_balance,
        )

        other_company = Company.objects.create(
            name="Başka Finance Tool Şirketi",
        )

        context = self.context_class(
            company=other_company,
            allowed_modules=frozenset({"finance"}),
        )

        result = get_customer_balance(
            context=context,
            customer_id=str(self.customer.id),
        )

        self.assertFalse(result["found"])


class ERPOpenInvoiceToolDefinitionTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )
        from apps.crm.models import Customer
        from apps.finance.models import (
            CustomerAccount,
            CustomerAccountTransaction,
        )
        from apps.sales.models import (
            Invoice,
            SalesOrder,
            SalesQuote,
        )

        self.invoice_model = Invoice
        self.quote_model = SalesQuote
        self.order_model = SalesOrder
        self.transaction_model = (
            CustomerAccountTransaction
        )

        self.company = Company.objects.create(
            name="Open Invoice Tool Test Şirketi",
        )

        self.customer = Customer.objects.create(
            company=self.company,
            name="Aurora Kozmetik A.Ş.",
            status=Customer.Status.ACTIVE,
        )

        self.account = CustomerAccount.objects.create(
            company=self.company,
            customer=self.customer,
            currency="TRY",
        )

        CustomerAccountTransaction.objects.create(
            account=self.account,
            company=self.company,
            direction=(
                CustomerAccountTransaction
                .Direction
                .DEBIT
            ),
            transaction_type=(
                CustomerAccountTransaction
                .TransactionType
                .SALES_INVOICE
            ),
            amount=Decimal("15000.00"),
            currency="TRY",
            description="Test satış faturası borcu",
        )

        self.context = ERPToolExecutionContext(
            company=self.company,
            allowed_modules=frozenset({"finance"}),
        )

    def create_invoice(
        self,
        *,
        title,
        status,
        total_amount,
        due_date=None,
        customer=None,
        company=None,
    ):
        company = company or self.company
        customer = customer or self.customer

        quote = self.quote_model.objects.create(
            company=company,
            customer=customer,
            title=title,
            status=self.quote_model.Status.ACCEPTED,
            total_amount=total_amount,
        )

        order = self.order_model.objects.create(
            company=company,
            customer=customer,
            quote=quote,
            total_amount=total_amount,
        )

        return self.invoice_model.objects.create(
            sales_order=order,
            company=company,
            customer=customer,
            status=status,
            currency="TRY",
            due_date=due_date,
            seller_name="Glauria Demo A.Ş.",
            customer_name=customer.name,
            total_amount=total_amount,
        )

    def test_open_invoice_tool_lists_open_statuses(self):
        from apps.ai_core.tools.definitions.finance import (
            get_open_invoices,
        )

        self.create_invoice(
            title="Kesilmiş Fatura",
            status=self.invoice_model.Status.ISSUED,
            total_amount=Decimal("10000.00"),
            due_date=timezone.localdate()
            + timedelta(days=10),
        )

        self.create_invoice(
            title="Kısmi Ödenmiş Fatura",
            status=(
                self.invoice_model.Status.PARTIALLY_PAID
            ),
            total_amount=Decimal("5000.00"),
            due_date=timezone.localdate()
            + timedelta(days=5),
        )

        result = get_open_invoices(
            context=self.context,
            customer_id=str(self.customer.id),
        )

        self.assertTrue(result["found"])
        self.assertEqual(
            result["open_invoice_count"],
            2,
        )
        self.assertEqual(
            result["recorded_open_invoice_amount"],
            "15000.00",
        )

    def test_paid_cancelled_and_draft_invoices_are_excluded(self):
        from apps.ai_core.tools.definitions.finance import (
            get_open_invoices,
        )

        for status in [
            self.invoice_model.Status.PAID,
            self.invoice_model.Status.CANCELLED,
            self.invoice_model.Status.DRAFT,
        ]:
            self.create_invoice(
                title=f"Kapalı Fatura {status}",
                status=status,
                total_amount=Decimal("1000.00"),
            )

        result = get_open_invoices(
            context=self.context,
            customer_name=self.customer.name,
        )

        self.assertEqual(
            result["open_invoice_count"],
            0,
        )
        self.assertEqual(
            result["recorded_open_invoice_amount"],
            "0.00",
        )

    def test_overdue_invoice_contains_days_overdue(self):
        from apps.ai_core.tools.definitions.finance import (
            get_open_invoices,
        )

        invoice = self.create_invoice(
            title="Gecikmiş Fatura",
            status=self.invoice_model.Status.OVERDUE,
            total_amount=Decimal("4000.00"),
            due_date=timezone.localdate()
            - timedelta(days=7),
        )

        result = get_open_invoices(
            context=self.context,
            customer_id=str(self.customer.id),
        )

        row = result["invoices"][0]

        self.assertEqual(
            row["invoice_number"],
            invoice.invoice_number,
        )
        self.assertTrue(row["is_overdue"])
        self.assertEqual(row["days_overdue"], 7)
        self.assertEqual(
            result["recorded_overdue_invoice_amount"],
            "4000.00",
        )

    def test_remaining_amount_is_not_fabricated(self):
        from apps.ai_core.tools.definitions.finance import (
            get_open_invoices,
        )

        self.create_invoice(
            title="Kısmi Ödenmiş Fatura",
            status=(
                self.invoice_model.Status.PARTIALLY_PAID
            ),
            total_amount=Decimal("6000.00"),
        )

        result = get_open_invoices(
            context=self.context,
            customer_id=str(self.customer.id),
        )

        row = result["invoices"][0]

        self.assertIsNone(row["remaining_amount"])
        self.assertFalse(
            row["remaining_amount_is_exact"]
        )
        self.assertIn(
            "kesin kalan tutar",
            row["remaining_amount_note"],
        )

    def test_open_invoice_tool_is_company_isolated(self):
        from apps.ai_core.tools import (
            ERPToolExecutionContext,
        )
        from apps.ai_core.tools.definitions.finance import (
            get_open_invoices,
        )

        self.create_invoice(
            title="Şirket İçi Fatura",
            status=self.invoice_model.Status.ISSUED,
            total_amount=Decimal("3000.00"),
        )

        other_company = Company.objects.create(
            name="Başka Open Invoice Şirketi",
        )

        context = ERPToolExecutionContext(
            company=other_company,
            allowed_modules=frozenset({"finance"}),
        )

        result = get_open_invoices(
            context=context,
            customer_id=str(self.customer.id),
        )

        self.assertFalse(result["found"])


class FakeFunctionUsage:
    input_tokens = 20
    output_tokens = 10
    total_tokens = 30


class FakeFunctionCall:
    type = "function_call"

    def __init__(
        self,
        *,
        name,
        arguments,
        call_id,
    ):
        self.name = name
        self.arguments = arguments
        self.call_id = call_id


class FakeFunctionResponse:
    def __init__(
        self,
        *,
        response_id,
        output=None,
        output_text="",
    ):
        self.id = response_id
        self.output = output or []
        self.output_text = output_text
        self.usage = FakeFunctionUsage()


class FakeFunctionResponsesAPI:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        if not self.responses:
            raise AssertionError(
                "Beklenmeyen ek OpenAI çağrısı yapıldı."
            )

        return self.responses.pop(0)


class FakeFunctionClient:
    def __init__(self, responses):
        self.responses = FakeFunctionResponsesAPI(
            responses
        )


class FakeFunctionProvider:
    responses = []

    def __init__(self, **kwargs):
        from types import SimpleNamespace

        self.kwargs = kwargs
        self.configuration = SimpleNamespace(
            provider="openai",
            default_model="gpt-test",
        )
        self.client = FakeFunctionClient(
            list(type(self).responses)
        )


class AIFunctionCallingRuntimeTestCase(TestCase):
    def setUp(self):
        from apps.ai_core.tools import (
            ERPToolDefinition,
            ERPToolRegistry,
        )

        self.company = Company.objects.create(
            name="Function Calling Test Şirketi",
        )

        self.user = User.objects.create_user(
            username="function.calling.user",
            email="function.calling@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        self.registry = ERPToolRegistry()

        def demo_customer_tool(
            *,
            context,
            customer_name,
        ):
            return {
                "company_id": str(context.company.id),
                "customer_name": customer_name,
                "balance": "12500.00",
            }

        self.registry.register(
            ERPToolDefinition(
                name="get_demo_customer",
                description=(
                    "Demo müşteri bilgisini getirir."
                ),
                module="crm",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_name": {
                            "type": "string",
                        },
                    },
                    "required": [
                        "customer_name",
                    ],
                    "additionalProperties": False,
                },
                handler=demo_customer_tool,
                is_read_only=True,
            )
        )

    def build_runtime(
        self,
        *,
        responses,
        allowed_modules=None,
        max_tool_rounds=5,
    ):
        from apps.ai_core.orchestration import (
            FunctionCallingRuntime,
        )

        FakeFunctionProvider.responses = responses

        return FunctionCallingRuntime(
            company=self.company,
            requested_by=self.user,
            allowed_modules=(
                allowed_modules
                if allowed_modules is not None
                else {"crm"}
            ),
            registry=self.registry,
            provider_class=FakeFunctionProvider,
            max_tool_rounds=max_tool_rounds,
            register_core_tools=False,
        )

    def test_runtime_executes_tool_and_returns_final_answer(self):
        runtime = self.build_runtime(
            responses=[
                FakeFunctionResponse(
                    response_id="resp-1",
                    output=[
                        FakeFunctionCall(
                            name="get_demo_customer",
                            arguments=(
                                '{"customer_name": '
                                '"Nova Kozmetik"}'
                            ),
                            call_id="call-1",
                        )
                    ],
                ),
                FakeFunctionResponse(
                    response_id="resp-2",
                    output_text=(
                        "Nova Kozmetik'in bakiyesi "
                        "12.500 TRY'dir."
                    ),
                ),
            ]
        )

        result = runtime.invoke(
            user_message=(
                "Nova Kozmetik'in bakiyesi nedir?"
            )
        )

        self.assertEqual(result.tool_call_count, 1)
        self.assertEqual(result.round_count, 2)
        self.assertEqual(
            result.tool_calls[0].tool_name,
            "get_demo_customer",
        )
        self.assertIn(
            "12.500",
            result.content,
        )

        tool_log = AIRequestLog.objects.get(
            feature="get_demo_customer",
        )

        self.assertEqual(
            tool_log.status,
            AIRequestLog.Status.COMPLETED,
        )

        ai_logs = AIRequestLog.objects.filter(
            feature="erp_function_calling",
        )

        self.assertEqual(ai_logs.count(), 2)

    def test_runtime_can_return_direct_answer(self):
        runtime = self.build_runtime(
            responses=[
                FakeFunctionResponse(
                    response_id="resp-direct",
                    output_text=(
                        "Bu soru için ERP aracı gerekmiyor."
                    ),
                )
            ]
        )

        result = runtime.invoke(
            user_message="Merhaba",
        )

        self.assertEqual(result.tool_call_count, 0)
        self.assertEqual(result.round_count, 1)

    def test_runtime_rejects_invalid_json_arguments(self):
        from apps.ai_core.orchestration import (
            FunctionCallingArgumentError,
        )

        runtime = self.build_runtime(
            responses=[
                FakeFunctionResponse(
                    response_id="resp-invalid",
                    output=[
                        FakeFunctionCall(
                            name="get_demo_customer",
                            arguments="{invalid-json",
                            call_id="call-invalid",
                        )
                    ],
                )
            ]
        )

        with self.assertRaises(
            FunctionCallingArgumentError
        ):
            runtime.invoke(
                user_message="Müşteriyi getir.",
            )

    def test_runtime_rejects_inaccessible_module(self):
        from apps.ai_core.services import (
            AIConfigurationError,
        )

        with self.assertRaises(
            AIConfigurationError
        ):
            self.build_runtime(
                responses=[],
                allowed_modules={"finance"},
            ).invoke(
                user_message="Müşteriyi getir.",
            )

    def test_runtime_stops_at_maximum_round_limit(self):
        from apps.ai_core.orchestration import (
            FunctionCallingLimitError,
        )

        runtime = self.build_runtime(
            responses=[
                FakeFunctionResponse(
                    response_id="resp-loop",
                    output=[
                        FakeFunctionCall(
                            name="get_demo_customer",
                            arguments=(
                                '{"customer_name": "Nova"}'
                            ),
                            call_id="call-loop",
                        )
                    ],
                )
            ],
            max_tool_rounds=1,
        )

        with self.assertRaises(
            FunctionCallingLimitError
        ):
            runtime.invoke(
                user_message="Müşteriyi getir.",
            )


class FakeEnterpriseAssistantToolCall:
    def __init__(
        self,
        *,
        tool_name="get_customer_balance",
        latency_ms=8,
    ):
        self.tool_name = tool_name
        self.latency_ms = latency_ms


class FakeEnterpriseAssistantResult:
    content = "Nova Kozmetik'in cari bakiyesi 12.500 TRY'dir."
    tool_calls = (
        FakeEnterpriseAssistantToolCall(),
    )
    round_count = 2


class FakeEnterpriseAssistantRuntime:
    calls = []

    def __init__(self, **kwargs):
        type(self).calls.append(
            {
                "init": kwargs,
            }
        )

    def invoke(self, **kwargs):
        type(self).calls.append(
            {
                "invoke": kwargs,
            }
        )

        return FakeEnterpriseAssistantResult()


class EnterpriseAIAssistantViewTestCase(TestCase):
    def setUp(self):
        from apps.accounts.models import (
            OrganizationMembership,
        )
        from apps.organizations.models import (
            Branch,
            Department,
        )

        self.membership_model = (
            OrganizationMembership
        )

        self.company = Company.objects.create(
            name="Enterprise AI Test Şirketi",
        )

        self.branch = Branch.objects.create(
            company=self.company,
            code="AI-HQ",
            name="AI Genel Merkez",
        )

        self.department = Department.objects.create(
            branch=self.branch,
            code="AI-DEPT",
            name="Dijital Dönüşüm",
        )

        self.user = User.objects.create_user(
            username="enterprise.ai.user",
            email="enterprise.ai@example.com",
            password="test-password",
            user_type=User.UserType.INTERNAL,
        )

        FakeEnterpriseAssistantRuntime.calls = []

    def create_membership(
        self,
        *,
        permissions=None,
    ):
        return self.membership_model.objects.create(
            user=self.user,
            company=self.company,
            branch=self.branch,
            department=self.department,
            role=self.membership_model.Role.MEMBER,
            permissions=permissions or [],
            is_primary=True,
            is_active=True,
        )

    def test_assistant_requires_login(self):
        response = self.client.get("/ai/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/accounts/login",
            response.url,
        )

    def test_assistant_rejects_user_without_membership(self):
        self.client.force_login(self.user)

        response = self.client.get("/ai/")

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            "Aktif çalışma alanı üyeliğiniz bulunmuyor",
            status_code=403,
        )

    def test_assistant_rejects_membership_without_tool_access(self):
        self.create_membership()

        self.client.force_login(self.user)

        response = self.client.get("/ai/")

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            "bir ERP modülüne erişiminiz bulunmuyor",
            status_code=403,
        )

    @patch(
        "apps.ai_core.views.FunctionCallingRuntime",
        FakeEnterpriseAssistantRuntime,
    )
    def test_assistant_runs_runtime_with_allowed_modules(self):
        self.create_membership(
            permissions=[
                self.membership_model
                .Permission
                .ACCESS_CRM,
                self.membership_model
                .Permission
                .ACCESS_FINANCE,
            ]
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/ai/",
            {
                "message": (
                    "Nova Kozmetik'in bakiyesini göster."
                ),
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "12.500 TRY",
        )
        self.assertContains(
            response,
            "get_customer_balance",
        )

        init_call = (
            FakeEnterpriseAssistantRuntime
            .calls[0]["init"]
        )

        self.assertEqual(
            init_call["company"],
            self.company,
        )
        self.assertEqual(
            init_call["requested_by"],
            self.user,
        )
        self.assertEqual(
            init_call["allowed_modules"],
            frozenset(
                {
                    "crm",
                    "finance",
                }
            ),
        )

    def test_assistant_rejects_empty_message(self):
        self.create_membership(
            permissions=[
                self.membership_model
                .Permission
                .ACCESS_CRM,
            ]
        )

        self.client.force_login(self.user)

        response = self.client.post(
            "/ai/",
            {
                "message": "   ",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "bir mesaj yazmalısınız",
        )


class ERPToolOptionalNullNormalizationTestCase(TestCase):
    def test_optional_null_argument_is_removed(self):
        from apps.ai_core.tools.validation import (
            normalize_tool_arguments,
        )

        schema = {
            "type": "object",
            "properties": {
                "requisition_number": {
                    "type": "string",
                },
            },
            "required": [],
            "additionalProperties": False,
        }

        normalized = normalize_tool_arguments(
            schema=schema,
            arguments={
                "requisition_number": None,
            },
        )

        self.assertEqual(normalized, {})

    def test_required_null_argument_is_not_removed(self):
        from apps.ai_core.tools.validation import (
            normalize_tool_arguments,
        )

        schema = {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                },
            },
            "required": ["sku"],
            "additionalProperties": False,
        }

        normalized = normalize_tool_arguments(
            schema=schema,
            arguments={
                "sku": None,
            },
        )

        self.assertEqual(
            normalized,
            {
                "sku": None,
            },
        )

    def test_required_null_still_fails_validation(self):
        from apps.ai_core.tools import (
            ERPToolValidationError,
        )
        from apps.ai_core.tools.validation import (
            normalize_tool_arguments,
            validate_tool_arguments,
        )

        schema = {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                },
            },
            "required": ["sku"],
            "additionalProperties": False,
        }

        arguments = normalize_tool_arguments(
            schema=schema,
            arguments={
                "sku": None,
            },
        )

        with self.assertRaises(
            ERPToolValidationError
        ):
            validate_tool_arguments(
                schema=schema,
                arguments=arguments,
            )
