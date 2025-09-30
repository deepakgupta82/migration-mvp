import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { graphService, CanonicalCentrality } from '../../services/GraphService';

interface Props { projectId: string; }

const ProjectCentralityView: React.FC<Props> = ({ projectId }) => {
  const [limit, setLimit] = useState(25);
  const [data, setData] = useState<CanonicalCentrality | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'name' | 'total' | 'out' | 'in'>('total');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await graphService.getCanonicalCentrality(projectId, limit);
      setData(res);
    } catch (e: any) {
      setError(e?.message || 'Failed to fetch centrality');
    } finally {
      setLoading(false);
    }
  }, [projectId, limit]);

  useEffect(() => { load(); }, [load]);

  const items = useMemo(() => {
    const rows = [...(data?.items ?? [])];
    rows.sort((a: any, b: any) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name':
          cmp = (a.name || '').localeCompare(b.name || '');
          break;
        case 'out':
          cmp = (a.out_degree || 0) - (b.out_degree || 0);
          break;
        case 'in':
          cmp = (a.in_degree || 0) - (b.in_degree || 0);
          break;
        case 'total':
        default:
          cmp = (a.total_degree || 0) - (b.total_degree || 0);
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    const start = (page - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [data, sortBy, sortDir, page, pageSize]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ fontWeight: 600, fontSize: 18 }}>Canonical Centrality</div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <label>
            Limit:
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value || '25', 10))}
              style={{ width: 72, marginLeft: 6 }}
            />
          </label>
          <label>
            Page size:
            <input
              type="number"
              min={5}
              max={100}
              value={pageSize}
              onChange={(e) => setPageSize(parseInt(e.target.value || '25', 10))}
              style={{ width: 72, marginLeft: 6 }}
            />
          </label>
          <label>
            Page:
            <input
              type="number"
              min={1}
              value={page}
              onChange={(e) => setPage(parseInt(e.target.value || '1', 10))}
              style={{ width: 72, marginLeft: 6 }}
            />
          </label>
          <button onClick={load} disabled={loading}>Refresh</button>
        </div>
      </div>

      {loading && <div>Loading…</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}

      {items.length > 0 && (
        <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 8 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left' }}>
                <th style={{ padding: '8px 6px' }}>#</th>
                <th style={{ padding: '8px 6px' }}>Canonical ID</th>
                <th style={{ padding: '8px 6px', cursor: 'pointer' }} onClick={() => { setSortBy('name'); setSortDir(sortBy==='name' && sortDir==='asc' ? 'desc':'asc'); }}>Name {sortBy==='name' ? (sortDir==='asc'?'▲':'▼') : ''}</th>
                <th style={{ padding: '8px 6px', cursor: 'pointer' }} onClick={() => { setSortBy('total'); setSortDir(sortBy==='total' && sortDir==='asc' ? 'desc':'asc'); }}>Total Degree {sortBy==='total' ? (sortDir==='asc'?'▲':'▼') : ''}</th>
                <th style={{ padding: '8px 6px', cursor: 'pointer' }} onClick={() => { setSortBy('out'); setSortDir(sortBy==='out' && sortDir==='asc' ? 'desc':'asc'); }}>Out Degree {sortBy==='out' ? (sortDir==='asc'?'▲':'▼') : ''}</th>
                <th style={{ padding: '8px 6px', cursor: 'pointer' }} onClick={() => { setSortBy('in'); setSortDir(sortBy==='in' && sortDir==='asc' ? 'desc':'asc'); }}>In Degree {sortBy==='in' ? (sortDir==='asc'?'▲':'▼') : ''}</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, limit).map((it, idx) => (
                <tr key={it.id}>
                  <td style={{ padding: '6px' }}>{idx + 1}</td>
                  <td style={{ padding: '6px', fontFamily: 'monospace' }}>{it.id}</td>
                  <td style={{ padding: '6px' }}>{it.name || ''}</td>
                  <td style={{ padding: '6px' }}>{it.total_degree}</td>
                  <td style={{ padding: '6px' }}>{it.out_degree}</td>
                  <td style={{ padding: '6px' }}>{it.in_degree}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div>No central entities found yet for this project.</div>
      )}
    </div>
  );
};

export default ProjectCentralityView;
