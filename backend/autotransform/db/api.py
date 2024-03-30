import json
import logging
from typing import Optional, cast
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import async_scoped_session

from autotransform.autotransform_types import (
    BaseRecord,
    Code,
    ExampleRecord,
    ProcessEventMetadata,
    ProcessingConfig,
    ProcessingMessage,
    ProcessingStatus,
)
from autotransform.db.models import ConfigModel, ProcessEventsModel

logger = logging.getLogger(__name__)


async def get_processing_config(
    config_id: UUID, db: async_scoped_session
) -> Optional[ProcessingConfig]:
    config_result = await db.execute(
        select(ConfigModel).where(ConfigModel.id == config_id)
    )
    config_model: ConfigModel = config_result.scalars().one_or_none()

    if config_model is None:
        config = None
    else:
        code = cast(Optional[str], config_model.code)
        config = ProcessingConfig(
            config_id=cast(UUID, config_model.id),
            name=cast(str, config_model.name),
            output_schema=cast(dict, config_model.output_schema),
            user_provided_records=cast(
                list[ExampleRecord],
                config_model.user_provided_records,
            ),
            code=(None if code is None else Code(code=code)),
            previous_records=cast(
                list[BaseRecord], config_model.previous_records
            ),
            current_records=cast(
                list[BaseRecord], config_model.current_records
            ),
            bot_provided_records=cast(
                list[ExampleRecord], config_model.bot_provided_records
            ),
        )

    return config


async def save_processing_config(
    config_id: UUID,
    processing_config: ProcessingConfig,
    db: async_scoped_session,
) -> None:
    processing_config_dict = processing_config.model_dump()
    code = (
        None
        if processing_config_dict["code"] is None
        else processing_config_dict["code"]["code"]
    )
    await db.execute(
        update(ConfigModel)
        .where(ConfigModel.id == config_id)
        .values(
            {
                "name": processing_config_dict["name"],
                "output_schema": processing_config_dict["output_schema"],
                "user_provided_records": processing_config_dict[
                    "user_provided_records"
                ],
                "code": code,
                "previous_records": processing_config_dict["previous_records"],
                "current_records": processing_config_dict["current_records"],
                "bot_provided_records": processing_config_dict[
                    "bot_provided_records"
                ],
            }
        )
    )


async def insert_processing_event(
    config_id: UUID,
    input_count: int,
    db: async_scoped_session,
) -> ProcessEventsModel:
    event_raw = await db.execute(
        insert(ProcessEventsModel)
        .returning(ProcessEventsModel)
        .values(
            {
                "config_id": config_id,
                "input_count": input_count,
                "output_count": None,
                "status": ProcessingStatus.running.value,
                "event_history": [],
            }
        )
    )
    event = event_raw.scalars().one()
    return event


async def update_processing_event(
    event: ProcessingMessage,
    db: async_scoped_session,
) -> None:
    event_history_raw = event.model_dump_json(include={"runs"})
    event_history = json.loads(event_history_raw)
    event_history = event_history["runs"]

    await db.execute(
        update(ProcessEventsModel)
        .where(ProcessEventsModel.id == event.id)
        .values(
            {
                "config_id": event.config_id,
                "input_count": event.input_count,
                "output_count": event.output_count,
                "status": event.status,
                "event_history": event_history,
            }
        )
    )


async def get_processing_event_history(
    config_id: UUID,
    db: async_scoped_session,
) -> list[ProcessEventMetadata]:
    event_result = await db.execute(
        select(
            ProcessEventsModel.id,
            ProcessEventsModel.config_id,
            ProcessEventsModel.input_count,
            ProcessEventsModel.output_count,
            ProcessEventsModel.status,
            ProcessEventsModel.updated_at,
        )
        .where(ProcessEventsModel.config_id == config_id)
        .order_by(ProcessEventsModel.updated_at.desc())
    )

    event_metadata = []
    for event in event_result:
        event_metadata.append(
            ProcessEventMetadata(
                id=cast(UUID, event.id),
                config_id=cast(UUID, event.config_id),
                input_count=cast(int, event.input_count),
                output_count=cast(int, event.output_count),
                status=cast(ProcessingStatus, event.status),
                timestamp=cast(str, event.updated_at.isoformat()),
            )
        )

    return event_metadata


async def get_processing_message(
    config_id: UUID,
    run_id: UUID,
    db: async_scoped_session,
) -> ProcessingMessage:
    message_result = await db.execute(
        select(ProcessEventsModel).where(
            ProcessEventsModel.config_id == config_id,
            ProcessEventsModel.id == run_id,
        )
    )
    message = message_result.scalars().one()
    return ProcessingMessage(
        id=cast(UUID, message.id),
        config_id=cast(UUID, message.config_id),
        input_count=cast(int, message.input_count),
        output_count=cast(int, message.output_count),
        status=cast(ProcessingStatus, message.status),
        runs=cast(list, message.event_history),
        start_timestamp=cast(str, message.created_at.isoformat()),
        timestamp=cast(str, message.updated_at.isoformat()),
    )
