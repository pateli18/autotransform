import json
from datetime import datetime
from enum import Enum
from functools import cached_property
from hashlib import blake2s
from typing import Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from autotransform.utils import settings


def encode_record(record: dict) -> str:
    return blake2s(json.dumps(record, sort_keys=True).encode()).hexdigest()[
        :16
    ]


class DataType(str, Enum):
    input = "input"
    output = "output"


class ProcessingStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class ToolChoiceFunction(BaseModel):
    name: str


class ToolChoiceObject(BaseModel):
    type: str = "function"
    function: ToolChoiceFunction


ToolChoice = Optional[Union[Literal["auto"], ToolChoiceObject]]


class ModelType(str, Enum):
    gpt4turbo = "gpt-4-turbo-preview"


class ModelChatType(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ModelChat(BaseModel):
    role: ModelChatType
    content: str


class ModelFunction(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[dict]


class Tool(BaseModel):
    type: str = "function"
    function: ModelFunction


OpenAiPromptReturnType = tuple[
    list[ModelChat], list[ModelFunction], ToolChoice
]


class OpenAiChatInput(BaseModel):
    messages: list[ModelChat]
    model: ModelType = ModelType.gpt4turbo
    max_tokens: Optional[int] = None
    n: int = 1
    temperature: float = 0.0
    stop: Optional[str] = None
    tools: Optional[list[Tool]] = None
    tool_choice: ToolChoice = None
    stream: bool = False
    logprobs: bool = False
    top_logprobs: Optional[int] = None

    @property
    def data(self) -> dict:
        exclusion = set()
        if self.tools is None:
            exclusion.add("tools")
        if self.tool_choice is None:
            exclusion.add("tool_choice")

        return self.model_dump(
            exclude=exclusion,
        )


class Code(BaseModel):
    code: str

    @cached_property
    def code_id(self) -> str:
        return blake2s(self.code.encode()).hexdigest()

    @computed_field
    @property
    def markdown(self) -> str:
        return f"```python\n{self.code}\n```"


class BaseRecord(BaseModel):
    input: dict

    @cached_property
    def record_id(self) -> str:
        return encode_record(self.input)

    @property
    def prompt(self) -> str:
        return f"_id_:`{self.record_id}` | _input_:`{self.input}`"


class ExampleRecord(BaseRecord):
    output: dict

    @property
    def prompt(self) -> str:
        return f"_id_:`{self.record_id}` | _input_:`{self.input}` | _output_:`{self.output}`"


class CodeQa(BaseModel):
    qa_pct: float = 0.2
    min_qa: int = 1


class ProcessingConfig(BaseModel):
    config_id: UUID
    name: str
    code: Optional[Code] = None
    previous_records: Optional[list[BaseRecord]] = None
    current_records: Optional[list[BaseRecord]] = None
    output_schema: dict
    user_provided_records: Optional[list[ExampleRecord]] = None
    bot_provided_records: Optional[list[ExampleRecord]] = None
    code_qa: CodeQa = Field(default_factory=CodeQa)

    def run_complete(self):
        # add in current records to previous records
        if self.previous_records is None:
            self.previous_records = []

        if self.current_records:
            self.previous_records += self.current_records

        # reset current records
        self.current_records = []

    @cached_property
    def current_record_lookup(self) -> set[str]:
        return {record.record_id for record in self.current_records or []}

    def add_current_record(self, record: BaseRecord) -> None:
        if self.current_records is None:
            self.current_records = []
        # check if record already exists
        if record.record_id not in self.current_record_lookup:
            self.current_records.append(record)
            self.current_record_lookup.add(record.record_id)

    def _cleanup_current_records(self) -> None:
        previous_record_lookup = {
            record.record_id for record in self.previous_records or []
        }
        new_previous_records = []
        if self.current_records is None:
            self.current_records = []
        for record in self.current_records:
            if record.record_id not in previous_record_lookup:
                new_previous_records.append(record)

    @property
    def potential_inputs(self) -> list[BaseRecord]:
        return (self.current_records or []) + (self.previous_records or [])

    @property
    def examples(self) -> list[ExampleRecord]:
        return (self.user_provided_records or []) + (
            self.bot_provided_records or []
        )

    @property
    def _base_prompt(self) -> str:
        fmt_examples = "\\\n".join([record.prompt for record in self.examples])

        message = f"""
**OUTPUT_FORMAT**: `{self.output_schema}`

**EXAMPLES**:

{fmt_examples}
"""
        return message

    def prompt(self, error_report: Optional[str] = None) -> str:
        fmt_potential_inputs = "\\".join(
            [record.prompt for record in self.potential_inputs]
        )
        message = f"""{self._base_prompt}

**POTENTIAL_INPUTS**:

{fmt_potential_inputs}
"""
        if self.code is not None:
            message += (
                f"\n**EXISTING_CODE**:\n```python\n{self.code.code}\n```"
            )

        if error_report:
            message += f"\n**LATEST SYSTEM RESULT**: `{error_report}`"

        return message

    def qa_prompt(self, record: dict) -> str:
        message = f"""{self._base_prompt}

INPUT: {record}
"""
        return message


class UpsertConfig(BaseModel):
    config_id: Optional[UUID] = None
    name: str
    output_schema: dict
    user_provided_records: Optional[list[ExampleRecord]]


class ConfigMetadata(BaseModel):
    config_id: UUID
    name: str
    last_updated: str


class OutputSchemaError(BaseModel):
    record: BaseRecord
    error: str

    @property
    def prompt(self) -> str:
        return f"*{self.record.record_id}* had a schema error `{self.error}`"


class ExecutionError(BaseModel):
    record: BaseRecord
    error: str

    @property
    def prompt(self) -> str:
        return f"*{self.record.record_id}* had error `{self.error}`"


class LogicError(BaseModel):
    record: BaseRecord
    actual_output: dict
    expected_output: dict

    @property
    def prompt(self) -> str:
        return f"*{self.record.record_id}* had output `{self.actual_output}` but the correct output is `{self.expected_output}`"


class ProcessingRunDebug(BaseModel):
    schema_chat: Optional[list[ModelChat]] = None
    code_chat: Optional[list[ModelChat]] = None
    qa_chat: Optional[list[ModelChat]] = None


class ProcessingRun(BaseModel):
    run_id: UUID
    output_schema: Optional[dict]
    code: str
    output_schema_errors: list[OutputSchemaError]
    execution_errors: list[ExecutionError]
    logic_errors: list[LogicError]
    timestamp: str
    status: ProcessingStatus
    debug: Optional[ProcessingRunDebug] = Field(
        None, exclude=not settings.processing_debug
    )


class ProcessEventMetadata(BaseModel):
    id: UUID
    config_id: UUID
    input_count: int
    output_count: Optional[int]
    status: ProcessingStatus
    timestamp: str


class ProcessingMessage(BaseModel):
    id: UUID
    config_id: UUID
    runs: list[ProcessingRun]
    input_count: int
    output_count: Optional[int] = None
    status: ProcessingStatus
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    output: Optional[list[dict]] = None

    def _upsert_run(
        self,
        run: ProcessingRun,
        output_schema: Optional[dict],
        code: Optional[str],
        output_schema_errors: Optional[list[OutputSchemaError]],
        execution_errors: Optional[list[ExecutionError]],
        logic_errors: Optional[list[LogicError]],
        processing_debug: Optional[ProcessingRunDebug],
    ) -> ProcessingRun:
        if output_schema is not None:
            run.output_schema = output_schema
        if code is not None:
            run.code = code
        if output_schema_errors is not None:
            run.output_schema_errors += output_schema_errors
        if execution_errors is not None:
            run.execution_errors += execution_errors
        if logic_errors is not None:
            run.logic_errors += logic_errors
        if processing_debug is not None:
            run.debug = processing_debug
        run.timestamp = datetime.now().isoformat()
        return run

    def add_run(
        self,
        run_id: UUID,
        output_schema: Optional[dict] = None,
        code: Optional[str] = None,
        output_schema_errors: Optional[list[OutputSchemaError]] = None,
        execution_errors: Optional[list[ExecutionError]] = None,
        logic_errors: Optional[list[LogicError]] = None,
        processing_debug: Optional[ProcessingRunDebug] = None,
    ) -> None:
        new_runs = []
        run_found = False
        for run in self.runs:
            if run.run_id == run_id:
                run_found = True
                run = self._upsert_run(
                    run,
                    output_schema,
                    code,
                    output_schema_errors,
                    execution_errors,
                    logic_errors,
                    processing_debug,
                )
            new_runs.append(run)

        if not run_found:
            new_runs.append(
                self._upsert_run(
                    ProcessingRun(
                        run_id=run_id,
                        output_schema=None,
                        code="",
                        output_schema_errors=[],
                        execution_errors=[],
                        logic_errors=[],
                        timestamp=datetime.now().isoformat(),
                        status=ProcessingStatus.running,
                        debug=None,
                    ),
                    output_schema,
                    code,
                    output_schema_errors,
                    execution_errors,
                    logic_errors,
                    processing_debug,
                )
            )
        self.runs = new_runs

    def _run_status_update(self):
        if (
            len(self.runs) > 0
            and self.runs[-1].status == ProcessingStatus.running
        ):
            self.runs[-1].status = self.status
            self.runs[-1].timestamp = self.timestamp

    def _cleanup(self, status: ProcessingStatus) -> None:
        self.status = status
        self.timestamp = datetime.now().isoformat()
        self._run_status_update()

    def stop(self) -> None:
        self._cleanup(ProcessingStatus.stopped)

    def complete(self, outputs: list[dict]) -> None:
        self.output = outputs
        self.output_count = len(outputs)
        self._cleanup(ProcessingStatus.completed)

    def fail(self) -> None:
        self._cleanup(ProcessingStatus.failed)

    def run_failed(self) -> None:
        if (
            len(self.runs) > 0
            and self.runs[-1].status == ProcessingStatus.running
        ):
            self.runs[-1].status = ProcessingStatus.failed
            self.runs[-1].timestamp = datetime.now().isoformat()

    @property
    def metadata(self) -> ProcessEventMetadata:
        return ProcessEventMetadata(
            id=self.id,
            config_id=self.config_id,
            input_count=self.input_count,
            output_count=self.output_count,
            status=self.status,
            timestamp=self.timestamp,
        )


class ProcessingEvent(BaseModel):
    message: ProcessingMessage
    input_data: list[dict]
    output_data: Optional[list[dict]]
