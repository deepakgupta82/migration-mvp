import React, { useEffect, useState } from 'react';
import { graphService, CanonicalCentrality } from '../../services/GraphService';

export const TopCentralCanonicalWidget: React.FC<{ projectId: string; limit?: number }> = ({ projectId, limit = 10 }) => {
  const [data, setData] = useState<CanonicalCentrality | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await graphService.getCanonicalCentrality(projectId, limit);
        if (mounted) setData(res);
      } catch (e: any) {
        if (mounted) setError(e?.message || 'Failed to load centrality');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, [projectId, limit]);

  return (
    <div style={{ border: '1px solid #eee', borderRadius: 8, padding: 12 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>Top Central Canonical Entities</div>
      {loading && <div>Loading…</div>}
      {error && <div style={{ color: 'red' }}>{error}</div>}
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left' }}>
              <th style={{ padding: '6px 4px' }}>Name</th>
              <th style={{ padding: '6px 4px' }}>Total</th>
              <th style={{ padding: '6px 4px' }}>Out</th>
              <th style={{ padding: '6px 4px' }}>In</th>
            </tr>
          </thead>
          <tbody>
            {(data.items || []).slice(0, limit).map((it) => (
              <tr key={it.id}>
                <td style={{ padding: '4px' }}>{it.name || it.id}</td>
                <td style={{ padding: '4px' }}>{it.total_degree}</td>
                <td style={{ padding: '4px' }}>{it.out_degree}</td>
                <td style={{ padding: '4px' }}>{it.in_degree}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default TopCentralCanonicalWidget;
