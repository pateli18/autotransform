import asyncio
import json
import os
from typing import AsyncGenerator
from uuid import UUID

import aiofiles
from cachetools import TTLCache

from autotransform.autotransform_types import DataType
from autotransform.utils import settings

partial_data_cache: TTLCache[str, list[dict]] = TTLCache(maxsize=1000, ttl=300)
partial_data_cache_lock = asyncio.Lock()


def _create_path(config_id: UUID, run_id: UUID, data_type: DataType) -> str:
    return os.path.join(
        settings.file_save_path,
        str(config_id),
        str(run_id),
        f"{data_type.value}.jsonl",
    )


async def save_data(
    data: list[dict], config_id: UUID, run_id: UUID, data_type: DataType
):
    path = _create_path(config_id, run_id, data_type)

    # create directories if they don't exist
    os.makedirs(os.path.dirname(path), exist_ok=True)

    async with aiofiles.open(path, "w") as f:
        # write data as jsonl
        for row in data:
            await f.write(json.dumps(row) + "\n")


async def read_data(
    config_id: UUID, run_id: UUID, data_type: DataType
) -> AsyncGenerator[str, None]:
    path = _create_path(config_id, run_id, data_type)

    async with aiofiles.open(path, "r") as f:
        # read data as jsonl
        async for line in f:
            yield line


async def read_data_partial(
    config_id: UUID, run_id: UUID, data_type: DataType, num_rows: int
) -> list[dict]:
    path = _create_path(config_id, run_id, data_type)
    data = partial_data_cache.get(path)
    if data is not None:
        return data

    data = []
    async with aiofiles.open(path, "r") as f:
        # read data as jsonl
        async for line in f:
            data.append(json.loads(line))
            if len(data) >= num_rows:
                break

    async with partial_data_cache_lock:
        partial_data_cache[path] = data

    return data
