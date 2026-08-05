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
