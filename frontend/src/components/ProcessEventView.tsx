import { Button } from "@/components/ui/button";
import {
  ExecutionError,
  LogicError,
  ModelChat,
  OutputSchemaError,
  ProcessingDebug,
  ProcessingEvent,
  ProcessingRun,
  ProcessingStatus,
} from "../types";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  StopIcon,
} from "@radix-ui/react-icons";
import JsonView from "react18-json-view";
import ReactJsonViewCompare from "react-json-view-compare";
import { useEffect, useState } from "react";
import {
  CodeView,
  CustomMarkdown,
  DataDisplay,
  ExternalGitLink,
  OutputSchemaView,
  StatusDisplay,
} from "./DisplayUtils";
import { loadAndFormatDate } from "../utils/date";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useNavigate } from "react-router-dom";
import { stopProcess } from "../utils/apiCalls";
import { badgeVariants } from "@/components/ui/badge";

const ProcessStatus = (props: {
  status: ProcessingStatus;
  timestamp: string;
}) => {
  let message: JSX.Element;
  let fmtTimestamp = loadAndFormatDate(props.timestamp);
  switch (props.status) {
    case "running":
      message = (
        <div className="text-xs text-blue-500">{`Last updated: ${fmtTimestamp}`}</div>
      );
      break;
    case "completed":
      message = (
        <div className="text-xs text-green-500">{`Completed: ${fmtTimestamp}`}</div>
      );
      break;
    case "failed":
      message = (
        <div className="text-xs text-red-500">{`Failed: ${fmtTimestamp}`}</div>
      );
      break;
    case "stopped":
      message = (
        <div className="text-xs text-gray-500">{`Stopped: ${fmtTimestamp}`}</div>
      );
      break;
    case "awaiting_review":
      message = (
        <div className="text-xs text-yellow-500">{`Awaiting review: ${fmtTimestamp}`}</div>
      );
      break;
  }

  return message;
};

const ExecutionErrorDisplay = (props: { executionError: ExecutionError }) => {
  return (
    <>
      <JsonView src={props.executionError.record} />
      <div className="text-red-500">
        <pre>{props.executionError.error}</pre>
      </div>
    </>
  );
};

const OutputSchemaErrorView = (props: {
  outputSchemaErrors: OutputSchemaError[];
}) => {
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-medium">Output Schema Errors</h3>
      {props.outputSchemaErrors.map((error, index) => (
        <ExecutionErrorDisplay key={index} executionError={error} />
      ))}
    </div>
  );
};

const ExecutionErrorView = (props: { executionErrors: ExecutionError[] }) => {
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-medium">Execution Errors</h3>
      {props.executionErrors.map((error, index) => (
        <ExecutionErrorDisplay key={index} executionError={error} />
      ))}
    </div>
  );
};

const LogicErrorDisplay = (props: { logicError: LogicError }) => {
  return (
    <>
      <JsonView src={props.logicError.record} />
      <ReactJsonViewCompare
        oldData={props.logicError.actual_output}
        newData={props.logicError.expected_output}
      />
    </>
  );
};

const LogicErrorView = (props: { logicErrors: LogicError[] }) => {
  return (
    <div className="space-y-2">
      <h3 className="text-lg font-medium">Logic Errors</h3>
      {props.logicErrors.map((error, index) => (
        <LogicErrorDisplay key={index} logicError={error} />
      ))}
    </div>
  );
};

const DebugChatView = (props: { chat: ModelChat[]; title: string }) => {
  return (
    <AccordionItem value={props.title}>
      <AccordionTrigger>{props.title}</AccordionTrigger>
      <AccordionContent>
        <div className="space-y-2">
          <div>
            {props.chat.map((chat, index) => (
              <div key={index}>
                <h5 className="text-gray-500 mb-2">
                  {chat.role.toUpperCase()}
                </h5>
                <CustomMarkdown content={chat.content} />
                {index < props.chat.length - 1 && (
                  <Separator className="mt-5 mb-5" />
                )}
              </div>
            ))}
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
};

const DebugRunView = (props: { processingDebug: ProcessingDebug }) => {
  return (
    <>
      <h3 className="text-lg font-medium">Debug</h3>
      <Accordion type="single" collapsible className="w-[660px]">
        {props.processingDebug.schema_chat && (
          <DebugChatView
            chat={props.processingDebug.schema_chat}
            title="Schema Chat"
          />
        )}
        {props.processingDebug.code_chat && (
          <DebugChatView
            chat={props.processingDebug.code_chat}
            title="Code Chat"
          />
        )}
        {props.processingDebug.qa_chat && (
          <DebugChatView chat={props.processingDebug.qa_chat} title="QA Chat" />
        )}
      </Accordion>
    </>
  );
};

const RunView = (props: {
  processingRun: ProcessingRun;
  runIndex: number;
  numRuns: number;
  setRunIndex: (runIndex: number) => void;
}) => {
  return (
    <div className="space-y-5">
      {props.numRuns && props.numRuns > 1 && (
        <>
          <div className="text-lg font-medium">{`Step ${props.runIndex + 1} / ${
            props.numRuns
          }`}</div>
          <div className="space-x-2 flex items-center">
            <Button
              disabled={props.runIndex === 0}
              onClick={() => props.setRunIndex(props.runIndex - 1)}
              variant="outline"
              size="sm"
            >
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            <Button
              disabled={props.runIndex === props.numRuns - 1}
              onClick={() => props.setRunIndex(props.runIndex + 1)}
              variant="outline"
              size="sm"
            >
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}
      <ProcessStatus
        status={props.processingRun.status}
        timestamp={props.processingRun.timestamp}
      />
      {props.processingRun.output_schema !== null && (
        <OutputSchemaView output_schema={props.processingRun.output_schema} />
      )}
      <CodeView code={props.processingRun.code} />
      {props.processingRun.output_schema_errors.length > 0 && (
        <OutputSchemaErrorView
          outputSchemaErrors={props.processingRun.output_schema_errors}
        />
      )}
      {props.processingRun.execution_errors.length > 0 && (
        <ExecutionErrorView
          executionErrors={props.processingRun.execution_errors}
        />
      )}
      {props.processingRun.logic_errors.length > 0 && (
        <LogicErrorView logicErrors={props.processingRun.logic_errors} />
      )}
      {props.processingRun.debug && (
        <DebugRunView processingDebug={props.processingRun.debug} />
      )}
    </div>
  );
};

export const ProcessEventView = (props: {
  configId: string;
  processingEvent: ProcessingEvent;
  setProcessingEvent: (processingEvent: ProcessingEvent) => void;
}) => {
  const navigator = useNavigate();
  const [runIndex, setRunIndex] = useState<number>(0);

  useEffect(() => {
    setRunIndex(Math.max(props.processingEvent.message.runs.length - 1, 0));
  }, [props.processingEvent.message.id]);

  useEffect(() => {
    if (props.processingEvent.message.status === "running") {
      setRunIndex(Math.max(props.processingEvent.message.runs.length - 1, 0));
    }
  }, [props.processingEvent.message.runs.length]);

  const onClickStop = async () => {
    if (props.processingEvent.message.status === "running") {
      await stopProcess(props.configId, props.processingEvent.message.id);
    }
  };

  return (
    <div className="space-y-5">
      <Button
        variant="secondary"
        onClick={() => navigator(`/?configId=${props.configId}`)}
      >
        Back to History
      </Button>
      <div className="text-lg font-medium">
        {props.processingEvent.message.id}
      </div>
      <div className="flex items-center space-x-2">
        <StatusDisplay status={props.processingEvent.message.status} />
        {props.processingEvent.message.status === "running" && (
          <Button variant="destructive" onClick={onClickStop}>
            <StopIcon className="mr-2 h-4 w-4" />
            Stop
          </Button>
        )}
        {props.processingEvent.message.pr_uri && (
          <ExternalGitLink
            url={props.processingEvent.message.pr_uri}
            text="View PR"
          />
        )}
      </div>
      <div className="text-xs text-muted-foreground">
        {loadAndFormatDate(props.processingEvent.message.timestamp)}
      </div>
      <DataDisplay
        title="Input"
        recordCount={props.processingEvent.message.input_count}
        dataToDisplay={props.processingEvent.input_data}
        downloadItems={{
          configId: props.configId,
          runId: props.processingEvent.message.id,
          recordType: "input",
        }}
      />
      {props.processingEvent.output_data && (
        <DataDisplay
          title="Output"
          recordCount={props.processingEvent.message.output_count!}
          dataToDisplay={props.processingEvent.output_data}
          downloadItems={{
            configId: props.configId,
            runId: props.processingEvent.message.id,
            recordType: "output",
          }}
        />
      )}
      {props.processingEvent.message.runs.length > 0 && (
        <RunView
          processingRun={props.processingEvent.message.runs[runIndex]}
          runIndex={runIndex}
          numRuns={props.processingEvent.message.runs.length}
          setRunIndex={setRunIndex}
        />
      )}
    </div>
  );
};
