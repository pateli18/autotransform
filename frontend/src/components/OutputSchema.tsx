import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useState } from "react";
import { parseSchema } from "../utils/apiCalls";
import { toast } from "sonner";
import { ReloadIcon } from "@radix-ui/react-icons";
import JsonView from "react18-json-view";
import "react18-json-view/src/style.css";
import { LabeledExample } from "src/types";
import { FormControl } from "@/components/ui/form";

const SchemaButtons = (props: {
  inputValue: string;
  handleParseClick: () => void;
  useLabeledExamplesLoading: boolean;
  parseLoading: boolean;
  labeledData: LabeledExample[] | null;
  handleUseLabeledExamplesClick: () => void;
  setEditView: (value: boolean) => void;
  parsedValue: Object | null;
}) => {
  return (
    <div className="space-x-2">
      <Button
        onClick={props.handleParseClick}
        disabled={
          !props.inputValue ||
          props.useLabeledExamplesLoading ||
          props.parseLoading
        }
      >
        Parse
        {props.parseLoading && (
          <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
        )}
      </Button>
      <Button
        disabled={
          !props.labeledData ||
          props.parseLoading ||
          props.useLabeledExamplesLoading
        }
        onClick={props.handleUseLabeledExamplesClick}
      >
        Use Labeled Data
        {props.useLabeledExamplesLoading && (
          <ReloadIcon className="ml-2 h-4 w-4 animate-spin" />
        )}
      </Button>
      {props.parsedValue !== null && (
        <Button variant="secondary" onClick={() => props.setEditView(false)}>
          Back to Schema
        </Button>
      )}
    </div>
  );
};

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
        <>
          <SchemaButtons
            inputValue={inputValue}
            handleParseClick={handleParseClick}
            useLabeledExamplesLoading={useLabeledExamplesLoading}
            parseLoading={parseLoading}
            labeledData={props.labeledData}
            handleUseLabeledExamplesClick={handleUseLabeledExamplesClick}
            setEditView={setEditView}
            parsedValue={props.parsedValue}
          />

          <FormControl>
            <Textarea
              placeholder="Paste your schema here, it can be anything (jsonschema, pydantic class, a normal data record) and we will automatically parse it for you"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              rows={5}
            />
          </FormControl>
        </>
      ) : (
        <>
          <JsonView src={props.parsedValue} />
          <Button
            variant="secondary"
            onClick={() => {
              setEditView(true);
            }}
          >
            Edit
          </Button>
        </>
      )}
    </div>
  );
};
