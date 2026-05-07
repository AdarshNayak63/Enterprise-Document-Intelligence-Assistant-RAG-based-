from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Document Intelligence Assistant"
    app_env: str = "dev"
    secret_key: str = "change_me_in_production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8

    database_url: str = "sqlite:///./rag_app.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    upload_dir: str = "storage/uploads"
    faiss_dir: str = "storage/faiss"
    chunk_size: int = 800
    chunk_overlap: int = 150
    retrieval_top_k: int = 5

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
