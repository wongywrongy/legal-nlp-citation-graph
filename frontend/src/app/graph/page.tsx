'use client';

/**
 * Graph page — the product's core canvas.
 *
 * Layout invariants:
 *   • Toolbar (h-12) at top — counts on left, similarity slider center, filters right
 *   • Empty state when stats.total_documents == 0 — toolbar + canvas hidden
 *   • Bottom-left legend overlay — always visible when canvas is mounted
 *   • Inline notice next to slider when zero semantic edges at current threshold
 *
 * Deep-links handled:
 *   ?focus=<id>  pulse a specific node + open inspector
 *   ?q=<query>   run semantic search, focus camera on hit set
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import {
  ArrowRight,
  Loader2,
  Network,
  SlidersHorizontal,
  Sparkles,
  Upload,
} from 'lucide-react';
import { documentApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Slider } from '@/components/ui/slider';
import { EmptyState } from '@/components/primitives/EmptyState';
import { TimelineScrubber } from '@/components/graph/TimelineScrubber';
import { GraphFilters, searchApi, statsApi } from '@/lib/api';
import { useGraphFocus } from '@/lib/graph-store';
import { useInspector } from '@/lib/inspector-store';
import { cn } from '@/lib/utils';

const CitationGraph = dynamic(() => import('@/components/CitationGraph'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      Loading graph…
    </div>
  ),
});

interface Counts {
  visibleEdges: number;
  totalEdges: number;
  citationEdges: number;
  semanticEdges: number;
}

// Default chosen to reduce visual noise on a 200-node corpus — at 0.75
// the 147 semantic edges combined with citation edges produce a hairball.
// Users can lower interactively via the slider.
const DEFAULT_THRESHOLD = 0.85;
const FALLBACK_THRESHOLD = 0.7;

export default function GraphPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const querySeed = searchParams?.get('q') ?? '';
  const focusId = searchParams?.get('focus') ?? '';
  const expandedParam = searchParams?.get('expanded') ?? '';
  const expansionIds = useMemo(
    () => (expandedParam ? expandedParam.split(',').filter(Boolean) : []),
    [expandedParam],
  );
  const mode: 'corpus' | 'neighborhood' = focusId ? 'neighborhood' : 'corpus';
  const setFocus = useGraphFocus((s) => s.setFocus);
  const pulseGraph = useGraphFocus((s) => s.pulse);
  const addRecent = useGraphFocus((s) => s.addRecent);
  const showInspector = useInspector((s) => s.show);

  // Track B — focal status for the processing-state status bar.
  const [focalStatus, setFocalStatus] = useState<{
    status: string | null;
    citations: number;
    embedded: boolean;
  }>({ status: null, citations: 0, embedded: false });

  const [corpusEmpty, setCorpusEmpty] = useState<boolean | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [minConfidence, setMinConfidence] = useState(0.7);
  const [semanticThreshold, setSemanticThreshold] = useState(DEFAULT_THRESHOLD);
  const [court, setCourt] = useState('');
  const [yearMin, setYearMin] = useState('');
  const [yearMax, setYearMax] = useState('');
  const [filters, setFilters] = useState<GraphFilters>({ minConfidence: 0.7 });
  const [counts, setCounts] = useState<Counts>({
    visibleEdges: 0,
    totalEdges: 0,
    citationEdges: 0,
    semanticEdges: 0,
  });
  const [years, setYears] = useState<number[]>([]);

  // Stats — used to gate the empty state.
  useEffect(() => {
    let mounted = true;
    statsApi
      .getStats()
      .then((s) => {
        if (!mounted) return;
        setCorpusEmpty(s.total_documents === 0);
      })
      .catch((e) => {
        if (!mounted) return;
        setCorpusEmpty(false); // assume not empty so the canvas still renders
        setStatsError(e instanceof Error ? e.message : 'Stats unavailable');
      });
    return () => {
      mounted = false;
    };
  }, []);

  const apply = () => {
    setFilters({
      minConfidence,
      court: court || null,
      yearMin: yearMin ? Number(yearMin) : null,
      yearMax: yearMax ? Number(yearMax) : null,
    });
  };

  // Direct deep-link: ?focus=<id> pulses + opens the inspector + records
  // the case in localStorage recents so the entry-point can surface it.
  useEffect(() => {
    if (!focusId) return;
    pulseGraph(focusId);
    showInspector({ kind: 'document', id: focusId });
    // Fetch the case metadata to populate the recents entry. Best-effort:
    // if the API fails, we silently skip the recents update.
    documentApi
      .getDocument(focusId)
      .then((detail) => {
        const doc = detail.document;
        addRecent({
          id: doc.id,
          title: doc.title,
          court: doc.court ?? null,
          year: doc.year ?? null,
        });
      })
      .catch(() => {});
  }, [focusId, pulseGraph, showInspector, addRecent]);

  // Track B — poll /v1/documents/{id}/status while the focal is in
  // 'processing'. When it completes, the CitationGraph mode-effect
  // refetches the neighborhood and the new structure appears.
  const lastStatusRef = useRef<string | null>(null);
  useEffect(() => {
    if (mode !== 'neighborhood' || !focusId) return;
    if (focalStatus.status === 'completed' || focalStatus.status === 'failed') {
      return;
    }
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      try {
        const s = await documentApi.getDocumentStatus(focusId);
        if (cancelled) return;
        if (s.status !== lastStatusRef.current) {
          lastStatusRef.current = s.status;
        }
        setFocalStatus({
          status: s.status,
          citations: s.citations_count,
          embedded: s.status === 'completed',
        });
        if (s.status === 'completed' || s.status === 'failed') return;
        window.setTimeout(tick, 3000);
      } catch {
        // Network blip — try again.
        if (!cancelled) window.setTimeout(tick, 3000);
      }
    };
    tick();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, mode, focalStatus.status]);

  const onFocalStatus = useCallback((status: string | null, citations: number) => {
    setFocalStatus((prev) => ({
      ...prev,
      status,
      citations,
      embedded: status === 'completed',
    }));
  }, []);

  // Plain semantic-search seed: ?q=<query> without ?focus= — pan camera.
  useEffect(() => {
    if (!querySeed || focusId) return;
    let mounted = true;
    searchApi
      .search(querySeed, 10, 0.4)
      .then((r) => {
        if (!mounted) return;
        setFocus(r.hits.map((h) => h.doc_id));
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [querySeed, focusId, setFocus]);

  const hasSemanticEdges = counts.semanticEdges > 0;
  const totalSemanticAvailable = counts.totalEdges - counts.citationEdges;

  // Show empty state if stats has loaded and corpus is empty.
  if (corpusEmpty === true) {
    return <GraphEmptyState />;
  }

  // While stats is still loading, render the toolbar layout but with a
  // subtle skeleton — avoids a flash of the empty state.
  return (
    <div className="flex h-full flex-col">
      <Toolbar
        counts={counts}
        semanticThreshold={semanticThreshold}
        onSemanticThresholdChange={setSemanticThreshold}
        onLowerThreshold={() => setSemanticThreshold(FALLBACK_THRESHOLD)}
        showLowerThresholdHint={
          hasSemanticEdges === false &&
          totalSemanticAvailable > 0 &&
          semanticThreshold > FALLBACK_THRESHOLD
        }
        statsError={statsError}
        filtersSheet={
          <FiltersSheet
            minConfidence={minConfidence}
            setMinConfidence={setMinConfidence}
            court={court}
            setCourt={setCourt}
            yearMin={yearMin}
            setYearMin={setYearMin}
            yearMax={yearMax}
            setYearMax={setYearMax}
            onApply={apply}
          />
        }
      />
      <div className="relative min-h-0 flex-1">
        <CitationGraph
          filters={filters}
          semanticThreshold={semanticThreshold}
          onCounts={setCounts}
          onYears={setYears}
          focusId={focusId || null}
          expansionIds={expansionIds}
          onFocalStatus={onFocalStatus}
        />
        <ModeSwitcher mode={mode} router={router} />
        {mode === 'neighborhood' && (
          <FocalStatusBar status={focalStatus} focusId={focusId} />
        )}
        <TimelineScrubber years={years} />
        <Legend />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mode switcher — bottom-right pill toggling between focal + corpus views.
// ---------------------------------------------------------------------------

function ModeSwitcher({
  mode,
  router,
}: {
  mode: 'corpus' | 'neighborhood';
  router: ReturnType<typeof useRouter>;
}) {
  if (mode === 'neighborhood') {
    return (
      <button
        type="button"
        onClick={() => router.push('/graph')}
        className={cn(
          'pointer-events-auto absolute right-3 top-12 z-10',
          'inline-flex items-center gap-1 rounded-md border bg-background/85 px-2 py-1',
          'text-[11px] text-muted-foreground backdrop-blur-sm transition-colors duration-150',
          'hover:bg-background hover:text-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30',
        )}
      >
        Showing neighborhood
        <span aria-hidden className="text-muted-foreground/60">·</span>
        Switch to full corpus
        <ArrowRight className="h-3 w-3" aria-hidden />
      </button>
    );
  }
  return (
    <Link
      href="/"
      className={cn(
        'pointer-events-auto absolute right-3 top-12 z-10',
        'inline-flex items-center gap-1 rounded-md border bg-background/85 px-2 py-1',
        'text-[11px] text-muted-foreground backdrop-blur-sm transition-colors duration-150',
        'hover:bg-background hover:text-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30',
      )}
    >
      Showing full corpus
      <span aria-hidden className="text-muted-foreground/60">·</span>
      Focus on a case
      <ArrowRight className="h-3 w-3" aria-hidden />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Focal-status bar — Track B processing-state visibility.
// ---------------------------------------------------------------------------

function FocalStatusBar({
  status,
  focusId,
}: {
  status: { status: string | null; citations: number; embedded: boolean };
  focusId: string;
}) {
  // Done state — nothing to show.
  if (status.status === 'completed' && status.embedded) return null;
  // Failed state — show retry hint.
  if (status.status === 'failed') {
    return (
      <div
        className={cn(
          'pointer-events-auto absolute bottom-16 left-1/2 z-10 -translate-x-1/2',
          'flex items-center gap-2 rounded-md border border-destructive/40',
          'bg-destructive/5 px-3 py-1.5 text-[11px] text-destructive shadow-sm backdrop-blur-sm',
        )}
      >
        Extraction failed for this case.
        <button
          type="button"
          onClick={() => documentApi.processDocument(focusId).catch(() => {})}
          className="underline underline-offset-2 hover:no-underline"
        >
          Retry
        </button>
      </div>
    );
  }

  let message = 'Processing this case…';
  if (status.status === 'processing' || status.citations === 0) {
    message = 'Extracting citations…';
  } else if (!status.embedded) {
    message = 'Building semantic connections…';
  } else {
    return null;
  }

  return (
    <div
      className={cn(
        'pointer-events-none absolute bottom-16 left-1/2 z-10 -translate-x-1/2',
        'flex items-center gap-2 rounded-md border bg-background/85 px-3 py-1.5',
        'text-[11px] text-muted-foreground shadow-sm backdrop-blur-sm',
        'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:duration-150',
      )}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-3 w-3 animate-spin motion-reduce:hidden" aria-hidden />
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state for zero-document corpus
// ---------------------------------------------------------------------------

function GraphEmptyState() {
  return (
    <div className="flex h-full items-center justify-center">
      <EmptyState
        icon={Network}
        title="Your corpus is empty"
        description="Seed SCOTUS opinions or upload your own PDFs to start exploring citation relationships and semantic clusters."
        actions={
          <>
            <Link href="/upload">
              <Button variant="accent" size="sm">
                <Upload className="h-3.5 w-3.5" /> Upload a PDF
              </Button>
            </Link>
            <a
              href="https://github.com/anthropics/legal-nlp-citation-graph#seed-with-50-scotus-opinions"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Button variant="outline" size="sm">
                <Sparkles className="h-3.5 w-3.5" /> Seed SCOTUS
              </Button>
            </a>
          </>
        }
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toolbar — counts + similarity slider + filters trigger
// ---------------------------------------------------------------------------

interface ToolbarProps {
  counts: Counts;
  semanticThreshold: number;
  onSemanticThresholdChange: (v: number) => void;
  onLowerThreshold: () => void;
  showLowerThresholdHint: boolean;
  statsError: string | null;
  filtersSheet: React.ReactNode;
}

function Toolbar({
  counts,
  semanticThreshold,
  onSemanticThresholdChange,
  onLowerThreshold,
  showLowerThresholdHint,
  statsError,
  filtersSheet,
}: ToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-background px-4 py-2">
      <div className="flex items-center gap-3">
        <CountsLabel counts={counts} />
        {statsError && (
          <span className="rounded-sm bg-destructive/10 px-1.5 py-0.5 text-[10px] text-destructive">
            {statsError}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ThresholdControl
          value={semanticThreshold}
          onChange={onSemanticThresholdChange}
          showLowerHint={showLowerThresholdHint}
          onLower={onLowerThreshold}
        />
        {filtersSheet}
      </div>
    </div>
  );
}

function CountsLabel({ counts }: { counts: Counts }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="flex items-center gap-1.5">
        {/* Citation icon: tapered triangle, source-wide → target-thin.
            Mirrors what the canvas actually renders so the legend
            doubles as a visual key. */}
        <svg
          width={14}
          height={6}
          viewBox="0 0 14 6"
          aria-hidden
          className="shrink-0"
        >
          <polygon points="0,1 0,5 14,3" className="fill-blue-500" />
        </svg>
        <span className="font-mono tabular-nums text-foreground">
          {counts.citationEdges}
        </span>
        <span>citation</span>
      </span>
      <span aria-hidden className="text-muted-foreground/40">·</span>
      <span className="flex items-center gap-1.5">
        {/* Semantic icon: a soft emerald arc, matching the curved edges
            painted by @sigma/edge-curve. The arc reads as "related but
            not directional" without needing a label. */}
        <svg
          width={14}
          height={6}
          viewBox="0 0 14 6"
          aria-hidden
          className="shrink-0"
        >
          <path
            d="M0 5 Q 7 -2 14 5"
            fill="none"
            stroke="#10b981"
            strokeWidth={1.4}
            strokeLinecap="round"
          />
        </svg>
        <span className="font-mono tabular-nums text-foreground">
          {counts.semanticEdges}
        </span>
        <span>similar</span>
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Threshold control — section label + slider + numeric badge + anchor labels
// ---------------------------------------------------------------------------

interface ThresholdControlProps {
  value: number;
  onChange: (v: number) => void;
  showLowerHint: boolean;
  onLower: () => void;
}

function ThresholdControl({
  value,
  onChange,
  showLowerHint,
  onLower,
}: ThresholdControlProps) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex items-center gap-2">
        <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
          Similarity threshold
        </Label>
        <span className="rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[11px] tabular-nums">
          {value.toFixed(2)}
        </span>
      </div>
      <div className="hidden flex-col items-stretch gap-1 sm:flex">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/70">
            Fewer
          </span>
          <div className="w-40">
            <Slider
              min={0.5}
              max={0.95}
              step={0.01}
              value={[value]}
              onValueChange={([v]) => onChange(v)}
              aria-label="Semantic similarity threshold"
            />
          </div>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground/70">
            More
          </span>
        </div>
        {showLowerHint && (
          <button
            type="button"
            onClick={onLower}
            className={cn(
              'self-end text-[10px] text-amber-700 underline-offset-2 hover:underline',
              'dark:text-amber-400',
            )}
          >
            No similar cases at this threshold — lower to {FALLBACK_THRESHOLD.toFixed(2)}?
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filters sheet
// ---------------------------------------------------------------------------

interface FiltersSheetProps {
  minConfidence: number;
  setMinConfidence: (v: number) => void;
  court: string;
  setCourt: (v: string) => void;
  yearMin: string;
  setYearMin: (v: string) => void;
  yearMax: string;
  setYearMax: (v: string) => void;
  onApply: () => void;
}

function FiltersSheet(props: FiltersSheetProps) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
        </Button>
      </SheetTrigger>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Graph filters</SheetTitle>
          <SheetDescription>
            Constrain the network by confidence, court, and year.
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-5 pt-4">
          <div className="flex flex-col gap-2">
            <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Min citation confidence
            </Label>
            <Slider
              min={0}
              max={1}
              step={0.05}
              value={[props.minConfidence]}
              onValueChange={([v]) => props.setMinConfidence(v)}
            />
            <div className="text-[11px] text-muted-foreground">
              Showing edges with confidence ≥{' '}
              <span className="font-mono tabular-nums text-foreground">
                {props.minConfidence.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Court (exact match)
            </Label>
            <Input
              value={props.court}
              onChange={(e) => props.setCourt(e.target.value)}
              placeholder="e.g. U.S. Supreme Court"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-2">
              <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Year ≥
              </Label>
              <Input
                value={props.yearMin}
                onChange={(e) => props.setYearMin(e.target.value)}
                placeholder="1900"
                type="number"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Year ≤
              </Label>
              <Input
                value={props.yearMax}
                onChange={(e) => props.setYearMax(e.target.value)}
                placeholder="2026"
                type="number"
              />
            </div>
          </div>
          <Button onClick={props.onApply} variant="accent" size="sm">
            Apply filters
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Persistent legend overlay (bottom-left of canvas)
// ---------------------------------------------------------------------------

function Legend() {
  return (
    <div
      className={cn(
        'pointer-events-none absolute bottom-3 left-3 z-10',
        'rounded-md border border-border/60 bg-background/80 px-3 py-2',
        'backdrop-blur-sm',
        'flex flex-col gap-1.5 text-[11px]',
      )}
      aria-label="Graph edge legend"
    >
      <div className="flex items-center gap-2">
        {/* Tapered triangle — same shape the WebGL tapered edge program
            paints. Wide at the source end, narrowing to a point at
            the target so directionality reads from shape alone. */}
        <svg width={24} height={6} viewBox="0 0 24 6" aria-hidden>
          <polygon points="0,0.5 0,5.5 24,3" className="fill-blue-500" />
        </svg>
        <span className="text-muted-foreground">Citation</span>
      </div>
      <div className="flex items-center gap-2">
        {/* Curved emerald arc — matches @sigma/edge-curve. The curve
            depth in the canvas is similarity-dependent (tighter scores
            curve less); legend uses a mid-range arc as a representative. */}
        <svg width={24} height={6} viewBox="0 0 24 6" aria-hidden>
          <path
            d="M0 5 Q 12 -2 24 5"
            fill="none"
            stroke="#10b981"
            strokeWidth={1.4}
            strokeLinecap="round"
          />
        </svg>
        <span className="text-muted-foreground">Semantic similarity</span>
      </div>
    </div>
  );
}
