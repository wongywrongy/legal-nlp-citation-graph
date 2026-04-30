'use client';

/**
 * Tiny inline SVG showing a single document's direct citation neighbourhood.
 * Renders as a 36×24 thumbnail next to the row title — at-a-glance "is this
 * case isolated, a leaf, or a hub?". Not interactive; purely decorative.
 *
 * Layout:
 *   - Anchor dot at centre = the document itself
 *   - Up to 6 neighbour dots arranged on a small ellipse around it
 *   - Hairline lines from anchor to each visible neighbour
 *   - If the doc has >6 neighbours, the 6 visible ones still appear; the
 *     extra count surfaces via title attribute (hover tooltip).
 *
 * Tone:
 *   - Anchor: amber (the case in focus)
 *   - In-neighbours (cited by this doc): teal
 *   - Out-neighbours (this doc cites): indigo
 */
import { memo, useMemo } from 'react';

interface CitationSparklineProps {
  /** Outgoing — cases this doc cites. */
  outgoing: number;
  /** Incoming — cases that cite this doc. */
  incoming: number;
}

function CitationSparklineImpl({ outgoing, incoming }: CitationSparklineProps) {
  const total = outgoing + incoming;
  const visible = Math.min(6, total);
  const visOut = Math.min(outgoing, Math.ceil(visible * (outgoing / Math.max(1, total))));
  const visIn = Math.min(incoming, visible - visOut);

  const positions = useMemo(() => {
    const n = visOut + visIn;
    if (n === 0) return [] as Array<{ x: number; y: number; tone: 'in' | 'out' }>;
    const cx = 18;
    const cy = 12;
    const rx = 14;
    const ry = 8;
    return Array.from({ length: n }, (_, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      return {
        x: cx + Math.cos(angle) * rx,
        y: cy + Math.sin(angle) * ry,
        tone: i < visOut ? ('out' as const) : ('in' as const),
      };
    });
  }, [visOut, visIn]);

  if (total === 0) {
    // Isolated node: just the anchor, no neighbours
    return (
      <svg
        width={36}
        height={24}
        viewBox="0 0 36 24"
        className="shrink-0 opacity-60"
        aria-hidden
      >
        <circle cx={18} cy={12} r={2} className="fill-muted-foreground" />
      </svg>
    );
  }

  return (
    <svg
      width={36}
      height={24}
      viewBox="0 0 36 24"
      className="shrink-0"
      aria-label={`Cites ${outgoing}, cited by ${incoming}`}
    >
      {/* hairlines from anchor to each neighbour */}
      {positions.map((p, i) => (
        <line
          key={`l${i}`}
          x1={18}
          y1={12}
          x2={p.x}
          y2={p.y}
          className={
            p.tone === 'out'
              ? 'stroke-indigo-400/40 dark:stroke-indigo-500/45'
              : 'stroke-teal-500/40 dark:stroke-teal-400/45'
          }
          strokeWidth={0.5}
        />
      ))}
      {positions.map((p, i) => (
        <circle
          key={`c${i}`}
          cx={p.x}
          cy={p.y}
          r={1.4}
          className={
            p.tone === 'out'
              ? 'fill-indigo-500 dark:fill-indigo-400'
              : 'fill-teal-500 dark:fill-teal-400'
          }
        />
      ))}
      {/* anchor dot last so it sits on top */}
      <circle
        cx={18}
        cy={12}
        r={2.5}
        className="fill-amber-500 dark:fill-amber-400"
      />
    </svg>
  );
}

// Memo: degree numbers change rarely (only on graph re-fetch), so the
// 100 row sparklines on /documents shouldn't re-render on every sort or
// search-input keystroke.
export const CitationSparkline = memo(CitationSparklineImpl);
