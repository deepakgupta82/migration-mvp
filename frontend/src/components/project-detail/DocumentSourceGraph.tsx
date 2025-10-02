/**
 * DocumentSourceGraph Component
 * 
 * Provides document-filtered view of the knowledge graph.
 * Features:
 * - Document dropdown selector showing all processed documents
 * - Filtered graph view showing only entities from selected document
 * - Document metadata display (filename, entity count)
 * - Trace information back to source
 */

import React, { useEffect, useState } from 'react';
import { Alert, Card, Group, Loader, Text, Select, Stack, Badge } from '@mantine/core';
import { IconAlertCircle, IconFileText } from '@tabler/icons-react';
import ForceGraph2D from 'react-force-graph-2d';
import {
  apiService,
  DocumentSourceGraphData,
  ProjectDocumentsResponse,
  DocumentInfo,
  GraphNode,
} from '../../services/api';

interface DocumentSourceGraphProps {
  projectId: string;
}

export const DocumentSourceGraph: React.FC<DocumentSourceGraphProps> = ({ projectId }) => {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<string | null>(null);
  const [graphData, setGraphData] = useState<DocumentSourceGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDocuments = async () => {
      setLoading(true);
      setError(null);
      try {
        const response: ProjectDocumentsResponse = await apiService.getProjectDocuments(projectId);
        setDocuments(response.documents || []);
        
        // Auto-select first document if available
        if (response.documents && response.documents.length > 0) {
          setSelectedDocument(response.documents[0].document_id);
        }
      } catch (err: any) {
        console.error('Failed to load documents:', err);
        setError(err.message || 'Failed to load documents');
      } finally {
        setLoading(false);
      }
    };

    loadDocuments();
  }, [projectId]);

  useEffect(() => {
    const loadGraphForDocument = async (documentId: string) => {
      setGraphLoading(true);
      try {
        const data = await apiService.getDocumentSourceGraph(projectId, documentId);
        setGraphData({
          ...data,
          links: data.edges || data.links || [],
        });
      } catch (err: any) {
        console.error('Failed to load document graph:', err);
        setError(err.message || 'Failed to load graph data');
      } finally {
        setGraphLoading(false);
      }
    };

    if (selectedDocument) {
      loadGraphForDocument(selectedDocument);
    }
  }, [selectedDocument, projectId]);

  // Node color by entity type
  const getNodeColor = (node: GraphNode) => {
    const typeColorMap: Record<string, string> = {
      Platform: '#ff6b6b',
      Application: '#4dabf7',
      Server: '#51cf66',
      IP: '#ffd43b',
      OS: '#ff922b',
      Database: '#9775fa',
      Service: '#22b8cf',
    };
    return typeColorMap[node.type] || '#868e96';
  };

  // Node size by degree - increased for better visibility
  const getNodeSize = (node: GraphNode) => {
    const degree = (node as any).degree || 1;
    // Scale: min 10px, max 35px
    return Math.max(10, Math.min(35, 10 + degree * 2));
  };

  if (loading) {
    return (
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Group justify="center" style={{ minHeight: '400px' }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Loading documents...</Text>
          </Stack>
        </Group>
      </Card>
    );
  }

  if (error && documents.length === 0) {
    return (
      <Alert icon={<IconAlertCircle size={16} />} title="Error" color="red">
        {error}
      </Alert>
    );
  }

  if (documents.length === 0) {
    return (
      <Alert icon={<IconFileText size={16} />} title="No Documents" color="blue">
        No documents have been processed for this project yet. 
        Upload and process documents to view document-specific graphs.
      </Alert>
    );
  }

  const selectedDocInfo = documents.find((d) => d.document_id === selectedDocument);

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      {/* Document Selector */}
      <Group mb="md" align="flex-start">
        <Select
          label="Select Source Document"
          placeholder="Choose a document"
          data={documents.map((doc) => ({
            value: doc.document_id,
            label: `${doc.filename} (${doc.entity_count} entities)`,
          }))}
          value={selectedDocument}
          onChange={(value) => setSelectedDocument(value)}
          style={{ flex: 1, minWidth: '300px' }}
        />
        
        {selectedDocInfo && (
          <Stack gap="xs" style={{ marginTop: '24px' }}>
            <Badge color="grape" variant="light">
              {selectedDocInfo.entity_count} entities
            </Badge>
            {graphData && (
              <Badge color="violet" variant="light">
                {graphData.stats.relationship_count} relationships
              </Badge>
            )}
          </Stack>
        )}
      </Group>

      {/* Document Metadata */}
      {selectedDocInfo && (
        <Group mb="md" gap="xs">
          <Text size="sm" fw={500}>Document:</Text>
          <Text size="sm" c="dimmed">{selectedDocInfo.filename}</Text>
        </Group>
      )}

      {/* Graph Loading State */}
      {graphLoading && (
        <Group justify="center" style={{ minHeight: '400px' }}>
          <Stack align="center" gap="md">
            <Loader size="lg" />
            <Text size="sm" c="dimmed">Loading graph for document...</Text>
          </Stack>
        </Group>
      )}

      {/* Graph Visualization */}
      {!graphLoading && graphData && graphData.nodes.length > 0 && (
        <>
          <div style={{ width: '100%', height: '700px', marginBottom: '1rem', backgroundColor: '#f8f9fa' }}>
            <ForceGraph2D
              graphData={{
                nodes: graphData.nodes,
                links: graphData.links || graphData.edges,
              }}
              nodeLabel={(node: any) => {
                const n = node as GraphNode;
                return `${(n as any).name || n.label || n.id}\nType: ${n.type || 'Unknown'}\nDocument: ${graphData.document_filename}`;
              }}
              nodeColor={(node: any) => getNodeColor(node as GraphNode)}
              nodeVal={(node: any) => getNodeSize(node as GraphNode)}
              linkDirectionalArrowLength={6}
              linkDirectionalArrowRelPos={1}
              linkColor={() => 'rgba(200, 200, 200, 0.5)'}
              linkWidth={1.5}
              d3AlphaDecay={0.01}
              d3VelocityDecay={0.2}
              cooldownTicks={150}
              onNodeClick={(node: any) => {
                console.log('Node clicked:', node);
              }}
              nodeCanvasObject={(node: any, ctx, globalScale) => {
                const n = node as any;
                const label = n.name || n.label || n.id;
                const nodeSize = getNodeSize(node as GraphNode);

                // Draw node with border
                ctx.beginPath();
                ctx.arc(n.x, n.y, nodeSize, 0, 2 * Math.PI);
                ctx.fillStyle = getNodeColor(node as GraphNode);
                ctx.fill();
                ctx.strokeStyle = '#ffffff';
                ctx.lineWidth = 2;
                ctx.stroke();

                // Draw label with background
                if (globalScale >= 0.8) {
                  const fontSize = Math.max(10, 14 / globalScale);
                  ctx.font = `bold ${fontSize}px Arial, Sans-Serif`;
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'top';
                  
                  const textWidth = ctx.measureText(label).width;
                  const padding = 4;
                  const bgHeight = fontSize + padding * 2;
                  const bgY = n.y + nodeSize + 4;
                  
                  // Background
                  ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                  ctx.fillRect(n.x - textWidth / 2 - padding, bgY, textWidth + padding * 2, bgHeight);
                  
                  // Border
                  ctx.strokeStyle = 'rgba(0, 0, 0, 0.2)';
                  ctx.lineWidth = 1;
                  ctx.strokeRect(n.x - textWidth / 2 - padding, bgY, textWidth + padding * 2, bgHeight);
                  
                  // Text
                  ctx.fillStyle = '#1a1a1a';
                  ctx.fillText(label, n.x, bgY + padding);
                }
              }}
              enableNodeDrag={true}
              enableZoomInteraction={true}
              enablePanInteraction={true}
            />
          </div>

          <Text size="xs" c="dimmed">
            💡 Tip: All entities shown were extracted from <strong>{graphData.document_filename}</strong>. 
            This view helps trace information back to its source document. Drag nodes to explore connections.
          </Text>
        </>
      )}

      {!graphLoading && graphData && graphData.nodes.length === 0 && (
        <Alert icon={<IconFileText size={16} />} title="No Entities" color="blue">
          No entities found in the selected document graph.
        </Alert>
      )}
    </Card>
  );
};

export default DocumentSourceGraph;
