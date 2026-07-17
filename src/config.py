"""Cấu hình tập trung (pydantic-settings). Owner: Dev C. Xem .env.example."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/app.db"
    chroma_persist_dir: str = "./data/chroma"
    procedures_collection: str = "tthc_procedures"
    bm25_index_path: str = "./data/bm25_index.json"

    llm_provider: str = "gemini"  # cùng stack với C2
    llm_api_key: str = ""

    ocr_engine: str = "paddleocr"  # 'paddleocr' | 'google_vision' | 'vision_llm'
    ocr_confidence_threshold: float = 0.85
    vision_llm_model: str = "gemini-2.5-flash"  # model cho engine vision_llm (chữ viết tay)

    readiness_submit_threshold: float = 0.9

    jwt_secret: str = "change-me"
    jwt_access_ttl_minutes: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
