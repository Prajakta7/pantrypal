"""All settings come from environment variables (see .env.example)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    project_id: str = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    region: str = os.environ.get("ALLOYDB_REGION", "us-central1")
    cluster: str = os.environ.get("ALLOYDB_CLUSTER", "pantrypal-cluster")
    instance: str = os.environ.get("ALLOYDB_INSTANCE", "pantrypal-primary")
    db_name: str = os.environ.get("DB_NAME", "pantrypal")
    db_user: str = os.environ.get("DB_USER", "postgres")
    db_password: str = os.environ.get("DB_PASSWORD", "")
    ip_type: str = os.environ.get("ALLOYDB_IP_TYPE", "PUBLIC").upper()  # PUBLIC, PRIVATE or PSC

    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "text-embedding-005")
    # Use a current Gemini Flash model available in your project
    gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_location: str = os.environ.get("GEMINI_LOCATION", "global")
    default_timezone: str = os.environ.get("DEFAULT_TIMEZONE", "UTC")

    @property
    def instance_uri(self) -> str:
        return (f"projects/{self.project_id}/locations/{self.region}"
                f"/clusters/{self.cluster}/instances/{self.instance}")


settings = Settings()
