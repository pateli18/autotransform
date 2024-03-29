import { useEffect, useState } from "react";
import { ProcessEventMetadata } from "../types";
import { ConfigViewControls } from "../components/ConfigView";
import { Layout } from "../components/Layout";
import { ProcessHistoryView } from "../components/ProcessHistoryView";
import { getProcessHistory, processData, stopProcess } from "../utils/apiCalls";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  ExclamationTriangleIcon,
  ReloadIcon,
  StopIcon,
} from "@radix-ui/react-icons";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataDisplay } from "../components/DisplayUtils";
import {
  Form,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Input } from "@/components/ui/input";
import { readJson } from "../utils/dataLoad";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProcessConfigurationView } from "../components/ProcessConfigurationView";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

const formSchema = z.object({
  data: z.array(z.record(z.any(), z.any())),
});

const EnterDataDialog = (props: {
  configId: string;
  dialogOpen: boolean;
  setDialogOpen: (dialogOpen: boolean) => void;
  setProcessEvents: React.Dispatch<
    React.SetStateAction<ProcessEventMetadata[]>
  >;
}) => {
  const navigate = useNavigate();
  const [submitLoading, setSubmitLoading] = useState(false);
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      data: undefined,
    },
  });
  const data = form.watch("data");

  useEffect(() => {
    if (!props.dialogOpen) {
      form.reset();
    }
  }, [props.dialogOpen]);

  const handleSubmit = async (data: z.infer<typeof formSchema>) => {
    setSubmitLoading(true);
    const response = await processData(data.data, props.configId);
    setSubmitLoading(false);
    if (response === null) {
      toast.error("Failed to start processing");
    } else {
      props.setProcessEvents((events) => [response, ...events]);
      props.setDialogOpen(false);
      navigate(`/run/${props.configId}/${response.id}`);
      toast.success("Data processing started");
    }
  };

  return (
    <Dialog open={props.dialogOpen} onOpenChange={props.setDialogOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Start Processing</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form className="space-y-8">
            <FormField
              name="data"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Upload Data</FormLabel>
                  <Input
                    type="file"
                    accept=".json"
                    onChange={(e) => {
                      if (e.target.files) {
                        const file = e.target.files[0];
                        readJson(file)
                          .then((data) => {
                            form.setValue("data", data);
                            form.clearErrors("data");
                          })
                          .catch((e) => {
                            console.error(e);
                            form.setError(
                              "data",
                              {
                                type: "invalid",
                                message: e.toString(),
                              },
                              { shouldFocus: true }
                            );
                            form.reset({ data: undefined });
                          });
                      }
                    }}
                  />
                  <FormDescription>
                    Each record should be a json object
                  </FormDescription>
                  <FormMessage />
                  {data && (
                    <DataDisplay
                      recordCount={data.length}
                      dataToDisplay={data}
                      title=""
                    />
                  )}
                </FormItem>
              )}
            />
          </form>
        </Form>
        <Button onClick={form.handleSubmit(handleSubmit)}>
          Process Data
          {submitLoading && (
            <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
          )}
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export const ProcessHistoryRoute = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [configId, setConfigId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [processEvents, setProcessEvents] = useState<ProcessEventMetadata[]>(
    []
  );
  const configRunning = processEvents.some(
    (event) => event.status === "running"
  );

  useEffect(() => {
    if (configId !== null) {
      getProcessHistory(configId).then((data) => {
        if (data === null) {
          toast.error("Failed to fetch history");
        } else {
          setProcessEvents(data);
        }
      });
      if (configId !== searchParams.get("configId")) {
        setSearchParams({ configId });
      }
    }
  }, [configId]);

  useEffect(() => {
    if (searchParams.has("configId")) {
      if (searchParams.get("configId") !== configId) {
        const newConfigId = searchParams.get("configId")!;
        setConfigId(newConfigId);
      }
    }
  }, [searchParams]);

  return (
    <Layout>
      <ConfigViewControls configId={configId} setConfigId={setConfigId} />
      {configId && (
        <EnterDataDialog
          dialogOpen={dialogOpen}
          setDialogOpen={setDialogOpen}
          configId={configId}
          setProcessEvents={setProcessEvents}
        />
      )}
      <Tabs defaultValue="history">
        <div className="space-x-2">
          <TabsList>
            <TabsTrigger value="history">History</TabsTrigger>
            {configId !== null && (
              <TabsTrigger value="config">Configure</TabsTrigger>
            )}
          </TabsList>
          {configId !== null && (
            <Button
              disabled={configRunning}
              onClick={() => setDialogOpen(true)}
            >
              {configRunning ? "Processing" : "Start Processing"}
              {configRunning && (
                <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
              )}
            </Button>
          )}
          {configRunning && configId && (
            <Button
              onClick={() => {
                stopProcess(configId);
              }}
              variant="destructive"
            >
              <StopIcon className="mr-2 h-4 w-4" />
              Stop
            </Button>
          )}
        </div>
        <TabsContent value="history">
          {processEvents.length > 0 ? (
            <ProcessHistoryView processEvents={processEvents} />
          ) : (
            <Alert>
              <ExclamationTriangleIcon className="h-4 w-4" />
              <AlertTitle>No History Available</AlertTitle>
              <AlertDescription>
                Click {configId === null ? "New Service" : "Start Processing"}
              </AlertDescription>
            </Alert>
          )}
        </TabsContent>
        {configId !== null && (
          <TabsContent value="config">
            <ProcessConfigurationView configId={configId!} />
          </TabsContent>
        )}
      </Tabs>
    </Layout>
  );
};
