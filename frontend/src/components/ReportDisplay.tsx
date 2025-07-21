import React from "react";
import { Paper } from "@mantine/core";
import ReactMarkdown from "react-markdown";

type ReportDisplayProps = {
  report: string;
};

const ReportDisplay: React.FC<ReportDisplayProps> = ({ report }) => {
  if (!report) return null;
  return (
    <Paper shadow="xs" p="md" style={{ marginTop: 20 }}>
      <ReactMarkdown>{report}</ReactMarkdown>
    </Paper>
  );
};

export default ReportDisplay;
