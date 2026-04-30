'use client';

/**
 * Horizontal timeline scrubber pinned to the bottom of the graph canvas.
 *
 * Above the slider: a decade histogram showing case density across the
 * corpus. Bars use the same muted palette as the rest of the graph chrome
 * so they annotate without competing.
 *
 * Slider: two-thumb range built on shadcn's Slider (Radix). Dragging
 * either thumb writes to graph-store.yearRange; CitationGraph's reducer
 * dims any node outside the range to slate-300.
 *
 * The component takes a `years: number[]` array — provided by
 * CitationGraph's onYears callback so we don't double-fetch /v1/graph.
 * If years is empty, the component renders nothing.
 */
import { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import { Slider } from '@/components/ui/slider';
import { useGraphFocus } from '@/lib/graph-store';
import { cn } from '@/lib/utils';

interface TimelineScrubberProps {
  years: number[];
}

export function TimelineScrubber({ years }: TimelineScrubberProps) {
  const yearRange = useGraphFocus((s) => s.yearRange);
  const setYearRange = useGraphFocus((s) => s.setYearRange);

  // Per-year vs per-decade binning is chosen by total span:
  //   - span < 20 years: each bar is one year. The histogram surfaces
  //     activity spikes that decade buckets would smear out.
  //   - span ≥ 20 years: bars are decade buckets. Per-year bars become
  //     too thin to read once you span more than two decades.
  // `binSize` is exposed downstream so the slider step + label can scale.
  const { minYear, maxYear, bins, binSize } = useMemo(() => {
    type Bin = { start: number; count: number };
    if (years.length === 0) {
      return { minYear: 1900, maxYear: 2025, bins: [] as Bin[], binSize: 10 };
    }
    const min = Math.min(...years);
    const max = Math.max(...years);
    const span = max - min;
    const usePerYear = span < 20;

    if (usePerYear) {
      const start = min;
      const end = max + 1;
      const out: Bin[] = [];
      for (let y = start; y < end; y += 1) {
        out.push({ start: y, count: 0 });
      }
      for (const y of years) {
        const idx = y - start;
        if (idx >= 0 && idx < out.length) out[idx].count += 1;
      }
      return { minYear: start, maxYear: end, bins: out, binSize: 1 };
    }

    const startDecade = Math.floor(min / 10) * 10;
    const endDecade = Math.ceil(max / 10) * 10;
    const out: Bin[] = [];
    for (let d = startDecade; d < endDecade; d += 10) {
      out.push({ start: d, count: 0 });
    }
    for (const y of years) {
      const idx = Math.floor((y - startDecade) / 10);
      if (idx >= 0 && idx < out.length) out[idx].count += 1;
    }
    return { minYear: startDecade, maxYear: endDecade, bins: out, binSize: 10 };
  }, [years]);

  const [localRange, setLocalRange] = useState<[number, number]>([minYear, maxYear]);

  // Reset local range whenever the corpus changes (years array shifts).
  useEffect(() => {
    setLocalRange([minYear, maxYear]);
  }, [minYear, maxYear]);

  // External clears (e.g. the close button below) should also reset local.
  useEffect(() => {
    if (yearRange === null) setLocalRange([minYear, maxYear]);
  }, [yearRange, minYear, maxYear]);

  if (years.length === 0) return null;
  // Hide the scrubber entirely when there's nothing to scrub — corpus
  // spans a single year (or fewer). Saves the bottom strip of canvas.
  if (minYear >= maxYear) return null;

  const maxCount = Math.max(1, ...bins.map((b) => b.count));
  const isFiltering = yearRange !== null;
  // Hide the histogram entirely when there's only one bar — that's
  // information-free clutter. Slider still renders so the user can
  // narrow within the year span if they want.
  const showHistogram = bins.length >= 2;
  // Decade labels every other bar to avoid crowding. Per-year mode only
  // labels every 5th to keep the row readable across 10–20 entries.
  const labelStride = binSize === 1 ? 5 : 2;

  return (
    <div
      className={cn(
        'pointer-events-auto absolute bottom-3 left-1/2 z-10 -translate-x-1/2',
        'w-[min(640px,calc(100%-2rem))]',
        'rounded-lg border border-border bg-background/85 px-4 pb-3 pt-2',
        'shadow-sm backdrop-blur-sm',
        'motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-300',
      )}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Timeline
          {/*
            Show the live range any time it's narrower than the corpus
            span — even before commit. Updates in real time as the user
            drags so they can see what they're selecting without waiting
            for the slider to settle.
          */}
          {(isFiltering ||
            localRange[0] !== minYear ||
            localRange[1] !== maxYear) && (
            <span className="ml-1.5 font-mono normal-case tracking-normal text-foreground">
              {localRange[0]} – {localRange[1]}
            </span>
          )}
        </span>
        {isFiltering && (
          <button
            type="button"
            onClick={() => setYearRange(null)}
            className={cn(
              'inline-flex items-center gap-0.5 text-[10px] text-muted-foreground',
              'transition-colors duration-150 hover:text-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:rounded',
            )}
            aria-label="Show all years"
          >
            <X className="h-3 w-3" /> Show all years
          </button>
        )}
      </div>

      {showHistogram && (
        <>
          {/* Histogram (per-year bars below 20-year span, per-decade above) */}
          <div className="mb-1 flex h-6 items-end gap-0.5" aria-hidden>
            {bins.map((b) => {
              const binEnd = b.start + binSize - 1;
              const inRange =
                binEnd >= localRange[0] && b.start <= localRange[1];
              const tooltip =
                binSize === 1
                  ? `${b.start} — ${b.count} cases`
                  : `${b.start}s — ${b.count} cases`;
              return (
                <span
                  key={b.start}
                  className={cn(
                    'block flex-1 rounded-sm transition-colors duration-150',
                    inRange ? 'bg-slate-400 dark:bg-slate-500' : 'bg-muted',
                  )}
                  style={{
                    height: `${Math.max(8, (b.count / maxCount) * 100)}%`,
                  }}
                  title={tooltip}
                />
              );
            })}
          </div>

          {/* X-axis labels: every Nth bin to avoid crowding. */}
          <div className="mb-2 flex gap-0.5 text-[9px] tabular-nums text-muted-foreground/70">
            {bins.map((b, i) => (
              <span key={b.start} className="flex-1 text-center">
                {i % labelStride === 0 ? b.start : ''}
              </span>
            ))}
          </div>
        </>
      )}

      {/* Two-thumb range slider */}
      <Slider
        min={minYear}
        max={maxYear}
        step={1}
        value={localRange}
        onValueChange={(values) => {
          if (values.length !== 2) return;
          const next: [number, number] = [values[0], values[1]];
          setLocalRange(next);
          if (next[0] === minYear && next[1] === maxYear) {
            setYearRange(null);
          } else {
            setYearRange(next);
          }
        }}
        aria-label="Filter cases by year"
      />
    </div>
  );
}
