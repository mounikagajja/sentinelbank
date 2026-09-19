from functools import lru_cache

from pydantic import Field, PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = Field(alias="POSTGRES_USER")
    postgres_password: str = Field(alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5434, alias="POSTGRES_PORT")

    redpanda_broker: str = Field(default="localhost:19092", alias="REDPANDA_BROKER")
    transactions_topic: str = Field(default="transactions", alias="TRANSACTIONS_TOPIC")

    consumer_group: str = Field(default="fraud-scorer", alias="CONSUMER_GROUP")
    fraud_threshold: float = Field(default=0.7, alias="FRAUD_THRESHOLD")
    model_path: str = Field(default="models/fraud_xgb.json", alias="MODEL_PATH")

    @computed_field
    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db,
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
