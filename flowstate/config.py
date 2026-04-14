from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	DATABASE_URL: str | None = None
	REDIS_URL: str
	CHROMA_HOST: str = "localhost"
	CHROMA_PORT: int = 8000
	OLLAMA_BASE_URL: str = "http://localhost:11434"
	DEFAULT_MODEL: str = "mistral"
	ENCRYPTION_KEY: str = "dev-only-change-me"

	POSTGRES_HOST: str | None = None
	POSTGRES_PORT: int = 5432
	POSTGRES_DB: str | None = None
	POSTGRES_USER: str | None = None
	POSTGRES_PASSWORD: str | None = None

	WATCHER_TEAM_IDS: str = "team_alpha"
	WATCHER_TYPES: str = "file"
	WATCHER_POLL_INTERVAL: int = 60
	WATCHER_MONITOR_INTERVAL_SECONDS: int = 10
	WATCHER_HEARTBEAT_TTL_SECONDS: int = 180

	ENABLE_FILE_WATCHER: bool = True
	FILE_WATCH_PATHS: str = "./storage/inbox"
	FILE_WATCH_EXTENSIONS: str = ".txt,.md,.json,.csv,.log"

	ENABLE_EMAIL_WATCHER: bool = False
	EMAIL_WATCH_QUERY: str = "in:inbox newer_than:2d"
	EMAIL_WATCH_LABEL_IDS: str = ""
	GMAIL_TOKEN_FILE: str | None = None

	model_config = SettingsConfigDict(env_file=".env", extra="ignore")

	@model_validator(mode="after")
	def build_database_url(self):
		if not self.DATABASE_URL and all(
			[self.POSTGRES_HOST, self.POSTGRES_DB, self.POSTGRES_USER, self.POSTGRES_PASSWORD]
		):
			self.DATABASE_URL = (
				f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
				f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
			)

		if not self.DATABASE_URL:
			raise ValueError("DATABASE_URL is required (or provide complete POSTGRES_* settings)")

		return self


settings = Settings()
