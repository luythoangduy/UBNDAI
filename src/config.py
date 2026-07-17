"""Cấu hình tập trung (pydantic-settings). Owner: Dev C. Xem .env.example."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/app.db"
    chroma_persist_dir: str = "./data/chroma"
    procedures_collection: str = "tthc_procedures"
    bm25_index_path: str = "./data/bm25_index.json"

    llm_provider: str = "anthropic"  # Claude — cùng stack với C2
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

    ocr_engine: str = "paddleocr"  # 'paddleocr' | 'google_vision'
    ocr_confidence_threshold: float = 0.85

    readiness_submit_threshold: float = 0.9

    jwt_secret: str = "change-me"
    jwt_access_ttl_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
