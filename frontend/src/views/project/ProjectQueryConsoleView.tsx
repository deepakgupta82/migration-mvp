import React, { useMemo, useState } from 'react';
import graphService from '../../services/GraphService';

interface Props { projectId: string }

const ProjectQueryConsoleView: React.FC<Props> = ({ projectId }) => {
  const [nl, setNl] = useState('list servers connecting to databases');
  const [limit, setLimit] = useState(50);
  const [cypher, setCypher] = useState('');
  const [building, setBuilding] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<any[]>([]);
  const [columns, setColumns] = useState<string[]>([]);

  const disabled = building || running;

  const preview = async () => {
    setBuilding(true); setError(null);
    try {
      const res = await graphService.nl2cypher(projectId, { nl, limit });
      setCypher(res.cypher);
    } catch (e: any) {
      setError(e?.message || 'Failed to build query');
    } finally {
      setBuilding(false);
    }
  };

  const run = async () => {
    setRunning(true); setError(null);
    try {
      const res = await graphService.runCypher(projectId, { cypher, limit });
      setColumns(res.columns || []);
      setRows(res.rows || []);
    } catch (e: any) {
      setError(e?.message || 'Query failed');
    } finally {
      setRunning(false);
    }
  };

  const hasResults = useMemo(() => rows.length > 0 && columns.length > 0, [rows, columns]);

  return (
    <div style={{ padding: 16, display: 'grid', gap: 12 }}>
      <h3>Semantic Query Console</h3>
      {error && <div style={{ color: 'red' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <input style={{ flex: 1, minWidth: 280, padding: 8 }} value={nl} onChange={(e) => setNl(e.target.value)} />
        <label>
          Limit:
          <input type="number" min={1} max={200} value={limit} onChange={(e) => setLimit(parseInt(e.target.value || '50', 10))} style={{ width: 80, marginLeft: 6 }} />
        </label>
        <button onClick={preview} disabled={disabled}>Preview Cypher</button>
        <button onClick={run} disabled={disabled || !cypher.trim()}>Run</button>
      </div>
      <div>
        <div style={{ fontSize: 12, color: '#666' }}>Cypher (read-only, project-scoped)</div>
        <textarea style={{ width: '100%', minHeight: 120, fontFamily: 'monospace' }} value={cypher} onChange={(e) => setCypher(e.target.value)} />
      </div>
      {hasResults && (
        <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>{columns.map(c => <th key={c} style={{ textAlign: 'left', padding: '6px' }}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>{columns.map(c => <td key={c} style={{ padding: '6px' }}><code>{JSON.stringify(r[c])}</code></td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ProjectQueryConsoleView;
