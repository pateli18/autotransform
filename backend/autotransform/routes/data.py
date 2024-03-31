from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from autotransform.autotransform_types import DataType
from autotransform.file import file_client

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
)


@router.get(
    "/export/{config_id}/{run_id}/{data_type}",
)
async def export(
    config_id: UUID,
    run_id: UUID,
    data_type: DataType,
):
    async def generate_jsonl():
        async for line in file_client.read_data(config_id, run_id, data_type):
            yield line

    return StreamingResponse(
        content=generate_jsonl(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename={config_id}-{run_id}-{data_type}.jsonl"
        },
    )
