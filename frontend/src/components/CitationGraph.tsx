'use client';

/**
 * Citation graph canvas. The reducers in here implement the full
 * "graph as a living surface" experience documented in AUDIT.md §12 + §13.
 * Effects layer in this priority (later beats earlier in the reducer):
 *
 *   year filter → constellation dim → hover dim → search-pulse tint →
 *   spawn grow-in → pulse amber → breathing (landmarks only)
 *
 * Two render-driven loops:
 *   - rAF loop (60fps) only runs when something dynamic is active
 *     (breathing, spawn animation, search pulse). Idle = no work.
 *   - The reducer is set once per static-state change; the rAF loop
 *     calls sigma.refresh({skipIndexation:true}) to re-evaluate it.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  SigmaContainer,
  useLoadGraph,
  useRegisterEvents,
  useSetSettings,
  useSigma,
} from '@react-sigma/core';
import '@react-sigma/core/lib/react-sigma.min.css';
import Graph, { MultiDirectedGraph } from 'graphology';
import {
  graphApi,
  searchApi,
  GraphFilters,
  GraphResponse,
  SimilarityEdge,
} from '@/lib/api';
import { useInspector } from '@/lib/inspector-store';
import { useGraphFocus, SPAWN_DURATION_MS } from '@/lib/graph-store';
import { buildSigmaGraph, runFa2Worker } from '@/lib/graph-data';
import DashedEdgeProgram from '@/lib/sigma-dashed-edge';
import { cn } from '@/lib/utils';

const PERFORMANCE_WARN_NODES = 1500;
// Edges fade across this similarity window around the threshold (so an
// edge at 0.86 is fully visible at threshold 0.85, half at 0.88,
// invisible at 0.90).
const THRESHOLD_FADE_WINDOW = 0.05;
// How many top-degree nodes get the subtle "breathing" continuous pulse.
const BREATHING_LANDMARKS = 3;

interface Counts {
  visibleEdges: number;
  totalEdges: number;
  citationEdges: number;
  semanticEdges: number;
}

interface CitationGraphProps {
  filters?: GraphFilters;
  semanticThreshold?: number;
  onCounts?: (counts: Counts) => void;
  /** Emits the list of node years so the timeline scrubber can build a
   *  histogram. Called once per graph load. */
  onYears?: (years: number[]) => void;
  /** Fires after the FA2 web worker finishes laying out the graph. The
   *  parent can use this to coordinate other animations (e.g. expand the
   *  inspector panel only after the canvas has settled). */
  onLayoutComplete?: () => void;
}

export default function CitationGraph({
  filters = {},
  semanticThreshold = 0.85,
  onCounts,
  onYears,
  onLayoutComplete,
}: CitationGraphProps) {
  const [citationGraph, setCitationGraph] = useState<GraphResponse | null>(null);
  const [semanticEdges, setSemanticEdges] = useState<SimilarityEdge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const filtersKey = useMemo(() => JSON.stringify(filters), [filters]);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    // Fetch similarity edges with a floor 15pt below the current threshold,
    // capped at 800 edges. Default threshold is 0.85, so we get edges ≥0.70
    // by default — the slider can drop to 0.70 without a refetch. Going
    // lower triggers a refetch (handled by the threshold-changed effect
    // below).
    const fetchFloor = Math.max(0.5, semanticThreshold - 0.15);
    Promise.all([
      graphApi.getGraph(filters),
      searchApi.getSimilarityEdges(fetchFloor, 800).catch(() => [] as SimilarityEdge[]),
    ])
      .then(([cg, sem]) => {
        if (!mounted) return;
        setCitationGraph(cg);
        setSemanticEdges(sem);
        if (onYears) {
          const years = cg.nodes
            .map((n) => n.meta?.year)
            .filter((y): y is number => typeof y === 'number');
          onYears(years);
        }
      })
      .catch(
        (e) =>
          mounted &&
          setError(e instanceof Error ? e.message : 'Failed to load graph'),
      )
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  // Build graph WITHOUT threshold filtering — render-time fade handles it.
  // semanticThreshold is intentionally excluded from the deps so the
  // threshold slider doesn't trigger an O(n²) layout recomputation.
  const graph = useMemo(() => {
    if (!citationGraph) return null;
    return buildSigmaGraph(citationGraph, semanticEdges, { semanticThreshold: 0 });
  }, [citationGraph, semanticEdges]);

  // FA2 layout runs on a web worker so the UI shell stays responsive
  // (sliders, scrolling, the inspector animations all keep moving while
  // the graph settles). `isLaying` controls a dim-and-fade transition on
  // the canvas: 60% opacity + pointer-events:none during layout, fading
  // to full crispness over 300ms when the worker stops.
  const [isLaying, setIsLaying] = useState(false);
  useEffect(() => {
    if (!graph) return;
    setIsLaying(true);
    const cancel = runFa2Worker(graph, () => {
      setIsLaying(false);
      onLayoutComplete?.();
    });
    return cancel;
    // onLayoutComplete is intentionally omitted — we only want a new
    // layout pass when the graph object identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph]);

  // Top-3 landmarks (highest in-degree) for the subtle breathing animation.
  const landmarks = useMemo<string[]>(() => {
    if (!graph) return [];
    const degree: Array<[string, number]> = [];
    graph.forEachNode((node) => {
      degree.push([node, graph.inDegree(node)]);
    });
    degree.sort((a, b) => b[1] - a[1]);
    return degree.slice(0, BREATHING_LANDMARKS).map(([id]) => id);
  }, [graph]);

  useEffect(() => {
    if (!graph || !onCounts) return;
    const visibleSemantic = semanticEdges.filter(
      (e) => e.similarity_score >= semanticThreshold,
    ).length;
    const citationCount = citationGraph?.edges.length ?? 0;
    onCounts({
      visibleEdges: graph.size,
      totalEdges: citationCount + semanticEdges.length,
      citationEdges: citationCount,
      semanticEdges: visibleSemantic,
    });
  }, [graph, citationGraph, semanticEdges, semanticThreshold, onCounts]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        Loading graph…
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-destructive">
        {error}
      </div>
    );
  }
  if (!graph || graph.order === 0) {
    return (
      <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
        No nodes match current filters.
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      {graph.order > PERFORMANCE_WARN_NODES && (
        <div className="absolute left-3 top-3 z-10 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 font-mono text-2xs text-amber-700 dark:text-amber-400">
          {graph.order} nodes — interaction may slow at this scale.
        </div>
      )}
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent('citegraph:fit'))}
        className={cn(
          'absolute right-3 top-3 z-10',
          'rounded-md border border-border bg-background/80 px-2 py-1',
          'text-[11px] text-muted-foreground backdrop-blur-sm transition-colors duration-150',
          'hover:bg-background hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        )}
        aria-label="Fit graph to view"
        title="Fit graph to view"
      >
        Fit view
      </button>
      <ConstellationExitOverlay />

      {/* "Laying out graph…" toast surfaces while the FA2 worker runs.
          Lives above the canvas (z-20) so it's not affected by the
          opacity dim. Disappears the moment layout completes. The
          shell — sidebar, inspector, top bar — stays fully interactive
          throughout because the layout is on a web worker. */}
      {isLaying && (
        <div
          className={cn(
            'pointer-events-none absolute left-1/2 top-3 z-20 -translate-x-1/2',
            'rounded-md border border-border bg-background/85 px-2.5 py-1',
            'text-[11px] text-muted-foreground backdrop-blur-sm shadow-sm',
            'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-150',
          )}
          role="status"
          aria-live="polite"
        >
          Laying out graph…
        </div>
      )}

      <div
        className={cn(
          // Canvas sits behind everything; dim + disable interaction
          // while the worker churns, then fade back to full opacity.
          'h-full w-full transition-opacity duration-300 motion-reduce:transition-none',
          isLaying
            ? 'pointer-events-none opacity-60'
            : 'pointer-events-auto opacity-100',
        )}
      >
      <SigmaContainer
        graph={MultiDirectedGraph}
        style={{ width: '100%', height: '100%', background: 'transparent' }}
        settings={{
          renderEdgeLabels: false,
          defaultEdgeColor: '#94a3b8',
          defaultNodeColor: '#64748b',
          labelColor: { color: '#475569' },
          labelSize: 11,
          labelWeight: '500',
          labelDensity: 0.7,
          labelGridCellSize: 120,
          labelRenderedSizeThreshold:
            graph.order >= 200 ? 12 : graph.order >= 100 ? 8 : 5,
          hideEdgesOnMove: true,
          hideLabelsOnMove: true,
          enableEdgeEvents: false,
          // Register the dashed-edge program. Citation edges keep using
          // sigma's built-in 'arrow' / 'line' programs; semantic edges set
          // type:'dashed' in graph-data.ts and route through this program.
          edgeProgramClasses: {
            dashed: DashedEdgeProgram,
          },
        }}
      >
        <GraphLoader graph={graph} />
        <GraphEvents onHoverNode={setHoveredNode} />
        <CameraFocus />
        <CameraFitController />
        <ConstellationCamera />
        <InitialLandmarkZoom landmarks={landmarks} />
        <EffectsReducer
          hoveredNode={hoveredNode}
          semanticThreshold={semanticThreshold}
          landmarks={landmarks}
        />
        <SessionTrailOverlay />
      </SigmaContainer>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loader / events / camera
// ---------------------------------------------------------------------------

function GraphLoader({ graph }: { graph: Graph }) {
  const load = useLoadGraph();
  useEffect(() => {
    load(graph);
  }, [load, graph]);
  return null;
}

function GraphEvents({
  onHoverNode,
}: {
  onHoverNode: (node: string | null) => void;
}) {
  const sigma = useSigma();
  const registerEvents = useRegisterEvents();
  const inspector = useInspector();

  useEffect(() => {
    registerEvents({
      clickNode: ({ node }) => inspector.show({ kind: 'document', id: node }),
      clickEdge: ({ edge }) => {
        const graph = sigma.getGraph();
        const attrs = graph.getEdgeAttributes(edge);
        const source = graph.source(edge);
        const target = graph.target(edge);
        if (attrs.kind === 'semantic') {
          inspector.show({
            kind: 'similarity',
            sourceId: source,
            targetId: target,
            score: (attrs.similarityScore as number | undefined) ?? 0,
          });
        } else {
          inspector.show({ kind: 'citation', id: edge, documentId: source });
        }
      },
      enterNode: ({ node }) => onHoverNode(node),
      leaveNode: () => onHoverNode(null),
    });
  }, [registerEvents, inspector, sigma, onHoverNode]);
  return null;
}

/**
 * Camera animation for pulse() — implements the "overshoot and settle"
 * pattern from the design brief: the camera zooms past the target then
 * eases back, which feels physical instead of mechanical.
 */
function CameraFocus() {
  const sigma = useSigma();
  const focusedNodeIds = useGraphFocus((s) => s.focusedNodeIds);
  const focusToken = useGraphFocus((s) => s.focusToken);

  useEffect(() => {
    if (!focusToken || focusedNodeIds.length === 0) return;
    const graph = sigma.getGraph();
    const xs: number[] = [];
    const ys: number[] = [];
    for (const id of focusedNodeIds) {
      if (!graph.hasNode(id)) continue;
      const a = graph.getNodeAttributes(id);
      xs.push(a.x);
      ys.push(a.y);
    }
    if (xs.length === 0) return;
    const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
    const cy = ys.reduce((a, b) => a + b, 0) / ys.length;
    const camera = sigma.getCamera();
    // Phase 1: zoom past (slightly tighter than final ratio, slight offset).
    camera.animate({ x: cx, y: cy, ratio: 0.32 }, { duration: 350 });
    // Phase 2: settle back.
    const timer = window.setTimeout(() => {
      camera.animate({ x: cx, y: cy, ratio: 0.4 }, { duration: 200 });
    }, 360);
    return () => window.clearTimeout(timer);
  }, [sigma, focusedNodeIds, focusToken]);
  return null;
}

/**
 * Camera animation for constellation mode — fits the focused case +
 * its neighbours when constellation enters; reset to full graph when
 * exiting.
 */
function ConstellationCamera() {
  const sigma = useSigma();
  const constellationFocus = useGraphFocus((s) => s.constellationFocus);

  useEffect(() => {
    const camera = sigma.getCamera();
    if (constellationFocus === null) {
      // Exit: zoom back out to fit everything.
      try {
        camera.animatedReset({ duration: 500 });
      } catch {
        // ignore
      }
      return;
    }
    const graph = sigma.getGraph();
    if (!graph.hasNode(constellationFocus)) return;
    const set = new Set<string>([
      constellationFocus,
      ...graph.neighbors(constellationFocus),
    ]);
    const xs: number[] = [];
    const ys: number[] = [];
    for (const id of set) {
      const a = graph.getNodeAttributes(id);
      xs.push(a.x);
      ys.push(a.y);
    }
    if (xs.length === 0) return;
    const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
    const cy = ys.reduce((a, b) => a + b, 0) / ys.length;
    camera.animate({ x: cx, y: cy, ratio: 0.25 }, { duration: 600 });
  }, [sigma, constellationFocus]);
  return null;
}

function ConstellationExitOverlay() {
  const constellationFocus = useGraphFocus((s) => s.constellationFocus);
  const setConstellation = useGraphFocus((s) => s.setConstellation);
  if (constellationFocus === null) return null;
  return (
    <button
      type="button"
      onClick={() => setConstellation(null)}
      className={cn(
        'absolute left-1/2 top-3 z-20 -translate-x-1/2',
        'rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5',
        'text-[11px] font-medium text-amber-700 dark:text-amber-400',
        'backdrop-blur-sm transition-colors duration-150',
        'hover:bg-amber-500/15',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500/50',
        'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1',
      )}
    >
      Exit constellation view
    </button>
  );
}

/**
 * On initial load, zoom in to the top-5 most-cited cases instead of the
 * full graph. Gives the user a sense of orientation before showing
 * everything. Triggered exactly once after the first sigma settle.
 */
function InitialLandmarkZoom({ landmarks }: { landmarks: string[] }) {
  const sigma = useSigma();
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    if (landmarks.length === 0) return;
    ranRef.current = true;
    const graph = sigma.getGraph();
    const xs: number[] = [];
    const ys: number[] = [];
    for (const id of landmarks) {
      if (!graph.hasNode(id)) continue;
      const a = graph.getNodeAttributes(id);
      xs.push(a.x);
      ys.push(a.y);
    }
    if (xs.length === 0) return;
    const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
    const cy = ys.reduce((a, b) => a + b, 0) / ys.length;
    const timer = window.setTimeout(() => {
      sigma.getCamera().animate({ x: cx, y: cy, ratio: 0.55 }, { duration: 700 });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [sigma, landmarks]);
  return null;
}

function CameraFitController() {
  const sigma = useSigma();
  useEffect(() => {
    const fit = () => {
      try {
        sigma.getCamera().animatedReset({ duration: 400 });
      } catch {
        // ignore
      }
    };
    window.addEventListener('citegraph:fit', fit);
    return () => window.removeEventListener('citegraph:fit', fit);
  }, [sigma]);
  return null;
}

// ---------------------------------------------------------------------------
// The unified effects reducer — handles every simultaneous overlay.
// ---------------------------------------------------------------------------

interface EffectsReducerProps {
  hoveredNode: string | null;
  semanticThreshold: number;
  landmarks: string[];
}

function EffectsReducer({
  hoveredNode,
  semanticThreshold,
  landmarks,
}: EffectsReducerProps) {
  const setSettings = useSetSettings();
  const sigma = useSigma();

  const highlightedNodeId = useGraphFocus((s) => s.highlightedNodeId);
  const constellationFocus = useGraphFocus((s) => s.constellationFocus);
  const searchPulseIds = useGraphFocus((s) => s.searchPulseIds);
  const yearRange = useGraphFocus((s) => s.yearRange);
  const spawnIds = useGraphFocus((s) => s.spawnIds);

  // The rAF phase ref is mutated each frame and read inside the reducer.
  // We never store it in state because that would re-run setSettings on
  // every frame — too expensive. Instead we set the reducer once and
  // schedule sigma.refresh per frame.
  const phaseRef = useRef(0);

  useEffect(() => {
    const graph = sigma.getGraph();

    const hoverNeighbours = hoveredNode
      ? new Set<string>([hoveredNode, ...graph.neighbors(hoveredNode)])
      : null;

    const constellationSet = constellationFocus
      ? new Set<string>([
          constellationFocus,
          ...graph.neighbors(constellationFocus),
        ])
      : null;

    const landmarkSeed = new Map<string, number>();
    landmarks.forEach((id, i) => landmarkSeed.set(id, i * 0.7));

    setSettings({
      nodeReducer: (node, data) => {
        const yr = (data as { year?: number | null }).year;

        // Year filter: nodes outside the active range ghost. Hover and
        // pulse can override later in the chain.
        let dimmedByYear = false;
        if (yearRange && typeof yr === 'number') {
          if (yr < yearRange[0] || yr > yearRange[1]) dimmedByYear = true;
        }

        // Pulse beats everything else.
        if (highlightedNodeId && node === highlightedNodeId) {
          return {
            ...data,
            size: (data.size ?? 6) * 1.8,
            color: '#f59e0b',
            zIndex: 10,
            highlighted: true,
          };
        }

        // Spawn animation: scale 0 → 1 over SPAWN_DURATION_MS.
        const spawnStart = spawnIds.get(node);
        if (spawnStart) {
          const t = Math.min(1, (Date.now() - spawnStart) / SPAWN_DURATION_MS);
          // ease-out quad
          const eased = 1 - (1 - t) * (1 - t);
          return {
            ...data,
            size: (data.size ?? 6) * eased,
            color: t < 0.7 ? '#f59e0b' : data.color,
            zIndex: 8,
          };
        }

        // Constellation: anything outside the focus + its neighbours
        // recedes to small + low contrast.
        if (constellationSet && !constellationSet.has(node)) {
          return {
            ...data,
            color: '#e2e8f0', // slate-200, very faint
            label: '',
            size: Math.max(1.5, (data.size ?? 6) * 0.25),
            zIndex: 0,
          };
        }

        // Hover: dim non-neighbours.
        if (hoverNeighbours && !hoverNeighbours.has(node)) {
          return {
            ...data,
            color: '#cbd5e1',
            label: '',
            size: Math.max(2, (data.size ?? 6) * 0.6),
            zIndex: 0,
          };
        }

        // Compose ambient effects (search pulse, breathing, year dim) on
        // a node that survived all the dimming filters above.
        let size = data.size ?? 6;
        let color = data.color ?? '#64748b';
        let zIndex = data.zIndex ?? 1;
        let forceLabel = false;

        // Search pulse: subtle amber tint + slight grow on matching nodes.
        if (searchPulseIds.size > 0 && searchPulseIds.has(node)) {
          const pulse = 0.5 + 0.5 * Math.sin(phaseRef.current * 4);
          size *= 1.1 + pulse * 0.15;
          color = '#f59e0b';
          zIndex = Math.max(zIndex, 4);
          forceLabel = true;
        }

        // Breathing: top-N landmarks gently pulse continuously. Only
        // applied when no other state override is active for the node.
        const seed = landmarkSeed.get(node);
        if (seed != null) {
          const breathe = 0.5 + 0.5 * Math.sin(phaseRef.current + seed);
          size *= 1 + breathe * 0.06;
        }

        // Hover focal node: bump + force label.
        if (hoveredNode === node) {
          size *= 1.25;
          zIndex = Math.max(zIndex, 5);
          forceLabel = true;
        }

        if (dimmedByYear) {
          color = '#cbd5e1';
          size = Math.max(2, size * 0.6);
          zIndex = 0;
          forceLabel = false;
        }

        return { ...data, size, color, zIndex, forceLabel };
      },
      edgeReducer: (edge, data) => {
        const source = graph.source(edge);
        const target = graph.target(edge);
        const kind = (data as { kind?: string }).kind;
        const score = (data as { similarityScore?: number }).similarityScore ?? 0;

        // Hover: only edges touching the hovered node survive.
        if (hoverNeighbours) {
          if (source !== hoveredNode && target !== hoveredNode) {
            return { ...data, hidden: true };
          }
          return { ...data, zIndex: 5, size: (data.size ?? 1) * 1.5 };
        }

        // Constellation: only edges within the focus set survive.
        if (constellationSet) {
          if (
            !constellationSet.has(source) ||
            !constellationSet.has(target)
          ) {
            return { ...data, hidden: true };
          }
        }

        // Year filter: hide edges where either endpoint is outside the
        // active year window.
        if (yearRange) {
          const sy = graph.getNodeAttribute(source, 'year') as
            | number
            | null
            | undefined;
          const ty = graph.getNodeAttribute(target, 'year') as
            | number
            | null
            | undefined;
          const inRange = (y: number | null | undefined) =>
            y == null || (y >= yearRange[0] && y <= yearRange[1]);
          if (!inRange(sy) || !inRange(ty)) {
            return { ...data, hidden: true };
          }
        }

        // Continuous threshold fade for semantic edges.
        if (kind === 'semantic') {
          const t = Math.max(
            0,
            Math.min(
              1,
              (score - semanticThreshold + THRESHOLD_FADE_WINDOW) /
                (2 * THRESHOLD_FADE_WINDOW),
            ),
          );
          if (t <= 0) return { ...data, hidden: true };
          // Re-encode the alpha into the colour so Sigma's renderer
          // respects it (Sigma 2.x doesn't have a per-edge alpha
          // setting; alpha lives in the colour's last channel).
          const baseAlpha = 0.7;
          const alpha = baseAlpha * t;
          const a = Math.round(alpha * 255)
            .toString(16)
            .padStart(2, '0');
          return { ...data, color: `#10b981${a}` };
        }
        return data;
      },
    });
  }, [
    setSettings,
    sigma,
    hoveredNode,
    highlightedNodeId,
    constellationFocus,
    searchPulseIds,
    yearRange,
    spawnIds,
    landmarks,
    semanticThreshold,
  ]);

  // rAF loop — only runs when something dynamic is active. Three perf
  // discipline knobs:
  //   1. Cap to 30fps for ambient-only animations (breathing). The eye
  //      can't tell the difference for a slow sine wave, but 30fps
  //      halves the canvas redraw cost.
  //   2. Pause when document.hidden — saves CPU on background tabs.
  //   3. Skip entirely if prefers-reduced-motion.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const reduced = window.matchMedia(
      '(prefers-reduced-motion: reduce)',
    ).matches;
    if (reduced) return;

    const dynamic =
      landmarks.length > 0 || searchPulseIds.size > 0 || spawnIds.size > 0;
    if (!dynamic) return;

    // Spawn animations are short-lived (700ms) and visible — render them
    // at 60fps so the grow-in feels smooth. Ambient breathing alone goes
    // to 30fps because the human eye cannot tell at sine-wave speeds.
    const wantHighFps = searchPulseIds.size > 0 || spawnIds.size > 0;
    const targetFrameMs = wantHighFps ? 16 : 33;

    let raf = 0;
    let lastTick = 0;
    const tick = (now: number) => {
      if (document.hidden) {
        raf = requestAnimationFrame(tick);
        return;
      }
      if (now - lastTick >= targetFrameMs) {
        lastTick = now;
        phaseRef.current = (now / 1500) % (2 * Math.PI);
        try {
          sigma.scheduleRefresh({ skipIndexation: true });
        } catch {
          try {
            sigma.refresh();
          } catch {
            // ignore
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [sigma, landmarks, searchPulseIds, spawnIds]);

  return null;
}

// ---------------------------------------------------------------------------
// Session trail — faint polyline of pulsed nodes in chronological order.
// Drawn as an SVG overlay so it inherits CSS animations and theming
// without going through Sigma's WebGL path.
// ---------------------------------------------------------------------------

function SessionTrailOverlay() {
  const sigma = useSigma();
  const trail = useGraphFocus((s) => s.trail);
  const [points, setPoints] = useState<Array<{ x: number; y: number; t: number }>>([]);

  useEffect(() => {
    if (trail.length < 2) {
      setPoints([]);
      return;
    }
    const compute = () => {
      const graph = sigma.getGraph();
      const out: Array<{ x: number; y: number; t: number }> = [];
      for (const entry of trail) {
        if (!graph.hasNode(entry.id)) continue;
        try {
          const v = sigma.graphToViewport({
            x: graph.getNodeAttribute(entry.id, 'x') as number,
            y: graph.getNodeAttribute(entry.id, 'y') as number,
          });
          out.push({ x: v.x, y: v.y, t: entry.t });
        } catch {
          // ignore
        }
      }
      setPoints(out);
    };
    compute();
    const camera = sigma.getCamera();
    camera.on('updated', compute);
    return () => {
      camera.off('updated', compute);
    };
  }, [sigma, trail]);

  if (points.length < 2) return null;
  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(' ');

  return (
    <svg
      className="pointer-events-none absolute inset-0 z-10 h-full w-full"
      aria-hidden
    >
      <path
        d={pathD}
        fill="none"
        stroke="rgb(245 158 11 / 0.45)"
        strokeWidth={1.25}
        strokeDasharray="4 4"
        strokeLinecap="round"
      />
      {points.map((p, i) => (
        <circle
          key={i}
          cx={p.x}
          cy={p.y}
          r={i === points.length - 1 ? 4 : 2.5}
          fill="rgb(245 158 11 / 0.5)"
        />
      ))}
    </svg>
  );
}
