import { Badge } from "@/components/ui/badge";
import { DownloadIcon } from "@radix-ui/react-icons";
import JsonView from "react18-json-view";
import { Code, ProcessingStatus } from "src/types";
import { buttonVariants } from "@/components/ui/button";
import Markdown from "react-markdown";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import a11yDark from "react-syntax-highlighter/dist/esm/styles/hljs/a11y-dark";

export const DataDisplay = (props: {
  title: string;
  recordCount: number;
  dataToDisplay: Record<any, any>[];
  downloadItems?: {
    configId: string;
    runId: string;
    recordType: "input" | "output";
  };
}) => {
  return (
    <div className="space-y-5">
      <h3 className="text-lg font-medium">
        {props.title}{" "}
        <Badge>
          {props.recordCount} {props.recordCount > 1 ? "Records" : "Record"}
        </Badge>{" "}
        {props.downloadItems && (
          <a
            href={`/api/v1/data/export/${props.downloadItems.configId}/${props.downloadItems.runId}/${props.downloadItems.recordType}`}
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            <DownloadIcon />
          </a>
        )}
      </h3>
      <JsonView src={props.dataToDisplay} />
    </div>
  );
};

export const StatusDisplay = (props: { status: ProcessingStatus }) => {
  switch (props.status) {
    case "running":
      return <Badge className="bg-blue-500">Running</Badge>;
    case "completed":
      return <Badge className="bg-green-500">Completed</Badge>;
    case "stopped":
      return <Badge className="bg-gray-500">Stopped</Badge>;
    case "failed":
      return <Badge className="bg-red-500">Failed</Badge>;
    case "awaiting_review":
      return <Badge className="bg-yellow-500">Awaiting Review</Badge>;
  }
};

export const CustomMarkdown = (props: { content: string }) => {
  return (
    <Markdown
      className="prose"
      children={props.content}
      components={{
        code({ ref, ...props }) {
          const { children, className, node, ...rest } = props;
          const match = /language-(\w+)/.exec(className || "");
          return match ? (
            <SyntaxHighlighter
              {...rest}
              PreTag="div"
              children={String(children).replace(/\n$/, "")}
              language={match[1]}
              style={a11yDark}
            />
          ) : (
            <code {...rest} className={className}>
              {children}
            </code>
          );
        },
      }}
    />
  );
};

export const CodeView = (props: { code: Code }) => {
  let codeToDisplay = props.code.code;
  // check if ```python in codeToDisplay, if not wrap it in ```python\n\n
  if (!codeToDisplay.includes("```python")) {
    codeToDisplay = "```python\n" + codeToDisplay + "\n```";
  }

  return (
    <>
      <h3 className="text-lg font-medium">Code</h3>
      <CustomMarkdown content={codeToDisplay} />
    </>
  );
};
