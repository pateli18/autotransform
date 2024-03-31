import { useEffect, useState } from "react";
import { Config, ConfigMetadata, ProcessEventMetadata } from "../types";
import { ConfigViewControls } from "../components/ConfigView";
import { Layout } from "../components/Layout";
import { ProcessHistoryView } from "../components/ProcessHistoryView";
import {
  getAllConfigs,
  getConfig,
  processData,
  stopProcess,
} from "../utils/apiCalls";
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
import { Loader2 } from "lucide-react";

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
  const [config, setConfig] = useState<Config | null>(null);
  const [configMetadata, setConfigMetadata] = useState<ConfigMetadata[]>([]);
  const [dataLoading, setDataLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [processEvents, setProcessEvents] = useState<ProcessEventMetadata[]>(
    []
  );
  const latestRun = processEvents.length > 0 ? processEvents[0] : null;

  useEffect(() => {
    getAllConfigs().then((data) => {
      if (data === null) {
        toast.error("Failed to fetch services");
      } else {
        setConfigMetadata(data);
      }
    });
  }, []);

  useEffect(() => {
    if (configId !== null) {
      setDataLoading(true);
      getConfig(configId).then((data) => {
        if (data === null) {
          toast.error("Failed to fetch config");
          setConfig(null);
          setConfigId(null);
          setSearchParams({});
        } else {
          setProcessEvents(data.history);
          setConfig(data.config);
        }
        setDataLoading(false);
      });
      if (configId !== searchParams.get("configId")) {
        setSearchParams({ configId });
      }
    }
  }, [configId]);

  useEffect(() => {
    if (configMetadata.length > 0 && configId === null) {
      setConfigId(configMetadata[0].config_id);
    }
  }, [configMetadata]);

  useEffect(() => {
    if (searchParams.has("configId")) {
      if (searchParams.get("configId") !== configId) {
        const newConfigId = searchParams.get("configId")!;
        setConfigId(newConfigId);
      }
    }
  }, [searchParams]);

  const onClickStop = async () => {
    if (latestRun?.status === "running" && configId) {
      await stopProcess(configId, latestRun.id);
      // reload page
      window.location.reload();
    }
  };

  return (
    <Layout>
      <ConfigViewControls
        configId={configId}
        setConfigId={setConfigId}
        configMetadata={configMetadata}
      />
      {config !== null && (
        <EnterDataDialog
          dialogOpen={dialogOpen}
          setDialogOpen={setDialogOpen}
          configId={config.config_id}
          setProcessEvents={setProcessEvents}
        />
      )}
      {dataLoading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="h-8 w-8 animate-spin" />
          <div className="ml-2">Loading Data</div>
        </div>
      ) : (
        <Tabs defaultValue="history">
          <div className="space-x-2 flex items-center">
            <TabsList>
              <TabsTrigger value="history">History</TabsTrigger>
              {config !== null && (
                <TabsTrigger value="config">Configure</TabsTrigger>
              )}
            </TabsList>
            {configId !== null && (
              <Button
                disabled={latestRun?.status === "running"}
                onClick={() => setDialogOpen(true)}
              >
                {latestRun?.status === "running"
                  ? "Processing"
                  : "Start Processing"}
                {latestRun?.status === "running" && (
                  <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
                )}
              </Button>
            )}
            {latestRun?.status === "running" && configId && (
              <Button onClick={onClickStop} variant="destructive">
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
          {config !== null && (
            <TabsContent value="config">
              <ProcessConfigurationView config={config} />
            </TabsContent>
          )}
        </Tabs>
      )}
    </Layout>
  );
};
