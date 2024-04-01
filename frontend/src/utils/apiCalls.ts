import {
  Config,
  ConfigMetadata,
  GitConfig,
  LabeledExample,
  ProcessEventMetadata,
} from "src/types";
import Ajax from "./Ajax";

export const parseSchema = async (
  inputSchema: string | null,
  examples: LabeledExample[] | null
) => {
  let response = null;
  try {
    response = await Ajax.req<Object>({
      url: "/api/v1/config/parse-schema",
      method: "POST",
      body: {
        input_schema: inputSchema,
        examples: examples,
      },
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const upsertConfig = async (
  configId: string | null,
  name: string,
  outputSchema: Object,
  labeledRecords: LabeledExample[],
  gitConfig: GitConfig | null
) => {
  let response = null;
  try {
    response = await Ajax.req<{ config_id: string }>({
      url: "/api/v1/config/upsert",
      method: "POST",
      body: {
        config_id: configId,
        name: name,
        output_schema: outputSchema,
        user_provided_records: labeledRecords,
        git_config: gitConfig,
      },
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const processData = async (
  records: Record<any, any>[],
  configId: string
) => {
  let response = null;
  try {
    response = await Ajax.req<ProcessEventMetadata>({
      url: `/api/v1/process/start`,
      method: "POST",
      body: {
        records: records,
        config_id: configId,
      },
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const stopProcess = async (configId: string, runId: string) => {
  let response = false;
  try {
    await Ajax.req({
      url: `/api/v1/process/stop/${configId}/${runId}`,
      method: "POST",
      body: {},
    });
    response = true;
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const getAllConfigs = async () => {
  let response = null;
  try {
    response = await Ajax.req<ConfigMetadata[]>({
      url: `/api/v1/config/all`,
      method: "GET",
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};

export const getConfig = async (configId: string) => {
  let response = null;
  try {
    response = await Ajax.req<{
      config: Config;
      history: ProcessEventMetadata[];
    }>({
      url: `/api/v1/config/${configId}`,
      method: "GET",
    });
  } catch (e) {
    console.error(e);
  }
  return response;
};
