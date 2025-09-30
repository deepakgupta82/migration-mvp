import React, { useEffect, useState } from 'react';
import { graphService } from '../../services/GraphService';

interface Props { projectId: string }

const fmtPct = (v?: number) => (typeof v === 'number' ? `${Math.round(v * 100)}%` : '—');

const Card: React.FC<{ title: string; value: string } & React.HTMLAttributes<HTMLDivElement>> = ({ title, value, ...rest }) => (
  <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12, minWidth: 160 }} {...rest}>
    <div style={{ fontSize: 12, color: '#666' }}>{title}</div>
    <div style={{ fontSize: 20, fontWeight: 600 }}>{value}</div>
  </div>
);

const ProjectMetricsWidget: React.FC<Props> = ({ projectId }) => {
  const [metrics, setMetrics] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setError(null);
      try {
        const m = await graphService.getProjectMetrics(projectId);
        if (mounted) setMetrics(m);
      } catch (e: any) {
        setError(e?.message || 'Failed to load metrics');
      }
    };
    load();
    const id = setInterval(load, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, [projectId]);

  if (error) return <div style={{ color: 'red' }}>{error}</div>;
  if (!metrics) return <div>Loading metrics…</div>;

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <Card title="Link coverage" value={fmtPct(metrics.link_coverage)} />
      <Card title="NL→Cypher pass-rate" value={fmtPct(metrics.nl2cypher_pass_rate)} />
      <Card title="Extraction yield" value={fmtPct(metrics.extraction_yield)} />
      <Card title="Schema conformance" value={fmtPct(metrics.schema_conformance)} />
    </div>
  );
};

export default ProjectMetricsWidget;
