import { Config } from "src/types";
import { useEffect, useState } from "react";
import { CodeView, CustomMarkdown, DataDisplay } from "./DisplayUtils";
import { ConfigForm, formSchema } from "./ConfigView";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { upsertConfig } from "../utils/apiCalls";
import { toast } from "sonner";
import * as z from "zod";
import { Button } from "@/components/ui/button";
import { ReloadIcon } from "@radix-ui/react-icons";
import { Separator } from "@/components/ui/separator";

export const ProcessConfigurationView = (props: { config: Config }) => {
  const [submitLoading, setSubmitLoading] = useState(false);
  const [parsedValue, setParsedValue] = useState<Object | null>(null);

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

  useEffect(() => {
    form.reset({
      name: props.config.name,
      outputSchema: undefined,
      labeledData: props.config.user_provided_records ?? undefined,
      gitUse: props.config.git_config !== null,
      gitOwner: props.config.git_config?.owner ?? undefined,
      gitRepoName: props.config.git_config?.repo_name ?? undefined,
      gitPrimaryBranch: props.config.git_config?.primary_branch_name ?? "main",
      gitBlockHumanReview: props.config.git_config?.block_human_review ?? true,
    });
    setParsedValue(props.config.output_schema.output_schema);
  }, [props.config.config_id]);

  const onSubmit = async (data: z.infer<typeof formSchema>) => {
    setSubmitLoading(true);
    const response = await upsertConfig(
      props.config.config_id,
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
      <>
        <Separator className="mt-5 mb-5" />
        <h3 className="text-lg font-semibold">Automatic Values</h3>
        {props.config.code && <CodeView code={props.config.code} />}
        {props.config.bot_provided_records &&
          props.config.bot_provided_records.length > 0 && (
            <DataDisplay
              title="Bot Provided Records"
              recordCount={(props.config.bot_provided_records ?? []).length}
              dataToDisplay={props.config.bot_provided_records ?? []}
            />
          )}
        {props.config.current_records &&
          props.config.current_records.length > 0 && (
            <DataDisplay
              title="Current Records"
              recordCount={(props.config.current_records ?? []).length}
              dataToDisplay={props.config.current_records ?? []}
            />
          )}
        {props.config.previous_records &&
          props.config.previous_records.length > 0 && (
            <DataDisplay
              title="Historical Records"
              recordCount={(props.config.previous_records ?? []).length}
              dataToDisplay={props.config.previous_records ?? []}
            />
          )}
      </>
    </div>
  );
};
