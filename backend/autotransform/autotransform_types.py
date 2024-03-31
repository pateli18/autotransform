import json
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from functools import cached_property
from hashlib import blake2s
from typing import Generic, Literal, Optional, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel, Field

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
    awaiting_review = "awaiting_review"


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


class OutputSchema(BaseModel):
    output_schema: dict
    commit: Optional[str] = None


class Code(BaseModel):
    code: str
    commit: Optional[str] = None


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


class GitConfig(BaseModel):
    owner: str
    repo_name: str
    primary_branch_name: str
    block_human_review: bool


class CodeQa(BaseModel):
    qa_pct: float = 0.2
    min_qa: int = 1


class ProcessingConfig(BaseModel):
    config_id: UUID
    name: str
    code: Optional[Code] = None
    previous_records: Optional[list[BaseRecord]] = None
    current_records: Optional[list[BaseRecord]] = None
    output_schema: OutputSchema
    user_provided_records: Optional[list[ExampleRecord]] = None
    bot_provided_records: Optional[list[ExampleRecord]] = None
    git_config: Optional[GitConfig] = None
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
    user_provided_records: Optional[list[ExampleRecord]] = None
    git_config: Optional[GitConfig] = None


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
    output_schema: Optional[OutputSchema]
    code: Code
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
    output_count: Optional[int] = None
    status: ProcessingStatus
    start_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    pr_uri: Optional[str] = None


class ProcessingMessage(ProcessEventMetadata):
    runs: list[ProcessingRun]

    def _upsert_run(
        self,
        run: ProcessingRun,
        output_schema: Optional[dict],
        code: Optional[str],
        output_schema_errors: Optional[list[OutputSchemaError]],
        execution_errors: Optional[list[ExecutionError]],
        logic_errors: Optional[list[LogicError]],
        output_schema_commit_uri: Optional[str],
        code_commit_uri: Optional[str],
        processing_debug: Optional[ProcessingRunDebug],
    ) -> ProcessingRun:
        if output_schema is not None:
            run.output_schema = OutputSchema(output_schema=output_schema)
        if code is not None:
            run.code.code = code
        if output_schema_errors is not None:
            run.output_schema_errors += output_schema_errors
        if execution_errors is not None:
            run.execution_errors += execution_errors
        if logic_errors is not None:
            run.logic_errors += logic_errors
        if (
            output_schema_commit_uri is not None
            and run.output_schema is not None
        ):
            run.output_schema.commit = output_schema_commit_uri
        if code_commit_uri is not None:
            run.code.commit = code_commit_uri
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
        code_commit_uri: Optional[str] = None,
        output_schema_commit_uri: Optional[str] = None,
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
                    output_schema_commit_uri,
                    code_commit_uri,
                    processing_debug,
                )
            new_runs.append(run)

        if not run_found:
            new_runs.append(
                self._upsert_run(
                    ProcessingRun(
                        run_id=run_id,
                        output_schema=None,
                        code=Code(code=""),
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
                    output_schema_commit_uri,
                    code_commit_uri,
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

    def await_review(self, output_count: int) -> None:
        self.output_count = output_count
        self._cleanup(ProcessingStatus.awaiting_review)

    def complete(self, output_count: int) -> None:
        self.output_count = output_count
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
            pr_uri=self.pr_uri,
        )


class ProcessingEvent(BaseModel):
    message: ProcessingMessage
    input_data: list[dict]
    output_data: Optional[list[dict]]


T = TypeVar("T")


class GitClient(Generic[T]):
    def __init__(
        self,
        owner: str,
        repo_name: str,
        primary_branch_name: str,
        block_human_review: bool,
        service_name: str,
        service_id: UUID,
        event_id: Optional[UUID],
    ):
        self.owner = owner
        self.repo_name = repo_name
        self.primary_branch_name = primary_branch_name
        self.block_human_review = block_human_review
        self.service_name = service_name
        self.service_id = service_id
        self.event_id = event_id
        self.base_file_path = f"{service_name}-{str(service_id)[:4]}"
        self.output_schema_filepath = (
            f"{self.base_file_path}/output_schema.json"
        )
        self.code_filepath = f"{self.base_file_path}/service.py"

        if event_id is None:
            self.branch_name = None
        else:
            self.branch_name = f"{service_name}-{event_id}"

    def commit(
        self,
        file_content: str,
        file_path: str,
        message: str,
        branch_name: Optional[str] = None,
    ) -> str:
        branch_to_use = self.branch_name or branch_name
        if branch_to_use is None:
            raise ValueError("Branch name is not set")
        self._create_branch(branch_to_use)
        commit_uri = self._upsert_file(
            file_content, file_path, message, branch_to_use
        )
        return commit_uri

    def complete(self, execution_passed: bool) -> tuple[str, bool]:
        if self.branch_name is None:
            raise ValueError("Branch name is not set")
        merged = False
        title = f"AutoTransform [{'PASS' if execution_passed else 'FAIL'}] {self.service_name} event={self.event_id}"
        body = f"You can view the code generation process and results [here]({settings.base_url}/run/{self.service_id}/{self.event_id})"
        pr, uri = self._create_pull_request(title, body, self.branch_name)
        if not self.block_human_review and execution_passed:
            self._merge_pull_request(pr)
            merged = True
        return uri, merged

    def check_pr_status(self) -> ProcessingStatus:
        if self.branch_name is None:
            raise ValueError("Branch name is not set")
        return self._check_pr_status(self.branch_name)

    @abstractmethod
    def get_latest_assets(self) -> tuple[OutputSchema, Optional[Code]]:
        raise NotImplementedError()

    @abstractmethod
    def _create_branch(self, branch_name: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _upsert_file(
        self,
        file_content: str,
        file_path: str,
        message: str,
        branch_name: str,
    ) -> str:
        raise NotImplementedError()

    @abstractmethod
    def _create_pull_request(
        self,
        title: str,
        body: str,
        branch_name: str,
    ) -> tuple[T, str]:
        raise NotImplementedError()

    @abstractmethod
    def _merge_pull_request(self, pull_request: T) -> None:
        raise NotImplementedError()

    @abstractmethod
    def _check_pr_status(self, branch_name: str) -> ProcessingStatus:
        raise NotImplementedError()


class ConfigResponse(BaseModel):
    history: list[ProcessEventMetadata]
    config: ProcessingConfig
