import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from autotransform.db.base import create_tables, shutdown_session
from autotransform.model import model_client
from autotransform.routes import config, data, process
from autotransform.utils import Environment, settings, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield
    await shutdown_session()
    await model_client.aclose()


app = FastAPI(lifespan=lifespan, title="AutoTransform", version="0.0.0")
app.include_router(config.router, prefix="/api/v1")
app.include_router(process.router, prefix="/api/v1")
app.include_router(data.router, prefix="/api/v1")


if settings.environment != Environment.dev:

    @app.get("/run/{config_id}/{run_id}", include_in_schema=False)
    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse("./autotransform/ui/index.html")

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    app.mount("/", StaticFiles(directory="./autotransform/ui/"), name="ui")
