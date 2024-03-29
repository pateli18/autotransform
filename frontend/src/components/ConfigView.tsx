import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { OutputSchema } from "./OutputSchema";
import * as z from "zod";
import { UseFormReturn, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useEffect, useState } from "react";
import { getAllConfigs, getConfig, upsertConfig } from "../utils/apiCalls";
import { toast } from "sonner";
import { PlusIcon, ReloadIcon } from "@radix-ui/react-icons";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfigMetadata } from "../types";
import { loadAndFormatDate } from "../utils/date";
import { DataDisplay } from "./DisplayUtils";
import { readJson } from "../utils/dataLoad";

export const formSchema = z.object({
  name: z.string(),
  outputSchema: z.record(z.any(), z.any()),
  labeledData: z
    .array(
      z.object({
        input: z.record(z.any(), z.any()),
        output: z.record(z.any(), z.any()),
      })
    )
    .optional(),
});

const jsonValidator = (data: any) => {
  if (!data.input || !data.output) {
    throw new Error(
      `Each record must have an 'input' and 'output' key: ${JSON.stringify(
        data
      )}`
    );
  }
};

export const ConfigForm = (props: {
  form: UseFormReturn<z.infer<typeof formSchema>>;
  parsedValue: Object | null;
  setParsedValue: (value: Object | null) => void;
}) => {
  const { form } = props;
  const labeledData = form.watch("labeledData");

  useEffect(() => {
    if (props.parsedValue === null) {
      form.reset({ outputSchema: undefined });
    } else {
      form.setValue("outputSchema", props.parsedValue);
    }
  }, [props.parsedValue]);

  return (
    <Form {...form}>
      <form className="space-y-8">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Service Name</FormLabel>
              <FormControl>
                <Input type="text" {...field} />
              </FormControl>
              <FormDescription>Name of the Service</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          name="outputSchema"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Output Schema</FormLabel>
              <OutputSchema
                labeledData={labeledData ?? null}
                parsedValue={props.parsedValue}
                setParsedValue={props.setParsedValue}
              />
              <FormDescription>
                The jsonschema that will be enforced by the service when it
                processes a record. You can provided some labeled records below
                and generate this automatically, or add it in whatever format
                you like and have the system parse it.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          name="labeledData"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Labeled Data</FormLabel>
              <Input
                type="file"
                accept=".json"
                onChange={(e) => {
                  if (e.target.files) {
                    const file = e.target.files[0];
                    readJson(file, jsonValidator)
                      .then((data) => {
                        form.setValue("labeledData", data);
                        form.clearErrors("labeledData");
                      })
                      .catch((e) => {
                        console.error(e);
                        form.setError(
                          "labeledData",
                          {
                            type: "invalid",
                            message: e.toString(),
                          },
                          { shouldFocus: true }
                        );
                        form.setValue("labeledData", undefined);
                      });
                  }
                }}
              />
              <FormDescription>
                {<strong>OPTIONAL</strong>} Each record should be a json object
                with an `input` key and an `output` key, with corresponding json
                objects as values
              </FormDescription>
              <FormMessage />
              {labeledData && (
                <DataDisplay
                  dataToDisplay={labeledData}
                  title=""
                  recordCount={labeledData.length}
                />
              )}
            </FormItem>
          )}
        />
      </form>
    </Form>
  );
};

const ConfigView = (props: {
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  configId: string | null;
  setConfigId: (configId: string) => void;
}) => {
  const [parsedValue, setParsedValue] = useState<Object | null>(null);
  const [submitLoading, setSubmitLoading] = useState(false);
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: undefined,
      outputSchema: undefined,
      labeledData: undefined,
    },
  });

  useEffect(() => {
    if (props.configId === null) {
      form.reset({
        name: undefined,
        outputSchema: undefined,
        labeledData: undefined,
      });
      setParsedValue(null);
    } else {
      getConfig(props.configId).then((data) => {
        if (data === null) {
          toast.error("Failed to fetch service");
        } else {
          form.reset({
            name: data.name,
            outputSchema: undefined,
            labeledData: data.user_provided_records ?? undefined,
          });
          setParsedValue(data.output_schema);
        }
      });
    }
  }, [props.configId]);

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setSubmitLoading(true);
    const response = await upsertConfig(
      props.configId,
      data.name,
      data.outputSchema,
      data.labeledData ?? null
    );
    setSubmitLoading(false);
    if (response === null) {
      toast.error("Failed to upsert config");
    } else {
      props.setConfigId(response.config_id);
      toast.success("Config created successfully");
      props.setDrawerOpen(false);
    }
  };

  return (
    <Drawer open={props.drawerOpen} onOpenChange={props.setDrawerOpen}>
      <DrawerContent className="max-h-[90%]">
        <DrawerHeader>
          <DrawerTitle>Configure Service</DrawerTitle>
        </DrawerHeader>
        <div className="p-4 space-y-5 overflow-y-auto">
          <ConfigForm
            form={form}
            parsedValue={parsedValue}
            setParsedValue={setParsedValue}
          />
        </div>
        <DrawerFooter>
          <Button onClick={form.handleSubmit(onSubmit)}>
            Submit
            {submitLoading && (
              <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
            )}
          </Button>
          <DrawerClose asChild>
            <Button variant="outline">Cancel</Button>
          </DrawerClose>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
};

const ConfigSelection = (props: {
  configs: ConfigMetadata[];
  configId: string | null;
  setConfigId: (configId: string) => void;
}) => {
  return (
    <Select
      value={props.configId ?? undefined}
      onValueChange={props.setConfigId}
    >
      <SelectTrigger className="overflow-hidden whitespace-nowrap w-[300px]">
        <SelectValue placeholder="Select Service" />
      </SelectTrigger>
      <SelectContent>
        <div className="overflow-y-scroll h-[200px]">
          {props.configs.map((config) => (
            <SelectItem key={config.config_id} value={config.config_id}>
              <div className="space-x-2">
                <span>{config.name}</span>
                <span className="text-gray-400">
                  {loadAndFormatDate(config.last_updated)}
                </span>
              </div>
            </SelectItem>
          ))}
        </div>
      </SelectContent>
    </Select>
  );
};

export const ConfigViewControls = (props: {
  configId: string | null;
  setConfigId: (configId: string | null) => void;
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [configs, setConfigs] = useState<ConfigMetadata[]>([]);

  useEffect(() => {
    getAllConfigs().then((data) => {
      if (data === null) {
        toast.error("Failed to fetch services");
      } else {
        setConfigs(data);
        if (props.configId === null && data.length > 0) {
          props.setConfigId(data[0].config_id);
        }
      }
    });
  }, []);

  useEffect(() => {
    if (props.configId === null && drawerOpen === false) {
      props.setConfigId(configs.length > 0 ? configs[0].config_id : null);
    }
  }, [drawerOpen]);

  return (
    <>
      <ConfigView
        drawerOpen={drawerOpen}
        setDrawerOpen={setDrawerOpen}
        configId={props.configId}
        setConfigId={props.setConfigId}
      />
      <div className="flex flex-wrap items-center space-x-2 py-1">
        <Button
          onClick={() => {
            props.setConfigId(null);
            setDrawerOpen(true);
          }}
          variant="secondary"
        >
          <PlusIcon className="w-4 h-4 mr-2" />
          New Service
        </Button>
        {configs.length > 0 && (
          <ConfigSelection
            configs={configs}
            configId={props.configId}
            setConfigId={props.setConfigId}
          />
        )}
      </div>
    </>
  );
};
