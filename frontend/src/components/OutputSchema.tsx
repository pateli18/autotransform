import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useEffect, useState } from "react";
import { parseSchema } from "../utils/apiCalls";
import { toast } from "sonner";
import { ReloadIcon } from "@radix-ui/react-icons";
import JsonView from "react18-json-view";
import "react18-json-view/src/style.css";
import { LabeledExample } from "src/types";

export const OutputSchema = (props: {
  labeledData: LabeledExample[] | null;
  parsedValue: Object | null;
  setParsedValue: (value: Object | null) => void;
}) => {
  const [parseLoading, setParseLoading] = useState<boolean>(false);
  const [useLabeledExamplesLoading, setUseLabeledExamplesLoading] =
    useState<boolean>(false);
  const [inputValue, setInputValue] = useState<string>("");
  const [editView, setEditView] = useState<boolean>(false);
  const inputView = props.parsedValue === null || editView;

  const handleParseClick = async () => {
    setParseLoading(true);
    const response = await parseSchema(inputValue, null);
    setParseLoading(false);
    if (response === null) {
      toast.error("Failed to parse schema");
    } else {
      props.setParsedValue(response);
      setEditView(false);
    }
  };

  const handleUseLabeledExamplesClick = async () => {
    setUseLabeledExamplesLoading(true);
    const response = await parseSchema(null, props.labeledData);
    setUseLabeledExamplesLoading(false);
    if (response === null) {
      toast.error("Failed to generate schema");
    } else {
      props.setParsedValue(response);
      setEditView(false);
    }
  };

  return (
    <div className="space-y-5">
      {inputView ? (
        <Textarea
          placeholder="Paste your schema here, it can be anything (jsonschema, pydantic class, a normal data record) and we will automatically parse it for you"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          rows={5}
        />
      ) : (
        <JsonView src={props.parsedValue} />
      )}
      <div className="flex items-center space-x-2">
        {inputView ? (
          <>
            <Button
              onClick={handleParseClick}
              disabled={
                !inputValue || useLabeledExamplesLoading || parseLoading
              }
            >
              Parse
              {parseLoading && (
                <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
              )}
            </Button>
            <Button
              disabled={
                !props.labeledData || parseLoading || useLabeledExamplesLoading
              }
              onClick={handleUseLabeledExamplesClick}
            >
              Use Labeled Data
              {useLabeledExamplesLoading && (
                <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
              )}
            </Button>
            {props.parsedValue !== null && (
              <Button variant="secondary" onClick={() => setEditView(false)}>
                Back to Schema
              </Button>
            )}
          </>
        ) : (
          <Button
            variant="secondary"
            onClick={() => {
              setEditView(true);
            }}
          >
            Edit
          </Button>
        )}
      </div>
    </div>
  );
};
