import logging.config
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings


class FileProviderType(str, Enum):
    local = "local"


class GitProviderType(str, Enum):
    github = "github"


class Environment(str, Enum):
    dev = "dev"
    prod = "prod"


class ModelType(str, Enum):
    gpt4turbo = "gpt-4-turbo"
    gpt3turbo = "gpt-3.5-turbo"


class Settings(BaseSettings):
    openai_api_key: str
    postgres_uri: str
    model: ModelType = ModelType.gpt4turbo
    file_provider: FileProviderType = FileProviderType.local
    file_provider_config: str = '{"save_path": "/app-data/"}'
    environment: Environment = Environment.dev
    git_provider: Optional[GitProviderType] = None
    git_provider_secret: Optional[str] = None
    base_url: str = "http://localhost:8000"
    processing_debug: bool = False
    log_level: str = "INFO"

    @property
    def postgres_connection_string(self) -> str:
        return self.postgres_uri.replace(
            "postgres://", "postgresql+asyncpg://"
        )


settings = Settings()  # type: ignore


class CustomLogFormatter(logging.Formatter):
    def format(self, record):
        extra_vars = []

        for key, value in record.__dict__.items():
            if (
                key
                not in logging.LogRecord(
                    "", 0, "", 0, "", (), None, None
                ).__dict__
                and key != "message"
            ):
                extra_vars.append(f"{key}={value}")

        if extra_vars:
            record.msg = f"{record.msg} {', '.join(extra_vars)}"
        return super().format(record)


class EndpointFilter(logging.Filter):
    def filter(self, record):
        # filter out healthz requests
        return record.getMessage().find("/healthz") == -1


def setup_logging() -> None:
    handlers = {
        "default": {
            "level": settings.log_level,
            "formatter": "default",
            "class": "logging.StreamHandler",
        },
    }

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": CustomLogFormatter,
                "format": "%(asctime)s.%(msecs)03d %(levelname)s %(name)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "loggers": {
            "": {
                "level": settings.log_level,
                "handlers": ["default"],
            },
        },
    }

    logging.config.dictConfig(logging_config)
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
