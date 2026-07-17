"""Cấu hình tập trung (pydantic-settings). Owner: Dev C. Xem .env.example."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/app.db"
    chroma_persist_dir: str = "./data/chroma"
    procedures_collection: str = "tthc_procedures"
    bm25_index_path: str = "./data/bm25_index.json"

    # LLM cho chatbot/agent (Dev A) — TÁCH RIÊNG với LLM cho OCR bên dưới.
    llm_provider: str = "anthropic"  # 'anthropic' | 'gemini'
    llm_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"

    ocr_engine: str = "paddleocr"  # 'paddleocr' | 'google_vision' | 'vision_llm'
    ocr_confidence_threshold: float = 0.85
    # LLM cho engine vision_llm (chữ viết tay) — key/model riêng, không dùng chung với chatbot.
    ocr_llm_provider: str = "openai"  # 'openai' | 'anthropic' | 'gemini'
    ocr_llm_api_key: str = ""
    ocr_llm_model: str = "gpt-5"

    readiness_submit_threshold: float = 0.9

    jwt_secret: str = "change-me"
    jwt_access_ttl_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
