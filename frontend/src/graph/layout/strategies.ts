/**
 * Layout Strategies for Unified Graph Views
 * Each strategy positions nodes based on view-specific algorithms
 */
import * as d3 from 'd3';
import { UnifiedNode, UnifiedEdge } from '../types';

export interface LayoutResult {
  nodes: UnifiedNode[];
  simulation?: d3.Simulation<UnifiedNode, undefined>;
}

/**
 * Knowledge View: Force-directed layout with collision and charge scaling
 * High-degree nodes are pinned after stabilization
 */
export function forceLayout(
  nodes: UnifiedNode[],
  edges: UnifiedEdge[],
  width: number,
  height: number
): LayoutResult {
  const simulation = d3
    .forceSimulation(nodes)
    .force(
      'link',
      d3
        .forceLink<UnifiedNode, UnifiedEdge>(edges)
        .id((d) => d.id)
        .distance(100)
    )
    .force('charge', d3.forceManyBody().strength((d) => -((d as UnifiedNode).metrics?.degree || 10) * 10))
    .force('collision', d3.forceCollide().radius(30))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .alpha(0.5)
    .alphaDecay(0.02);

  // Pin high-degree nodes after 300 ticks
  let ticks = 0;
  simulation.on('tick', () => {
    ticks++;
    if (ticks === 300) {
      nodes.forEach((n) => {
        if ((n.metrics?.degree || 0) > 5) {
          n.fx = n.x;
          n.fy = n.y;
        }
      });
    }
  });

  return { nodes, simulation };
}

/**
 * Infrastructure View: Layered horizontal swimlanes by level
 * Levels from backend (0-3), y-coordinate assigned per level
 */
export function layeredLayout(
  nodes: UnifiedNode[],
  edges: UnifiedEdge[],
  width: number,
  height: number
): LayoutResult {
  const levels = new Map<number, UnifiedNode[]>();
  nodes.forEach((n) => {
    const level = n.level ?? 0;
    if (!levels.has(level)) levels.set(level, []);
    levels.get(level)!.push(n);
  });

  const levelCount = Math.max(...Array.from(levels.keys()), 0) + 1;
  const layerHeight = height / (levelCount + 1);

  levels.forEach((levelNodes, level) => {
    const xSpacing = width / (levelNodes.length + 1);
    levelNodes.forEach((n, i) => {
      n.x = xSpacing * (i + 1);
      n.y = layerHeight * (level + 1);
    });
  });

  return { nodes };
}

/**
 * Platform View: Radial concentric rings by level
 * Center = Platform (level 0), rings expand outward
 */
export function radialLayout(
  nodes: UnifiedNode[],
  edges: UnifiedEdge[],
  width: number,
  height: number
): LayoutResult {
  const centerX = width / 2;
  const centerY = height / 2;
  const maxRadius = Math.min(width, height) / 2 - 50;

  const levels = new Map<number, UnifiedNode[]>();
  nodes.forEach((n) => {
    const level = n.level ?? 0;
    if (!levels.has(level)) levels.set(level, []);
    levels.get(level)!.push(n);
  });

  const levelCount = Math.max(...Array.from(levels.keys()), 0) + 1;

  levels.forEach((levelNodes, level) => {
    const radius = (maxRadius / levelCount) * (level + 1);
    const angleStep = (2 * Math.PI) / levelNodes.length;
    levelNodes.forEach((n, i) => {
      const angle = angleStep * i;
      n.x = centerX + radius * Math.cos(angle);
      n.y = centerY + radius * Math.sin(angle);
    });
  });

  return { nodes };
}

/**
 * Environment View: Partition layout with columns per environment
 * Cross-environment edges highlighted
 */
export function partitionLayout(
  nodes: UnifiedNode[],
  edges: UnifiedEdge[],
  width: number,
  height: number
): LayoutResult {
  const envs = new Map<string, UnifiedNode[]>();
  nodes.forEach((n) => {
    const env = n.environment || 'default';
    if (!envs.has(env)) envs.set(env, []);
    envs.get(env)!.push(n);
  });

  const envCount = envs.size;
  const colWidth = width / envCount;

  Array.from(envs.entries()).forEach(([env, envNodes], colIdx) => {
    const xCenter = colWidth * colIdx + colWidth / 2;
    const ySpacing = height / (envNodes.length + 1);
    envNodes.forEach((n, i) => {
      n.x = xCenter;
      n.y = ySpacing * (i + 1);
    });
  });

  return { nodes };
}

/**
 * Document View: Radial star with document center pinned
 * Ring 0 = document, ring 1 = entities, ring 2 = related
 */
export function radialDocumentLayout(
  nodes: UnifiedNode[],
  edges: UnifiedEdge[],
  width: number,
  height: number,
  documentId?: string
): LayoutResult {
  const centerX = width / 2;
  const centerY = height / 2;
  const maxRadius = Math.min(width, height) / 2 - 50;

  const rings = new Map<number, UnifiedNode[]>();
  nodes.forEach((n) => {
    const ring = n.ring ?? (n.id === documentId ? 0 : 1);
    if (!rings.has(ring)) rings.set(ring, []);
    rings.get(ring)!.push(n);
  });

  rings.forEach((ringNodes, ring) => {
    if (ring === 0) {
      // Center document
      ringNodes.forEach((n) => {
        n.x = centerX;
        n.y = centerY;
        n.fx = centerX;
        n.fy = centerY;
      });
    } else {
      const radius = (maxRadius / 2) * ring;
      const angleStep = (2 * Math.PI) / ringNodes.length;
      ringNodes.forEach((n, i) => {
        const angle = angleStep * i;
        n.x = centerX + radius * Math.cos(angle);
        n.y = centerY + radius * Math.sin(angle);
      });
    }
  });

  return { nodes };
}

/**
 * Apply cached positions from localStorage if available
 */
export function applyCachedPositions(nodes: UnifiedNode[], cacheKey: string): UnifiedNode[] {
  try {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      const positions = JSON.parse(cached) as Record<string, { x: number; y: number }>;
      nodes.forEach((n) => {
        if (positions[n.id]) {
          n.x = positions[n.id].x;
          n.y = positions[n.id].y;
        }
      });
    }
  } catch (e) {
    console.warn('Failed to load cached positions:', e);
  }
  return nodes;
}

/**
 * Save current positions to localStorage
 */
export function cachePositions(nodes: UnifiedNode[], cacheKey: string): void {
  try {
    const positions: Record<string, { x: number; y: number }> = {};
    nodes.forEach((n) => {
      if (n.x !== undefined && n.y !== undefined) {
        positions[n.id] = { x: n.x, y: n.y };
      }
    });
    localStorage.setItem(cacheKey, JSON.stringify(positions));
  } catch (e) {
    console.warn('Failed to cache positions:', e);
  }
}
