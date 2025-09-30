import React, { useEffect, useState } from 'react';
import { graphService, ExplorerOverview, FusedSearchItem } from '../../services/GraphService';
import TopCentralCanonicalWidget from '../../components/project-detail/TopCentralCanonicalWidget';
import ProjectMetricsWidget from '../../components/project-detail/ProjectMetricsWidget';

interface Props { projectId: string }

const ProjectExplorerView: React.FC<Props> = ({ projectId }) => {
  const [overview, setOverview] = useState<ExplorerOverview | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FusedSearchItem[]>([]);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [running, setRunning] = useState(false);
  const [lastRunResult, setLastRunResult] = useState<any>(null);
  const [boostCentrality, setBoostCentrality] = useState(true);
  const [weights, setWeights] = useState<string>('entity_cards:1.0,raw_chunks:0.8');
  const [centralityScale, setCentralityScale] = useState<number>(0.05);
  const [normalizedCentrality, setNormalizedCentrality] = useState<boolean>(true);
  const [summary, setSummary] = useState<any | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize, setHistoryPageSize] = useState(10);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoadingOverview(true);
      setError(null);
      try {
        const data = await graphService.getExplorerOverview(projectId);
        if (mounted) setOverview(data);
        // Fetch maintenance summary (unlinked counts, etc.)
        try {
          const sres = await fetch(`http://localhost:8006/projects/${projectId}/maintenance/summary`, {
            headers: { 'Authorization': 'Bearer service-backend-token' }
          });
          if (sres.ok) {
            const sval = await sres.json();
            if (mounted) setSummary(sval);
          }
        } catch {}
        try {
          const hres = await fetch(`http://localhost:8006/projects/${projectId}/maintenance/history?limit=20`, {
            headers: { 'Authorization': 'Bearer service-backend-token' }
          });
          if (hres.ok) {
            const hval = await hres.json();
            if (mounted) setHistory(hval.items || []);
          }
        } catch {}
      } catch (e: any) {
        setError(e?.message || 'Failed to load overview');
      } finally {
        setLoadingOverview(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [projectId]);

  const runSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query?.trim()) return;
    setLoadingSearch(true);
    setError(null);
    try {
      const data = await graphService.fusedSearch(projectId, {
        q: query,
        kinds: ['entity_cards','raw_chunks'],
        k: 10,
        use_hybrid: true,
        boost_centrality: boostCentrality,
        weights,
        centrality_scale: centralityScale,
        normalized_centrality: normalizedCentrality,
      } as any);
      setResults(data.items || []);
    } catch (e: any) {
      setError(e?.message || 'Search failed');
    } finally {
      setLoadingSearch(false);
    }
  };

  const runPhases = async (commit: boolean = false) => {
    setRunning(true);
    setError(null);
    setLastRunResult(null);
    try {
      const effectiveDryRun = commit ? false : dryRun;
      const res = await graphService.runPhases(projectId, { dry_run: effectiveDryRun, min_score: 0.55, min_support: 2 });
      setLastRunResult(res);
      // Refresh maintenance summary after apply
      try {
        const sres = await fetch(`http://localhost:8006/projects/${projectId}/maintenance/summary`, {
          headers: { 'Authorization': 'Bearer service-backend-token' }
        });
        if (sres.ok) {
          setSummary(await sres.json());
        }
      } catch {}
      try {
        const hres = await fetch(`http://localhost:8006/projects/${projectId}/maintenance/history?limit=20`, {
          headers: { 'Authorization': 'Bearer service-backend-token' }
        });
        if (hres.ok) {
          const hval = await hres.json();
          setHistory(hval.items || []);
        }
      } catch {}
    } catch (e: any) {
      const msg = String(e?.message || 'Run phases failed');
      const hint = msg.includes('HTTP 403')
        ? ' (Hint: If GRAPH_ENFORCE_PROJECT_HEADER is enabled, the service requires X-Project-Id to match the URL.)'
        : '';
      setError(`${msg}${hint}`);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="project-explorer-view" style={{ padding: 16 }}>
      <h2>Graph Explorer</h2>
      {error && <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>}
      <section style={{ marginBottom: 24 }}>
        <h3>Overview</h3>
        {loadingOverview && <div>Loading overview…</div>}
        {overview && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, color: '#666' }}>Entities</div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{overview.entity_count}</div>
            </div>
            <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, color: '#666' }}>Relationships</div>
              <div style={{ fontSize: 20, fontWeight: 600 }}>{overview.relationship_count}</div>
            </div>
            <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
              <div style={{ fontSize: 12, color: '#666' }}>Top Entity Types</div>
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                {(overview.top_entity_types || []).map((x) => (
                  <li key={x.type}>{x.type}: {x.count}</li>
                ))}
              </ul>
            </div>
            {/* Project metrics widget spanning full width */}
            <div style={{ gridColumn: '1 / -1' }}>
              <ProjectMetricsWidget projectId={projectId} />
            </div>
            {/* Centrality widget below the three stats, spanning full width on small screens */}
            <div style={{ gridColumn: '1 / -1' }}>
              <TopCentralCanonicalWidget projectId={projectId} limit={10} />
            </div>
          </div>
        )}
      </section>

      <section>
        <h3>Fused Search</h3>
        <form onSubmit={runSearch} style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search entities and content…"
            style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #ccc' }}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={boostCentrality} onChange={(e) => setBoostCentrality(e.target.checked)} />
            Boost centrality
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Weights
            <input
              type="text"
              value={weights}
              onChange={(e) => setWeights(e.target.value)}
              placeholder="entity_cards:1.0,raw_chunks:0.8"
              style={{ width: 240, padding: 6, borderRadius: 6, border: '1px solid #ccc' }}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Centrality scale
            <input
              type="number"
              step="0.01"
              min={0}
              max={1}
              value={centralityScale}
              onChange={(e) => setCentralityScale(Math.max(0, Math.min(1, Number(e.target.value || 0))))}
              style={{ width: 90, padding: 6, borderRadius: 6, border: '1px solid #ccc' }}
            />
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={normalizedCentrality} onChange={(e) => setNormalizedCentrality(e.target.checked)} />
            Normalized
          </label>
          <button type="submit" disabled={loadingSearch || !query.trim()} style={{ padding: '8px 12px' }}>
            {loadingSearch ? 'Searching…' : 'Search'}
          </button>
        </form>
        {results.length > 0 && (
          <div>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>Results: {results.length}</div>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {results.map((r) => (
                <li key={r.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 12, marginBottom: 8 }}>
                  <div style={{ fontWeight: 600 }}>{r.name || r.id}</div>
                  {r.text && <div style={{ color: '#444', marginTop: 6 }}>{r.text}</div>}
                  <div style={{ fontSize: 12, color: '#666', marginTop: 6 }}>
                    Fused score: {r.fused_score.toFixed(4)} · Sources: {(r.sources || []).map(s => s.source).join(', ')}
                  </div>
                  {(r.sources && r.sources.length > 0) && (
                    <div style={{ marginTop: 6 }}>
                      <button type="button" onClick={() => setExpandedIds(prev => ({ ...prev, [r.id]: !prev[r.id] }))} style={{ fontSize: 12 }}>
                        {expandedIds[r.id] ? 'Hide details' : 'Show details'}
                      </button>
                      {expandedIds[r.id] && (
                        <div style={{ marginTop: 6, border: '1px dashed #ddd', borderRadius: 6 }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                              <tr style={{ textAlign: 'left' }}>
                                <th style={{ padding: '6px' }}>Source</th>
                                <th style={{ padding: '6px' }}>Rank</th>
                                <th style={{ padding: '6px' }}>Score</th>
                              </tr>
                            </thead>
                            <tbody>
                              {r.sources.map((s, i) => (
                                <tr key={i}>
                                  <td style={{ padding: '6px' }}>{s.source}</td>
                                  <td style={{ padding: '6px' }}>{s.rank}</td>
                                  <td style={{ padding: '6px' }}>{typeof s.score === 'number' ? s.score.toFixed(4) : String(s.score)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section style={{ marginTop: 24 }}>
        <h3>Maintenance</h3>
        {/* Summary + actions */}
        {summary && (
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
            <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 10 }}>
              <div style={{ fontSize: 12, color: '#666' }}>Entities (unlinked)</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{summary.entities_unlinked ?? '—'}</div>
            </div>
            <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 10 }}>
              <div style={{ fontSize: 12, color: '#666' }}>REFERS_TO edges</div>
              <div style={{ fontSize: 16, fontWeight: 600 }}>{summary.refers_to_edges ?? '—'}</div>
            </div>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
            Dry run
          </label>
          <button onClick={() => runPhases(false)} disabled={running} style={{ padding: '6px 10px' }}>
            {running ? 'Running…' : 'Run Phases (Link + Promote)'}
          </button>
          <button
            onClick={() => {
              if (window.confirm('Apply changes? This will run without dry_run and may write REFERS_TO and canonical relationships.')) {
                runPhases(true);
              }
            }}
            disabled={running}
            style={{ padding: '6px 10px' }}
          >
            {running ? 'Applying…' : 'Commit Apply'}
          </button>
        </div>
        {lastRunResult && (
          <pre style={{ background: '#f7f7f7', padding: 12, borderRadius: 6, maxHeight: 260, overflow: 'auto' }}>
            {JSON.stringify(lastRunResult, null, 2)}
          </pre>
        )}
        {history.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>Recent Runs</div>
            <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom: 6, flexWrap:'wrap' }}>
              <label>
                Page size:
                <input type="number" min={5} max={50} value={historyPageSize} onChange={(e) => setHistoryPageSize(parseInt(e.target.value || '10', 10))} style={{ width: 64, marginLeft: 6 }} />
              </label>
              <label>
                Page:
                <input type="number" min={1} value={historyPage} onChange={(e) => setHistoryPage(parseInt(e.target.value || '1', 10))} style={{ width: 64, marginLeft: 6 }} />
              </label>
            </div>
            <div style={{ overflow: 'auto', border: '1px solid #eee', borderRadius: 8 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ textAlign: 'left' }}>
                    <th style={{ padding: '8px 6px' }}>Timestamp (UTC)</th>
                    <th style={{ padding: '8px 6px' }}>Action</th>
                    <th style={{ padding: '8px 6px' }}>Mode</th>
                    <th style={{ padding: '8px 6px' }}>Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice((historyPage-1)*historyPageSize, (historyPage-1)*historyPageSize + historyPageSize).map((h, idx) => (
                    <tr key={idx}>
                      <td style={{ padding: '6px' }}>{h.ts || ''}</td>
                      <td style={{ padding: '6px' }}>{h.action || ''}</td>
                      <td style={{ padding: '6px' }}>{h.dry_run ? 'dry-run' : 'apply'}</td>
                      <td style={{ padding: '6px' }}>
                        <code style={{ fontSize: 12 }}>
                          {(() => {
                            try { return JSON.stringify(h.summary || {}, null, 0).slice(0, 180); } catch { return ''; }
                          })()}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export default ProjectExplorerView;
