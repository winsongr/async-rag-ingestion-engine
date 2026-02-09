from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Data Platform"

    # Postgres
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "cortex"
    POSTGRES_PASSWORD: str = "R29We1aNH3Mt"
    POSTGRES_DB: str = "cortex"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str | None = None

    @property
    def REDIS_URI(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    DEFAULT_TIMEOUT: int = 10

    # Queue backpressure
    QUEUE_MAX_LENGTH: int = 1000

    @property
    def QDRANT_URI(self) -> str:
        return self.QDRANT_URL


settings = Settings()
