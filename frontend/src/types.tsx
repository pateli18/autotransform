export interface UnlabeledExample {
  input: object;
}

export interface LabeledExample extends UnlabeledExample {
  output: object;
}

export type ProcessingStatus =
  | "running"
  | "completed"
  | "failed"
  | "stopped"
  | "awaiting_review";

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

export interface Code {
  code: string;
  commit: string | null;
  markdown: string;
}

export interface OutputSchema {
  output_schema: object;
  commit: string | null;
}

export interface ProcessingRun {
  run_id: string;
  output_schema: OutputSchema;
  code: Code;
  output_schema_errors: OutputSchemaError[];
  execution_errors: ExecutionError[];
  logic_errors: LogicError[];
  timestamp: string;
  status: ProcessingStatus;
  debug: ProcessingDebug | null;
  commit_uri: string | null;
}

export interface ProcessEventMetadata {
  id: string;
  config_id: string;
  input_count: number;
  output_count: number | null;
  status: ProcessingStatus;
  timestamp: string;
  pr_uri: string | null;
}

export interface ProcessingMessage extends ProcessEventMetadata {
  runs: ProcessingRun[];
}

export interface ConfigMetadata {
  config_id: string;
  name: string;
  last_updated: string;
}

export interface GitConfig {
  owner: string;
  repo_name: string;
  primary_branch_name: string;
  block_human_review: boolean;
}

export interface Config {
  config_id: string;
  name: string;
  code: Code | null;
  output_schema: OutputSchema;
  previous_records: UnlabeledExample[] | null;
  current_records: UnlabeledExample[] | null;
  user_provided_records: LabeledExample[];
  bot_provided_records: LabeledExample[] | null;
  git_config: GitConfig | null;
}

export interface ProcessingEvent {
  message: ProcessingMessage;
  input_data: object[];
  output_data: object[] | null;
}
