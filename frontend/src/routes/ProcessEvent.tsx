import { useEffect, useState } from "react";
import { ProcessingEvent } from "../types";
import { ProcessEventView } from "../components/ProcessEventView";
import { Layout } from "../components/Layout";
import { useParams } from "react-router-dom";

export const ProcessEventRoute = () => {
  const { configId, runId } = useParams<{ configId: string; runId: string }>();
  const [processingEvent, setProcessingEvent] =
    useState<ProcessingEvent | null>(null);
  let eventSource: EventSource | null;

  useEffect(() => {
    if (configId && runId) {
      eventSource = new EventSource(
        `/api/v1/process/status-ui/${configId}/${runId}`
      );
      eventSource.onmessage = (event) => {
        const data: ProcessingEvent = JSON.parse(event.data);
        setProcessingEvent(data);
        if (data.message.status !== "running") {
          eventSource?.close();
        }
      };

      return () => {
        if (eventSource) {
          eventSource.close();
        }
      };
    } else {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    }
  }, [configId, runId]);

  return (
    <Layout>
      {configId && processingEvent && (
        <ProcessEventView
          configId={configId}
          processingEvent={processingEvent}
          setProcessingEvent={setProcessingEvent}
        />
      )}
    </Layout>
  );
};
