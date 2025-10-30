import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

current_file = Path(__file__)
project_root = current_file.parent.parent.parent.parent
env_path = project_root / ".env"

load_dotenv(dotenv_path=env_path)

@dataclass(frozen=True)
class Settings:
    es_hosts: str = os.getenv("ES_HOSTS", os.getenv("ES_HOST", "http://localhost:9200"))
    es_index: str = os.getenv("ES_INDEX", "news_sampleindex")
    es_username: str | None = os.getenv("ES_USERNAME") or None
    es_password: str | None = os.getenv("ES_PASSWORD") or None
    es_verify_certs: bool = (os.getenv("ES_VERIFY_CERTS", "false").lower() == "true")
    es_ca_cert: str | None = os.getenv("ES_CA_CERT") or None

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    dart_api_key: str | None = os.getenv("DART_API_KEY") or None
    clova_api_key: str | None = os.getenv("CLOVA_API_KEY") or None

    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_username: str | None = os.getenv("DB_USERNAME") or None
    db_password: str | None = os.getenv("DB_PASSWORD") or None
    db_database: str | None = os.getenv("DB_DATABASE") or None

    allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "*")

settings = Settings()
