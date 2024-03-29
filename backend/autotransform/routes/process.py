import asyncio
import logging
import random
import re
from typing import Optional, cast
from uuid import UUID, uuid4

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import async_scoped_session
from sse_starlette.sse import EventSourceResponse

from autotransform.autotransform_types import (
    BaseRecord,
    Code,
    DataType,
    ExampleRecord,
    ExecutionError,
    LogicError,
    ModelChat,
    ModelChatType,
    OpenAiChatInput,
    OutputSchemaError,
    ProcessEventMetadata,
    ProcessingConfig,
    ProcessingEvent,
    ProcessingMessage,
    ProcessingRunDebug,
    ProcessingStatus,
)
from autotransform.db.api import (
    get_processing_config,
    get_processing_message,
    insert_processing_event,
    save_processing_config,
    update_processing_event,
)
from autotransform.db.base import async_session_scope, get_session
from autotransform.file_api import read_data_partial, save_data
from autotransform.model import (
    model_client,
    openai_stream_response_generator,
    parse_json_output,
    send_openai_request,
)
from autotransform.task_manager import (
    processing_message_queue,
    processing_message_queue_lock,
    task_manager,
)
from autotransform.utils import settings

router = APIRouter(
    prefix="/process",
    tags=["process"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger(__name__)

MAX_PROCESSING_ATTEMPTS = 5
DATA_RECORDS_TO_DISPLAY = 10


class CodeQAException(Exception):
    pass


class SchemaNotFoundException(Exception):
    pass


class CodeNotFoundException(Exception):
    pass


class CodeExecutionException(Exception):
    pass


class MaxProcessAttemptsException(Exception):
    pass


class DataToProcess(BaseModel):
    records: list[dict]
    config_id: UUID


def create_qa_prompt(
    config: ProcessingConfig, record: dict
) -> list[ModelChat]:
    system_message = """
FACTS:
- You are an expert python developer
- You will be given the following information:
    - OUTPUT_FORMAT: a json schema representing the expected output format
    - EXAMPLES: A list of `input`s and their corresponding `output`s
    - INPUT: the `input` of the record you are being asked to produce the `ouput` for

RULES:
- Your task is to generate the `output` for the given `input` as a json object
- Only return a json object, nothing else
"""

    return [
        ModelChat(
            role=ModelChatType.system,
            content=system_message,
        ),
        ModelChat(
            role=ModelChatType.user,
            content=config.qa_prompt(record),
        ),
    ]


def _base_information_prompt() -> str:
    prompt = """- You will be given the following information:
    - **OUTPUT_FORMAT**: a json schema representing the expected output format
    - **EXAMPLES**: A list of `input`s and their corresponding `output`s
    - **POTENTIAL_INPUTS**: A list of `input`s that do not have corresponding `output`s but will be passed to your code
    - [OPTIONAL] **EXISTING_CODE**: A string of python code that you can use as a starting point. You can ignore this if you want to start from scratch
"""
    return prompt


def create_schema_change_prompt(config: ProcessingConfig) -> list[ModelChat]:
    system_message = f"""
### FACTS
- You are an expert python developer
{_base_information_prompt()}

### RULES
- Your task is to update the OUTPUT_SCHEMA given the provided information
- The OUTPUT_SCHEMA should be a valid jsonschema
- Only return a jsonschema, nothing else
"""
    return [
        ModelChat(
            role=ModelChatType.system,
            content=system_message,
        ),
        ModelChat(
            role=ModelChatType.user,
            content=config.prompt(),
        ),
    ]


def create_code_gen_prompt(config: ProcessingConfig) -> list[ModelChat]:
    system_message = f"""
### FACTS
- You are an expert python developer
- Your code will be run in a python 3.11 environment
{_base_information_prompt()}

### RULES
- Your task is to write a python function that:
    - has the signature `run_code(input: dict) -> dict`
    - accepts a dictionary called `input`
    - returns a dictionary called `output`
- Pay attention to all examples in the chat history, not just the most recent ones
- Do not use any external libraries
- All responses should include valid python code
- Only return the function, do not include any other code
"""

    return [
        ModelChat(
            role=ModelChatType.system,
            content=system_message,
        ),
        ModelChat(
            role=ModelChatType.user,
            content=config.prompt(),
        ),
    ]


def create_error_report(
    output_schema_errors: list[OutputSchemaError],
    execution_errors: list[ExecutionError],
    logic_errors: list[LogicError],
) -> tuple[bool, str]:
    passed = False
    report = ""
    if len(output_schema_errors) > 0:
        output_schema_errors_fmt = "\\\n".join(
            [error.prompt for error in output_schema_errors]
        )
        report += (
            f"\\\n**Output Schema Errors**:\\\n{output_schema_errors_fmt}"
        )

    if len(execution_errors) > 0:
        execution_errors_fmt = "\\\n".join(
            [error.prompt for error in execution_errors]
        )
        report += f"\\\n**Execution Errors**:\\\n{execution_errors_fmt}"
    if len(logic_errors) > 0:
        logic_errors_fmt = "\\\n".join(
            [error.prompt for error in logic_errors]
        )
        report += f"\\\n**Logic Errors**:\\\n{logic_errors_fmt}"

    if not report:
        passed = True
        report = "No errors found, code is ready for use"

    return passed, report


async def generate_code(
    config_id: UUID,
    run_id: UUID,
    chat: list[ModelChat],
) -> tuple[list[ModelChat], Code]:
    logger.info("Generating code for config %s", config_id)
    openai_chat_input = OpenAiChatInput(
        messages=chat,
        stream=True,
    )
    content = ""
    async for output in openai_stream_response_generator(
        model_client, openai_chat_input
    ):
        if "error" in output:
            raise CodeNotFoundException()  # TODO: better error handling
        else:
            content = output["content"]
            async with processing_message_queue_lock:
                processing_message_queue[config_id].add_run(
                    run_id, code=content
                )
    chat.append(
        ModelChat(
            role=ModelChatType.assistant,
            content=content,
        )
    )
    groups = re.search(r"```python(.*)```", content, re.DOTALL)
    if groups is None:
        raise CodeNotFoundException()
    code = groups.group(1).strip()

    logger.info("Generated code for config %s", config_id)
    return chat, Code(code=code)


def _execute_code(
    code: Code,
    record: dict,
) -> dict:
    code_to_run = f"""
import jsonschema
{code.code}
code_output = run_code(code_input)
"""
    _locals = {"code_input": record}
    exec(code_to_run, _locals, _locals)
    result = _locals["code_output"]
    return result


def run_code(
    code: Code,
    output_schema: dict,
    record: dict,
) -> tuple[dict, Optional[str], Optional[str]]:
    output = {}
    execution_error = None
    output_schema_error = None
    try:
        output = _execute_code(code, record)
        try:
            jsonschema.validate(output, output_schema)
        except jsonschema.ValidationError as e:
            output_schema_error = str(e)
    except Exception as e:
        execution_error = str(e)

    return output, output_schema_error, execution_error


async def run_checks(
    config: ProcessingConfig,
    code: Code,
    config_id: UUID,
    run_id: UUID,
) -> tuple[bool, str]:
    logger.info("Running checks for config")
    output_schema_errors: list[OutputSchemaError] = []
    execution_errors: list[ExecutionError] = []
    logic_errors: list[LogicError] = []
    for record in config.potential_inputs:
        _, output_schema_error, execution_error = run_code(
            code, config.output_schema, record.input
        )
        if output_schema_error is not None:
            output_schema_errors.append(
                OutputSchemaError(record=record, error=output_schema_error)
            )
        if execution_error is not None:
            execution_errors.append(
                ExecutionError(record=record, error=execution_error)
            )

    for record in config.examples:
        output, output_schema_error, execution_error = run_code(
            code, config.output_schema, record.input
        )
        if output_schema_error is not None:
            output_schema_errors.append(
                OutputSchemaError(record=record, error=output_schema_error)
            )
        if execution_error is not None:
            execution_errors.append(
                ExecutionError(record=record, error=execution_error)
            )
        elif output != record.output:
            logic_errors.append(
                LogicError(
                    record=record,
                    actual_output=output,
                    expected_output=record.output,
                )
            )

    async with processing_message_queue_lock:
        processing_message_queue[config_id].add_run(
            run_id,
            output_schema_errors=output_schema_errors,
            execution_errors=execution_errors,
            logic_errors=logic_errors,
        )

    passed, error_report = create_error_report(
        output_schema_errors, execution_errors, logic_errors
    )
    return passed, error_report


async def update_schema(
    chat: list[ModelChat],
) -> tuple[dict, list[ModelChat]]:
    openai_chat_input = OpenAiChatInput(messages=chat, stream=True)
    content = ""
    async for output in openai_stream_response_generator(
        model_client, openai_chat_input
    ):
        if "error" in output:
            raise SchemaNotFoundException()  # TODO: better error handling
        else:
            content = output["content"]
    chat.append(
        ModelChat(
            role=ModelChatType.assistant,
            content=content,
        )
    )
    output_schema = parse_json_output(content)

    return output_schema, chat


async def generate_and_test_code(
    config_id: UUID,
    config: ProcessingConfig,
) -> Code:
    code_chat = create_code_gen_prompt(config)
    schema_chat = None
    error_report = None
    schema_changed = False
    passed = False
    attempts = 0
    while not passed:
        attempts += 1
        run_id = uuid4()
        logger.info("Starting run %s for config %s", run_id, config_id)

        # handle schema changes
        if error_report is not None and "Output Schema Errors" in error_report:
            if schema_chat is None:
                schema_chat = create_schema_change_prompt(config)
            schema_chat.append(
                ModelChat(
                    role=ModelChatType.user,
                    content=error_report,
                )
            )
            new_schema, schema_chat = await update_schema(schema_chat)

            if not schema_changed and new_schema != config.output_schema:
                schema_changed = True

            # reset code chat if schema is changed
            config.output_schema = new_schema
            code_chat = create_code_gen_prompt(config)

        # ensure that once a schema has changed it shows up in all run displays
        if schema_changed:
            async with processing_message_queue_lock:
                processing_message_queue[config_id].add_run(
                    run_id,
                    output_schema=config.output_schema,
                )

        # generate code and checks
        code_chat, code = await generate_code(config_id, run_id, code_chat)
        passed, error_report = await run_checks(
            config, code, config_id, run_id
        )

        # add debug information
        processing_debug = ProcessingRunDebug(
            code_chat=code_chat,
            schema_chat=schema_chat,
        )

        # cleanup chat and run status
        code_chat.append(
            ModelChat(
                role=ModelChatType.user,
                content=error_report,
            )
        )

        # update processing run
        async with processing_message_queue_lock:
            processing_message_queue[config_id].add_run(
                run_id,
                processing_debug=processing_debug,
            )
            if not passed:
                processing_message_queue[config_id].run_failed()

        if not passed and attempts >= MAX_PROCESSING_ATTEMPTS:
            raise MaxProcessAttemptsException()
    return code


async def qa_code_output(
    record: dict,
    code_output: dict,
    config: ProcessingConfig,
) -> tuple[bool, dict, list[ModelChat]]:
    chat = create_qa_prompt(config, record)
    openai_chat_input = OpenAiChatInput(messages=chat)
    response = await send_openai_request(
        model_client,
        openai_chat_input.data,
        "chat/completions",
    )
    # parse json
    raw_output = response["choices"][0]["message"]["content"]
    model_output = parse_json_output(raw_output)
    chat.append(
        ModelChat(
            role=ModelChatType.assistant,
            content=raw_output,
        )
    )

    return model_output == code_output, model_output, chat


def _check_schema_execution_errors(
    output_schema_error: Optional[str],
    execution_error: Optional[str],
    record: BaseRecord,
    config_id: UUID,
    code: str,
) -> None:
    if output_schema_error is not None or execution_error is not None:
        output_schema_errors = (
            None
            if output_schema_error is None
            else [OutputSchemaError(record=record, error=output_schema_error)]
        )
        execution_errors = (
            None
            if execution_error is None
            else [ExecutionError(record=record, error=execution_error)]
        )

        run_id = uuid4()
        logger.info("Adding run %s for schema or execution error", run_id)
        processing_message_queue[config_id].add_run(
            run_id,
            code=code,
            output_schema_errors=output_schema_errors,
            execution_errors=execution_errors,
        )
        raise CodeExecutionException(output_schema_error or execution_error)


async def _check_logic_error(
    record: BaseRecord,
    actual_output: dict,
    config: ProcessingConfig,
    qa_records_run: int,
    record_to_process_index: int,
    record_count: int,
):
    if random.random() < config.code_qa.qa_pct or (
        qa_records_run < config.code_qa.min_qa
        and record_count - record_to_process_index <= config.code_qa.min_qa
    ):
        qa_records_run += 1
        passed, bot_output, qa_chat = await qa_code_output(
            record.input, actual_output, config
        )
        if config.bot_provided_records is None:
            config.bot_provided_records = []
        # remove from current records
        if config.current_records is not None:
            config.current_records.remove(record)

        config.bot_provided_records.append(
            ExampleRecord(
                input=record.input,
                output=bot_output,
            )
        )
        if passed is False:
            run_id = uuid4()
            logger.info("Adding run %s for logic error", run_id)
            processing_message_queue[config.config_id].add_run(
                run_id,
                code=cast(Code, config.code).markdown,
                logic_errors=[
                    LogicError(
                        record=record,
                        actual_output=actual_output,
                        expected_output=bot_output,
                    )
                ],
                processing_debug=(
                    ProcessingRunDebug(qa_chat=qa_chat)
                    if settings.processing_debug
                    else None
                ),
            )
            raise CodeQAException()


async def execute_data_processing(
    config: ProcessingConfig, data: DataToProcess
) -> None:
    try:
        if config.code is None:
            config.code = await generate_and_test_code(
                data.config_id,
                config,
            )

        # execute code
        outputs: list[dict] = []
        qa_records_run: int = 0
        record_to_process_index: int = 0
        while record_to_process_index < len(data.records):
            record = BaseRecord(input=data.records[record_to_process_index])
            config.add_current_record(record)
            try:
                output, output_schema_error, execution_error = run_code(
                    config.code, config.output_schema, record.input
                )
                _check_schema_execution_errors(
                    output_schema_error,
                    execution_error,
                    record,
                    config.config_id,
                    config.code.markdown,
                )
                await _check_logic_error(
                    record,
                    output,
                    config,
                    qa_records_run,
                    record_to_process_index,
                    len(data.records),
                )
                outputs.append(output)
                record_to_process_index += 1
            except Exception as e:
                if isinstance(e, MaxProcessAttemptsException):
                    raise e
                logger.info("Error processing record %s: %s", record, e)
                config.code = await generate_and_test_code(
                    data.config_id,
                    config,
                )
                record_to_process_index = 0
        passed = True
    except Exception:
        logger.exception("Error processing data")
        passed = False

    async with processing_message_queue_lock:
        if passed:
            processing_message_queue[data.config_id].complete(outputs=outputs)
            await save_data(
                outputs,
                data.config_id,
                processing_message_queue[data.config_id].id,
                DataType.output,
            )
        else:
            processing_message_queue[data.config_id].fail()

    async with async_session_scope() as db:
        if passed:
            await save_processing_config(data.config_id, config, db)
        await update_processing_event(
            processing_message_queue[data.config_id], db
        )

        await db.commit()


@router.post("/start", response_model=ProcessEventMetadata)
async def processing_start(
    request: DataToProcess,
    db: async_scoped_session = Depends(get_session),
) -> ProcessEventMetadata:
    config = await get_processing_config(request.config_id, db)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Config not found",
        )

    task_manager.add_task(
        str(request.config_id),
        execute_data_processing,
        config,
        request,
    )

    event = await insert_processing_event(
        config_id=request.config_id,
        input_count=len(request.records),
        db=db,
    )

    async with processing_message_queue_lock:
        processing_message_queue[request.config_id] = ProcessingMessage(
            id=cast(UUID, event.id),
            config_id=cast(UUID, event.config_id),
            runs=[],
            input_count=cast(int, event.input_count),
            status=cast(ProcessingStatus, event.status),
        )

    await save_data(
        request.records,
        request.config_id,
        cast(UUID, event.id),
        DataType.input,
    )

    await db.commit()

    return processing_message_queue[request.config_id].metadata


@router.post("/stop/{config_id}", status_code=204)
async def processing_stop(config_id: UUID):
    task_manager.cancel_task(str(config_id))
    async with processing_message_queue_lock:
        processing_message_queue[config_id].stop()

    async with async_session_scope() as db:
        await update_processing_event(processing_message_queue[config_id], db)
        await db.commit()
    return Response(status_code=204)


@router.get("/status/{config_id}/{run_id}")
async def processing_status(
    config_id: UUID,
    run_id: UUID,
    db: async_scoped_session = Depends(get_session),
):
    async def event_generator():
        input_data = await read_data_partial(
            config_id, run_id, DataType.input, DATA_RECORDS_TO_DISPLAY
        )
        output_data = None
        while True:
            async with processing_message_queue_lock:
                processing_message = processing_message_queue.get(config_id)
                if (
                    processing_message is None
                    or processing_message.id != run_id
                ):
                    processing_message = await get_processing_message(
                        config_id, run_id, db
                    )
            if processing_message is not None:
                if processing_message.output_count:
                    output_data = await read_data_partial(
                        config_id,
                        run_id,
                        DataType.output,
                        DATA_RECORDS_TO_DISPLAY,
                    )
                data = ProcessingEvent(
                    message=processing_message,
                    input_data=input_data,
                    output_data=output_data,
                )

                yield {"data": data.model_dump_json()}

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
