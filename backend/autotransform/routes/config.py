import json
import logging
import re
from typing import Optional, cast
from uuid import UUID

import jsonschema
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, insert, select
from sqlalchemy.ext.asyncio import async_scoped_session

from autotransform.autotransform_types import (
    ConfigMetadata,
    ExampleRecord,
    ModelChat,
    ModelChatType,
    OpenAiChatInput,
    ProcessEventMetadata,
    ProcessingConfig,
    UpsertConfig,
)
from autotransform.db.api import (
    get_processing_config,
    get_processing_event_history,
)
from autotransform.db.base import get_session
from autotransform.db.models import ConfigModel
from autotransform.model import model_client, send_openai_request

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/config",
    tags=["config"],
    responses={404: {"description": "Not found"}},
)

MAX_PARSE_ATTEMPTS = 3


class UpsertConfigResponse(BaseModel):
    config_id: UUID


class ParseSchemaRequest(BaseModel):
    input_schema: Optional[str] = None
    examples: Optional[list[ExampleRecord]] = None


@router.post("/upsert", response_model=UpsertConfigResponse)
async def upsert_config(
    request: UpsertConfig,
    db: async_scoped_session = Depends(get_session),
) -> UpsertConfigResponse:

    for record in request.user_provided_records or []:
        try:
            jsonschema.validate(request.output_schema, record.output)
        except jsonschema.ValidationError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Labeled record does not comply with provided schema: {e.message}",
            )

    if request.config_id is None:
        config_id = await db.execute(
            insert(ConfigModel).returning(ConfigModel.id),
            [
                request.model_dump(exclude={"config_id"}),
            ],
        )
        config_id = config_id.scalars().one()
    else:
        config_id = request.config_id
        config_result = await db.execute(
            select(ConfigModel).where(ConfigModel.id == config_id)
        )
        config: ConfigModel = config_result.scalars().one_or_none()
        if config is None:
            raise HTTPException(
                status_code=404,
                detail="Config not found",
            )
        config.name = cast(Column[str], request.name)
        config.output_schema = cast(Column, request.output_schema)
        config.user_provided_records = cast(
            Column,
            [
                record.model_dump()
                for record in request.user_provided_records or []
            ],
        )

    await db.commit()
    return UpsertConfigResponse(config_id=config_id)


@router.get(
    "/process-history/{config_id}", response_model=list[ProcessEventMetadata]
)
async def get_process_history(
    config_id: UUID,
    db: async_scoped_session = Depends(get_session),
) -> list[ProcessEventMetadata]:
    event_history = await get_processing_event_history(config_id, db)
    return event_history


@router.get("/all", response_model=list[ConfigMetadata])
async def get_all_configs(
    db: async_scoped_session = Depends(get_session),
) -> list[ConfigMetadata]:
    configs_result = await db.execute(select(ConfigModel))
    configs = configs_result.scalars().all()
    return [
        ConfigMetadata(
            config_id=cast(UUID, config.id),
            name=cast(str, config.name),
            last_updated=config.updated_at.isoformat(),
        )
        for config in configs
    ]


@router.get("/{config_id}", response_model=ProcessingConfig)
async def get_config(
    config_id: UUID,
    db: async_scoped_session = Depends(get_session),
) -> ProcessingConfig:
    config = await get_processing_config(config_id, db)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Config not found",
        )

    return config


def create_parse_schema_prompt(input_schema: str) -> list[ModelChat]:
    system_message = """
FACTS:
- You are an expert developer
- You are given an object which represents the output of a data transform. This object can be many different things, e.g. a json, a pydantic schema, etc.

RULES:
- Your task is to convert the object into a valid jsonschema
- Only return a jsonschema, nothing else
"""

    return [
        ModelChat(
            role=ModelChatType.system,
            content=system_message,
        ),
        ModelChat(
            role=ModelChatType.user,
            content=input_schema,
        ),
    ]


def create_schema_from_examples_prompt(
    examples: list[ExampleRecord],
) -> list[ModelChat]:
    system_message = """
FACTS:
- You are an expert developer
- You are given json records, each of which has an `input` and an `output`. The `input` is a json object and the `output` is a json object.

RULES:
- Your task is to create a valid jsonschema from the `output` of the records
- Only return a jsonschema, nothing else
"""

    fmt_example_records = "\n".join([example.prompt for example in examples])
    return [
        ModelChat(
            role=ModelChatType.system,
            content=system_message,
        ),
        ModelChat(
            role=ModelChatType.user,
            content=fmt_example_records,
        ),
    ]


@router.post("/parse-schema", response_model=dict)
async def parse_schema(request: ParseSchemaRequest) -> dict:
    output_schema = None
    if request.input_schema is not None:
        chat = create_parse_schema_prompt(request.input_schema)
    elif request.examples is not None:
        chat = create_schema_from_examples_prompt(request.examples)
    else:
        raise HTTPException(
            status_code=422,
            detail="Either `input_schema` or `examples` must be provided",
        )

    attempt = 1
    while output_schema is None and attempt <= MAX_PARSE_ATTEMPTS:
        openai_chat_input = OpenAiChatInput(messages=chat)
        response = await send_openai_request(
            model_client,
            openai_chat_input.data,
            "chat/completions",
        )
        raw_output = response["choices"][0]["message"]["content"]
        if "```json" in raw_output:
            groups = re.search(r"```json(.*)```", raw_output, re.DOTALL)
            if groups is not None:
                raw_output = groups.group(1).strip()
        try:
            schema = json.loads(raw_output)
            jsonschema.Validator.check_schema(schema)
            output_schema = schema
        except Exception as e:
            logger.info(f"model returned invalid jsonschema: {e}")
            chat.extend(
                [
                    ModelChat(
                        **response["choices"][0]["message"],
                    ),
                    ModelChat(
                        role=ModelChatType.user,
                        content=f"This is not a valid jsonschema, I got the following error validating it: {e}",
                    ),
                ]
            )
            attempt += 1

    if output_schema is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse schema",
        )
    return output_schema
