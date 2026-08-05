from django.test import TestCase

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
