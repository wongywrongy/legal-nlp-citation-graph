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
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import {
  Network,
  SlidersHorizontal,
  Sparkles,
  Upload,
} from 'lucide-react';
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
  const searchParams = useSearchParams();
  const querySeed = searchParams?.get('q') ?? '';
  const focusId = searchParams?.get('focus') ?? '';
  const setFocus = useGraphFocus((s) => s.setFocus);
  const pulseGraph = useGraphFocus((s) => s.pulse);
  const showInspector = useInspector((s) => s.show);

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

  // Direct deep-link: ?focus=<id> pulses + opens the inspector.
  useEffect(() => {
    if (!focusId) return;
    pulseGraph(focusId);
    showInspector({ kind: 'document', id: focusId });
  }, [focusId, pulseGraph, showInspector]);

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
        />
        <TimelineScrubber years={years} />
        <Legend />
      </div>
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
        <span className="inline-block h-0.5 w-3 rounded-full bg-blue-500" aria-hidden />
        <span className="font-mono tabular-nums text-foreground">
          {counts.citationEdges}
        </span>
        <span>citation</span>
      </span>
      <span aria-hidden className="text-muted-foreground/40">·</span>
      <span className="flex items-center gap-1.5">
        <span
          className="inline-block h-0.5 w-3 rounded-full"
          style={{
            backgroundImage:
              'repeating-linear-gradient(to right, #10b981, #10b981 3px, transparent 3px, transparent 6px)',
          }}
          aria-hidden
        />
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
        <span className="inline-block h-0.5 w-6 rounded-full bg-blue-500" aria-hidden />
        <span className="text-muted-foreground">Citation</span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-0.5 w-6"
          style={{
            backgroundImage:
              'repeating-linear-gradient(to right, #10b981, #10b981 3px, transparent 3px, transparent 6px)',
          }}
          aria-hidden
        />
        <span className="text-muted-foreground">Semantic similarity</span>
      </div>
    </div>
  );
}
