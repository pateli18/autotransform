import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useNavigate } from "react-router-dom";
import { ProcessEventMetadata } from "src/types";
import { loadAndFormatDate } from "../utils/date";
import {
  ExternalGitLink,
  ReprocessButton,
  StatusDisplay,
} from "./DisplayUtils";

const ProcessEventMetadataView = (props: { event: ProcessEventMetadata }) => {
  const navigate = useNavigate();
  return (
    <div
      className="space-x-5 hover:bg-gray-100 p-3 rounded-lg hover:cursor-pointer"
      onClick={() =>
        navigate(`/run/${props.event.config_id}/${props.event.id}`)
      }
    >
      <StatusDisplay status={props.event.status} />
      <span className="font-bold">{props.event.id}</span>
      <span className="text-muted-foreground">
        {loadAndFormatDate(props.event.timestamp)}
      </span>
      {props.event.output_count && (
        <Badge variant="secondary">
          {props.event.output_count}{" "}
          {props.event.output_count > 1 ? "Records" : "Record"}
        </Badge>
      )}
      {props.event.pr_uri && (
        <ExternalGitLink url={props.event.pr_uri} text="View PR" />
      )}
      {props.event.status !== "running" && (
        <ReprocessButton
          configId={props.event.config_id}
          runId={props.event.id}
        />
      )}
    </div>
  );
};

export const ProcessHistoryView = (props: {
  processEvents: ProcessEventMetadata[];
}) => {
  return (
    <div>
      {props.processEvents.map((event, i) => (
        <div key={event.id}>
          <ProcessEventMetadataView event={event} />
          {i !== props.processEvents.length - 1 && <Separator />}
        </div>
      ))}
    </div>
  );
};
