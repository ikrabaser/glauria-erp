class AICoreError(Exception):
    """AI Core içerisindeki bütün kontrollü hataların temel sınıfı."""


class AIConfigurationError(AICoreError):
    """AI sağlayıcısı eksik veya devre dışı olduğunda oluşur."""


class AIProviderError(AICoreError):
    """Harici AI sağlayıcısından geçerli yanıt alınamadığında oluşur."""


class AIStructuredOutputError(AICoreError):
    """Yapılandırılmış AI çıktısı ayrıştırılamadığında oluşur."""
