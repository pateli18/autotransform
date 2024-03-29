import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from autotransform.db.base import create_tables, shutdown_session
from autotransform.model import model_client
from autotransform.routes import config, data, process
from autotransform.utils import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield
    await shutdown_session()
    await model_client.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(config.router, prefix="/api/v1")
app.include_router(process.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")
