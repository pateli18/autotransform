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
    GitConfig,
    OutputSchema,
    ProcessEventMetadata,
    ProcessingConfig,
    ProcessingMessage,
    ProcessingStatus,
)
from autotransform.db.models import ConfigModel, ProcessEventsModel

logger = logging.getLogger(__name__)


async def get_latest_config_event(
    config_id: UUID, db: async_scoped_session
) -> Optional[ProcessingMessage]:
    event_result_raw = await db.execute(
        select(ProcessEventsModel)
        .where(ProcessEventsModel.config_id == config_id)
        .order_by(ProcessEventsModel.updated_at.desc())
        .limit(1)
    )
    event_result = event_result_raw.scalars().one_or_none()

    processing_message = None
    if event_result is not None:
        processing_message = ProcessingMessage(
            id=cast(UUID, event_result.id),
            config_id=cast(UUID, event_result.config_id),
            input_count=cast(int, event_result.input_count),
            output_count=cast(int, event_result.output_count),
            status=cast(ProcessingStatus, event_result.status),
            runs=cast(list, event_result.event_history),
            timestamp=cast(str, event_result.updated_at.isoformat()),
        )

    return processing_message


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
        # process code output
        code_raw = cast(Optional[str], config_model.code)
        if code_raw is None:
            code = None
        else:
            code = Code(
                code=code_raw,
                commit=cast(Optional[str], config_model.code_commit),
            )

        # process git config
        git_owner_raw = cast(Optional[str], config_model.git_owner)
        if git_owner_raw is None:
            git_config = None
        else:
            git_config = GitConfig(
                owner=cast(str, config_model.git_owner),
                repo_name=cast(str, config_model.git_repo_name),
                primary_branch_name=cast(
                    str, config_model.git_primary_branch_name
                ),
                block_human_review=cast(
                    bool, config_model.git_block_human_review
                ),
            )

        config = ProcessingConfig(
            config_id=cast(UUID, config_model.id),
            name=cast(str, config_model.name),
            output_schema=OutputSchema(
                output_schema=cast(dict, config_model.output_schema),
                commit=cast(Optional[str], config_model.output_schema_commit),
            ),
            user_provided_records=cast(
                list[ExampleRecord],
                config_model.user_provided_records,
            ),
            code=code,
            previous_records=cast(
                list[BaseRecord], config_model.previous_records
            ),
            current_records=cast(
                list[BaseRecord], config_model.current_records
            ),
            bot_provided_records=cast(
                list[ExampleRecord], config_model.bot_provided_records
            ),
            git_config=git_config,
        )

    return config


async def save_processing_config(
    config_id: UUID,
    processing_config: ProcessingConfig,
    db: async_scoped_session,
) -> None:
    processing_config_dict = processing_config.model_dump()

    # handle code values
    code_values = {}
    if processing_config_dict["code"] is not None:
        code_values["code"] = processing_config_dict["code"]["code"]
        code_values["code_commit"] = processing_config_dict["code"]["commit"]

    # handle git values
    git_values = {}
    if processing_config_dict["git_config"] is not None:
        git_values = {
            f"git_{k}": v
            for k, v in processing_config_dict["git_config"].items()
        }

    await db.execute(
        update(ConfigModel)
        .where(ConfigModel.id == config_id)
        .values(
            {
                "name": processing_config_dict["name"],
                "output_schema": processing_config_dict["output_schema"][
                    "output_schema"
                ],
                "output_schema_commit": processing_config_dict[
                    "output_schema"
                ]["commit"],
                "user_provided_records": processing_config_dict[
                    "user_provided_records"
                ],
                **code_values,
                "previous_records": processing_config_dict["previous_records"],
                "current_records": processing_config_dict["current_records"],
                "bot_provided_records": processing_config_dict[
                    "bot_provided_records"
                ],
                **git_values,
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
    event: ProcessingMessage | ProcessEventMetadata,
    db: async_scoped_session,
) -> None:
    update_values = event.model_dump(
        exclude={"runs", "id", "timestamp", "start_timestamp"}
    )
    if isinstance(event, ProcessingMessage):
        event_history_raw = event.model_dump_json(include={"runs"})
        event_history = json.loads(event_history_raw)
        update_values["event_history"] = event_history["runs"]

    await db.execute(
        update(ProcessEventsModel)
        .where(ProcessEventsModel.id == event.id)
        .values(update_values)
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
            ProcessEventsModel.pr_uri,
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
                pr_uri=cast(Optional[str], event.pr_uri),
            )
        )

    return event_metadata


async def get_processing_event(
    config_id: UUID,
    run_id: UUID,
    db: async_scoped_session,
) -> Optional[ProcessingMessage]:
    event_result = await db.execute(
        select(ProcessEventsModel).where(
            ProcessEventsModel.config_id == config_id,
            ProcessEventsModel.id == run_id,
        )
    )
    event = event_result.scalars().one_or_none()
    processing_message = None
    if event is not None:
        processing_message = ProcessingMessage(
            id=cast(UUID, event.id),
            config_id=cast(UUID, event.config_id),
            input_count=cast(int, event.input_count),
            output_count=cast(int, event.output_count),
            status=cast(ProcessingStatus, event.status),
            runs=cast(list, event.event_history),
            start_timestamp=cast(str, event.created_at.isoformat()),
            timestamp=cast(str, event.updated_at.isoformat()),
            pr_uri=cast(Optional[str], event.pr_uri),
        )
    return processing_message
