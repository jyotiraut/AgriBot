"""
Krishi- Configuration
Load from environment / .env file
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    mongodb_uri: str 
    mongodb_db_name: str = "krishimitra"

    # LLM and Embeddings
    GROQ_API_KEY: str = ""  # deprecated — kept so old .env files don't break
    # Gemini's OpenAI-compatible endpoint (used by the native OpenAI-SDK callers)
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Vector DB
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    COLLECTION_NAME: str = "krishimitra_knowledge_base"

    # Embedding Configuration
    # NOTE: This must match the model the Qdrant collection was ingested with.
    # Current default is English-only (384-dim). For better Nepali/Romanized
    # retrieval, switch to a multilingual model and RE-INGEST, e.g.:
    #   embedding_model = "BAAI/bge-m3"                              (1024-dim)
    #   embedding_model = "paraphrase-multilingual-MiniLM-L12-v2"   (384-dim, light)
    # After changing the model, run `python -m rag.ingest` again — ingestion
    # auto-recreates the collection when the dimension changes.
    embedding_model: str = "BAAI/bge-m3"  # multilingual (1024-dim) — needed for Nepali
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # Retrieval
    retriever_top_k: int = 3
    retriever_score_threshold: float = 0.0   # 0 disables filtering
    
    # File Paths
    base_dir: str = ""
    pdf_folder: str = ""
    
    # LLM Settings
    # llm_model      → quality-critical reasoning (advisory synthesis, crop
    #                  validation, disease advice). Slower/pricier.
    # llm_model_fast → the latency-sensitive chat loop (reply + field extraction).
    # Use Google's maintained "-latest" aliases: they always resolve to the
    # newest stable model in each tier, so they won't 404 when a generation is
    # retired (gemini-2.5-* is already blocked for new API keys).
    llm_model: str = "gemini-pro-latest"        # quality tier (best available)
    llm_model_fast: str = "gemini-flash-latest"  # fast chat-loop tier
    temperature: float = 0.3
    google_api_key: str = ""

    # JWT Settings
    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72

    # Notification channel
    delivery_channel: str = "simulate"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # App
    app_name: str = "KrishiMitra"
    debug: bool = False
    default_language: str = "nepali"  # nepali | english

    # CORS — comma-separated origins, or "*" for all (dev only).
    # Credentials are only allowed when origins are explicitly listed (not "*").
    cors_allow_origins: str = "*"

    # Rule engine thresholds
    max_urea_kg_per_ha: float = 120.0
    max_dap_kg_per_ha: float = 100.0
    max_mop_kg_per_ha: float = 80.0
    max_pesticide_ml_per_ha: float = 1000.0
    base_temp_celsius: float = 10.0  # base temperature for GDD calculation

    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "Krishi mitra"
    LANGCHAIN_TRACING_V2: str = "true"

    # Crop Keywords
    crop_keywords: dict = {
        "potato":      ["potato", "aloo"],
        "tomato":      ["tomato", "golbheda"],
        "cauliflower": ["cauliflower", "cauli", "kauli"],
        "soil":        ["soil", "fertilizer", "mato"],
        "pest":        ["pest", "disease", "ipm", "rog"],
    }

    def cors_origins_list(self) -> list[str]:
        """Parse cors_allow_origins into a list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def jwt_secret_is_default(self) -> bool:
        return self.jwt_secret == "change-this-in-production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()