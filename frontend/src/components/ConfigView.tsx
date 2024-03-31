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
import { getAllConfigs, upsertConfig } from "../utils/apiCalls";
import { toast } from "sonner";
import { CaretSortIcon, PlusIcon, ReloadIcon } from "@radix-ui/react-icons";
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
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";

export const formSchema = z
  .object({
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
    gitUse: z.boolean().optional(),
    gitOwner: z.string().optional(),
    gitRepoName: z.string().optional(),
    gitPrimaryBranch: z.string().optional(),
    gitBlockHumanReview: z.boolean().optional(),
  })
  .refine((data) => {
    if (data.gitUse === true) {
      return (
        data.gitOwner &&
        data.gitRepoName &&
        data.gitPrimaryBranch &&
        data.gitBlockHumanReview !== undefined
      );
    }
    return true;
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

const GitForm = (props: {
  form: UseFormReturn<z.infer<typeof formSchema>>;
}) => {
  const gitUse = props.form.watch("gitUse");

  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button variant="ghost" className="pl-0">
          Git Settings
          {gitUse && <span className="text-green-500 ml-2">Enabled</span>}
          <CaretSortIcon className="h-4 w-4" />
          <span className="sr-only">Toggle</span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4">
        <FormField
          control={props.form.control}
          name="gitUse"
          render={({ field }) => (
            <FormItem className="space-x-3">
              <FormLabel>Use External Git Provider</FormLabel>
              <FormControl>
                <Checkbox
                  checked={field.value}
                  onCheckedChange={(checked) => {
                    const value = typeof checked === "boolean" ? checked : true;
                    field.onChange(value);
                  }}
                />
              </FormControl>
              <FormDescription>
                If you want to store and manage the code for this service in an
                external git provider like Github, enable this option
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        {gitUse && (
          <>
            <FormField
              control={props.form.control}
              name="gitOwner"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Owner</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormDescription>Your github user id</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={props.form.control}
              name="gitRepoName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Repo Name</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormDescription>Name of the github repo</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={props.form.control}
              name="gitPrimaryBranch"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Primary Branch Name</FormLabel>
                  <FormControl>
                    <Input type="text" {...field} />
                  </FormControl>
                  <FormDescription>
                    The branch that contains the code running in the service
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={props.form.control}
              name="gitBlockHumanReview"
              render={({ field }) => (
                <FormItem className="space-x-3">
                  <FormLabel>Await Human Review</FormLabel>
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        const value =
                          typeof checked === "boolean" ? checked : true;
                        field.onChange(value);
                      }}
                    />
                  </FormControl>
                  <FormDescription>
                    All code and schema changes will be blocked until a human
                    approves the pr
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
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
        <GitForm form={form} />
      </form>
    </Form>
  );
};

const ConfigView = (props: {
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
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
      gitUse: false,
      gitOwner: undefined,
      gitRepoName: undefined,
      gitPrimaryBranch: "main",
      gitBlockHumanReview: true,
    },
  });
  const gitUse = form.watch("gitUse");

  useEffect(() => {
    if (props.drawerOpen === true) {
      form.reset({
        name: undefined,
        outputSchema: undefined,
        labeledData: undefined,
        gitUse: false,
        gitOwner: undefined,
        gitRepoName: undefined,
        gitPrimaryBranch: "main",
        gitBlockHumanReview: true,
      });
      setParsedValue(null);
    }
  }, [props.drawerOpen]);

  useEffect(() => {
    if (gitUse === true) {
      form.reset(
        {
          gitOwner: undefined,
          gitRepoName: undefined,
          gitPrimaryBranch: "main",
          gitBlockHumanReview: true,
        },
        { keepValues: true }
      );
    }
  }, [gitUse]);

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setSubmitLoading(true);
    const response = await upsertConfig(
      null,
      data.name,
      data.outputSchema,
      data.labeledData ?? null,
      data.gitUse
        ? {
            owner: data.gitOwner!,
            repo_name: data.gitRepoName!,
            primary_branch_name: data.gitPrimaryBranch!,
            block_human_review: data.gitBlockHumanReview!,
          }
        : null
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
  configMetadata: ConfigMetadata[];
  setConfigId: (configId: string | null) => void;
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (props.configId === null && drawerOpen === false) {
      props.setConfigId(
        props.configMetadata.length > 0
          ? props.configMetadata[0].config_id
          : null
      );
    }
  }, [drawerOpen]);

  return (
    <>
      <ConfigView
        drawerOpen={drawerOpen}
        setDrawerOpen={setDrawerOpen}
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
        {props.configMetadata.length > 0 && (
          <ConfigSelection
            configs={props.configMetadata}
            configId={props.configId}
            setConfigId={props.setConfigId}
          />
        )}
      </div>
    </>
  );
};
