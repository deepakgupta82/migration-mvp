import React from "react";
import { Paper } from "@mantine/core";

type LiveConsoleProps = {
  logs: string[];
};

const LiveConsole: React.FC<LiveConsoleProps> = ({ logs }) => (
  <Paper shadow="xs" p="md" style={{ maxHeight: 300, overflowY: "auto", background: "#222", color: "#eee" }}>
    <pre style={{ margin: 0, fontFamily: "monospace" }}>
      {logs.join("\n")}
    </pre>
  </Paper>
);

export default LiveConsole;
