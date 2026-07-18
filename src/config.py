"""Cấu hình tập trung (pydantic-settings). Owner: Dev C. Xem .env.example."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/app.db"
    chroma_persist_dir: str = "./data/chroma"
    procedures_collection: str = "tthc_procedures"
    bm25_index_path: str = "./data/bm25_index.json"
    raw_documents_dir: str = "./data/raw_documents"
    procedure_candidates_dir: str = "./data/procedure_candidates"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_connect_timeout_s: float = 0.25
    chat_experience_cache_ttl_s: int = 3600
    # Khi kéo nguồn live thất bại, cache kết quả suy giảm bằng TTL ngắn này thay vì
    # chat_experience_cache_ttl_s — nếu không, một cú 503 thoáng qua của Cổng DVC sẽ
    # bị "đóng băng" nguyên 1 tiếng dù cổng đã hồi phục.
    official_source_retry_ttl_s: int = 120
    official_source_live_fetch: bool = True
    official_source_timeout_s: float = 2.5
    # thutuc.dichvucong.gov.vn đã ngừng phục vụ (503 toàn subdomain); Cổng DVC nay
    # gom về dichvucong.gov.vn với route tra cứu mới.
    dvc_search_url: str = "https://dichvucong.gov.vn/tra-cuu-thu-tuc"
    # Tách index VBPL khỏi catalog thủ tục để có thể dùng lại index dựng sẵn.
    # Rỗng = dùng cùng CHROMA_PERSIST_DIR với catalog.
    legal_chroma_persist_dir: str = ""
    legal_collection: str = "legal_documents"
    # BM25 là tuỳ chọn; chỉ cấu hình khi nó được build từ đúng legal collection.
    legal_bm25_index_path: str = ""

    # LLM cho chatbot/agent — tách riêng với LLM cho OCR bên dưới.
    llm_provider: str = "anthropic"  # 'anthropic' | 'gemini'
    llm_api_key: str = ""  # hoặc đặt ANTHROPIC_API_KEY
    # Haiku: tier Claude rẻ/nhanh nhất — cố định theo quyết định dự án (như C2)
    llm_model: str = "claude-haiku-4-5"
    llm_temperature: float = 0.1
    llm_timeout_s: int = 30

    # 'auto' | 'google' | 'huggingface' | 'bge-m3' | 'hashing' | 'fake'
    # Phải khớp provider lúc index Chroma.
    embedding_provider: str = "auto"
    local_embedding_model_name: str = "BAAI/bge-m3"
    local_embedding_offline: bool = True
    huggingface_embedding_model_name: str = "BAAI/bge-m3"
    huggingface_inference_provider: str = "hf-inference"
    huggingface_inference_timeout_s: float = 60.0
    hash_embedding_dimension: int = 384

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
    # Chỉ áp dụng provider openai (GPT-5): minimal | low | medium | high.
    # OCR là trích xuất, không cần suy luận sâu — effort thấp giảm mạnh latency + token.
    ocr_llm_reasoning_effort: str = "minimal"
    # Cache kết quả OCR theo hash ảnh (upload lại cùng ảnh không tốn API call). 0 = tắt.
    ocr_cache_size: int = 128

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
    upload_max_bytes: int = 10 * 1024 * 1024

    @property
    def database_persistence_enabled(self) -> bool:
        """Use configured persistence automatically when DATABASE_URL is PostgreSQL."""
        return self.persistence_enabled or self.database_url.startswith(
            ("postgresql://", "postgresql+psycopg://")
        )

settings = Settings()
