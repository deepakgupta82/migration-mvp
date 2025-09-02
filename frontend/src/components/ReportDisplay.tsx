import React from "react";
import { Paper, Alert } from "@mantine/core";
import ReactMarkdown from "react-markdown";
import { IconInfoCircle } from "@tabler/icons-react";
import JsonlAnalysisDisplay from "./JsonlAnalysisDisplay";

type ReportDisplayProps = {
  report?: string;
  analysis?: any;
  useJsonl?: boolean;
  projectId?: string;
  analysisId?: string;
};

const ReportDisplay: React.FC<ReportDisplayProps> = ({
  report,
  analysis,
  useJsonl = false,
  projectId,
  analysisId
}) => {
  // If using JSONL analysis display
  if (useJsonl && analysis) {
    return (
      <Paper shadow="xs" p="md" style={{ marginTop: 20 }}>
        <JsonlAnalysisDisplay
          analysis={analysis}
          projectId={projectId}
          analysisId={analysisId}
        />
      </Paper>
    );
  }

  // Fallback to markdown display
  if (!report) {
    return (
      <Alert icon={<IconInfoCircle size={16} />} color="blue">
        No report data available
      </Alert>
    );
  }

  return (
    <Paper shadow="xs" p="md" style={{ marginTop: 20 }}>
      <ReactMarkdown>{report}</ReactMarkdown>
    </Paper>
  );
};

export default ReportDisplay;
