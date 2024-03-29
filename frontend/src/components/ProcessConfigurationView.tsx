import { Config } from "src/types";
import { useEffect, useState } from "react";
import { CustomMarkdown, DataDisplay } from "./DisplayUtils";
import { ConfigForm, formSchema } from "./ConfigView";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { getConfig, upsertConfig } from "../utils/apiCalls";
import { toast } from "sonner";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { ReloadIcon } from "@radix-ui/react-icons";
import { Separator } from "@/components/ui/separator";

export const ProcessConfigurationView = (props: { configId: string }) => {
  const [submitLoading, setSubmitLoading] = useState(false);
  const [parsedValue, setParsedValue] = useState<Object | null>(null);
  const [config, setConfig] = useState<Config | null>(null);

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: undefined,
      outputSchema: undefined,
      labeledData: undefined,
    },
  });

  useEffect(() => {
    getConfig(props.configId).then((data) => {
      if (data === null) {
        toast.error("Failed to fetch service");
      } else {
        setConfig(data);
      }
    });
  }, [props.configId]);

  useEffect(() => {
    if (config !== null) {
      form.reset({
        name: config.name,
        outputSchema: undefined,
        labeledData: config.user_provided_records ?? undefined,
      });
      setParsedValue(config.output_schema);
    }
  }, [config]);

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
      toast.error("Failed to update config");
    } else {
      toast.success("Config updated successfully");
    }
  };

  return (
    <div className="space-y-5 pt-5">
      <h3 className="text-lg font-semibold">Editable Values</h3>
      <ConfigForm
        form={form}
        parsedValue={parsedValue}
        setParsedValue={setParsedValue}
      />
      <Button onClick={form.handleSubmit(onSubmit)}>
        Update
        {submitLoading && <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />}
      </Button>
      {config && (
        <>
          <Separator className="mt-5 mb-5" />
          <h3 className="text-lg font-semibold">Automatic Values</h3>
          {config.code && (
            <>
              <h3 className="text-lg font-medium">Code</h3>
              <CustomMarkdown content={config.code.markdown} />
            </>
          )}
          {config.bot_provided_records &&
            config.bot_provided_records.length > 0 && (
              <DataDisplay
                title="Bot Provided Records"
                recordCount={(config.bot_provided_records ?? []).length}
                dataToDisplay={config.bot_provided_records ?? []}
              />
            )}
          {config.current_records && config.current_records.length > 0 && (
            <DataDisplay
              title="Current Records"
              recordCount={(config.current_records ?? []).length}
              dataToDisplay={config.current_records ?? []}
            />
          )}
          {config.previous_records && config.previous_records.length > 0 && (
            <DataDisplay
              title="Historical Records"
              recordCount={(config.previous_records ?? []).length}
              dataToDisplay={config.previous_records ?? []}
            />
          )}
        </>
      )}
    </div>
  );
};
