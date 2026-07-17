"""Cấu hình tập trung (pydantic-settings). Owner: Dev C. Xem .env.example."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/app.db"
    chroma_persist_dir: str = "./data/chroma"
    procedures_collection: str = "tthc_procedures"
    bm25_index_path: str = "./data/bm25_index.json"

    # LLM cho chatbot/agent — tách riêng với LLM cho OCR bên dưới.
    llm_provider: str = "anthropic"  # 'anthropic' | 'gemini'
    llm_api_key: str = ""  # hoặc đặt ANTHROPIC_API_KEY
    # Haiku: tier Claude rẻ/nhanh nhất — cố định theo quyết định dự án (như C2)
    llm_model: str = "claude-haiku-4-5"
    llm_temperature: float = 0.1
    llm_timeout_s: int = 30

    # 'auto' | 'google' | 'bge-m3' | 'fake' — phải khớp provider lúc index Chroma
    embedding_provider: str = "auto"
    local_embedding_model_name: str = "BAAI/bge-m3"

    retrieval_top_k: int = 6
    identify_confidence_threshold: float = 0.55
    identify_min_relevance: float = 0.6
    identify_min_margin: float = 0.15

    ocr_engine: str = "paddleocr"  # 'paddleocr' | 'google_vision' | 'vision_llm'
    ocr_confidence_threshold: float = 0.85
    # LLM cho engine vision_llm (chữ viết tay) — key/model riêng, không dùng chung với chatbot.
    ocr_llm_provider: str = "openai"  # 'openai' | 'anthropic' | 'gemini'
    ocr_llm_api_key: str = ""
    ocr_llm_model: str = "gpt-5-mini"

    readiness_submit_threshold: float = 0.9

    jwt_secret: str = "change-me"
    jwt_access_ttl_minutes: int = 30
    demo_password: str = "ChangeMe123!"
    app_env: str = "development"
    enable_demo_auth: bool = True
    persistence_enabled: bool = False
    storage_backend: str = "local"
    storage_root: str = "./uploads/private"
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_audience: str = ""
    oidc_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/oidc/callback"
    oidc_required_mfa_claim: str = "amr:mfa"
    upload_max_files: int = 10
    upload_max_bytes: int = 20 * 1024 * 1024

settings = Settings()
