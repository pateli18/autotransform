export interface UnlabeledExample {
  input: object;
}

export interface LabeledExample extends UnlabeledExample {
  output: object;
}

export type ProcessingStatus = "running" | "completed" | "failed" | "stopped";

export interface OutputSchemaError {
  record: object;
  error: string;
}

export interface ExecutionError {
  record: object;
  error: string;
}

export interface LogicError {
  record: object;
  actual_output: object;
  expected_output: object;
}

export type ModelChatType = "system" | "user" | "assistant";

export interface ModelChat {
  role: ModelChatType;
  content: string;
}

export interface ProcessingDebug {
  schema_chat: ModelChat[] | null;
  code_chat: ModelChat[] | null;
  qa_chat: ModelChat[] | null;
}

export interface ProcessingRun {
  run_id: string;
  output_schema: object;
  code: string;
  output_schema_errors: OutputSchemaError[];
  execution_errors: ExecutionError[];
  logic_errors: LogicError[];
  timestamp: string;
  status: ProcessingStatus;
  debug: ProcessingDebug | null;
}

export interface ProcessingMessage {
  id: string;
  config_id: string;
  input_count: number;
  output_count: number | null;
  runs: ProcessingRun[];
  status: ProcessingStatus;
  timestamp: string;
  output: object[] | null;
}

export interface ConfigMetadata {
  config_id: string;
  name: string;
  last_updated: string;
}

interface Code {
  code: string;
  markdown: string;
}

export interface Config {
  id: string;
  name: string;
  code: Code | null;
  output_schema: object;
  previous_records: UnlabeledExample[] | null;
  current_records: UnlabeledExample[] | null;
  user_provided_records: LabeledExample[] | null;
  bot_provided_records: LabeledExample[] | null;
}

export interface ProcessEventMetadata {
  id: string;
  config_id: string;
  input_count: number;
  output_count: number | null;
  status: ProcessingStatus;
  timestamp: string;
}

export interface ProcessingEvent {
  message: ProcessingMessage;
  input_data: object[];
  output_data: object[] | null;
}
