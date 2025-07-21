import React, { useState, useRef } from "react";
import { Button, Group, Stack, Text, Paper, Loader } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import axios from "axios";
import { v4 as uuidv4 } from "uuid";
import LiveConsole from "./LiveConsole";
import ReportDisplay from "./ReportDisplay";

type FileUploadProps = {};

const FileUpload: React.FC<FileUploadProps> = () => {
  const [files, setFiles] = useState<File[]>([]);
  const [projectId, setProjectId] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);
  const [isAssessing, setIsAssessing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>("");
  const [isReportStreaming, setIsReportStreaming] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  const handleDrop = (acceptedFiles: File[]) => {
    setFiles(acceptedFiles);
    setProjectId(uuidv4());
    setLogs([]);
    setFinalReport("");
    setIsReportStreaming(false);
  };

  const handleUploadAndAssess = async () => {
    if (files.length === 0 || !projectId) return;
    setIsUploading(true);
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    try {
      await axios.post(`/upload/${projectId}`, formData, {
        baseURL: "http://localhost:8000",
        headers: { "Content-Type": "multipart/form-data" },
      });
      setIsUploading(false);
      setIsAssessing(true);
      const ws = new WebSocket(`ws://localhost:8000/ws/run_assessment/${projectId}`);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        const msg = event.data;
        if (msg === "FINAL_REPORT_MARKDOWN_START") {
          setFinalReport("");
          setIsReportStreaming(true);
        } else if (msg === "FINAL_REPORT_MARKDOWN_END") {
          setIsReportStreaming(false);
          setIsAssessing(false);
        } else if (isReportStreaming) {
          setFinalReport((prev) => prev + msg + "\n");
        } else {
          setLogs((prev) => [...prev, msg]);
        }
      };
      ws.onclose = () => setIsAssessing(false);
    } catch (err) {
      setIsUploading(false);
      setIsAssessing(false);
      setLogs((prev) => [...prev, "Error uploading files or starting assessment."]);
    }
  };

  return (
    <Stack spacing="md">
      <Dropzone onDrop={handleDrop} multiple>
        <Text>Drag and drop files here, or click to select</Text>
      </Dropzone>
      <Group>
        <Button
          onClick={handleUploadAndAssess}
          disabled={files.length === 0 || isUploading || isAssessing}
        >
          Upload & Start Assessment
        </Button>
        {isUploading && <Loader size="sm" />}
        {isAssessing && <Text>Assessment in progress...</Text>}
      </Group>
      {logs.length > 0 && <LiveConsole logs={logs} />}
      {finalReport && <ReportDisplay report={finalReport} />}
    </Stack>
  );
};

export default FileUpload;
