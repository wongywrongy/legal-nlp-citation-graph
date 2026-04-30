import { cn } from '@/lib/utils';
import { tierFor, tierLabel, type ConfidenceTier } from '@/lib/confidence';

interface ConfidenceBadgeProps {
  value: number | null | undefined;
  resolved?: boolean;
  showLabel?: boolean;
  className?: string;
}

/**
 * A11y rule 9: confidence is communicated by both shape AND color.
 * High = filled dot, Medium = half-filled, Low = hollow, Unresolved = dashed ring.
 */
export function ConfidenceBadge({ value, resolved = true, showLabel = true, className }: ConfidenceBadgeProps) {
  const tier: ConfidenceTier = tierFor(value, resolved);

  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', className)}>
      <ConfidenceGlyph tier={tier} />
      {showLabel && (
        <span
          className={cn(
            tier === 'high' && 'text-confidence-high',
            tier === 'medium' && 'text-confidence-medium',
            tier === 'low' && 'text-confidence-low',
            tier === 'unresolved' && 'text-confidence-unresolved',
          )}
        >
          {tierLabel[tier]}
          {value != null && resolved ? <span className="ml-1 font-mono opacity-70">{(value * 100).toFixed(0)}%</span> : null}
        </span>
      )}
    </span>
  );
}

function ConfidenceGlyph({ tier }: { tier: ConfidenceTier }) {
  switch (tier) {
    case 'high':
      return <span className="block h-2 w-2 rounded-full bg-confidence-high" aria-hidden />;
    case 'medium':
      return (
        <span className="relative block h-2 w-2 rounded-full border border-confidence-medium" aria-hidden>
          <span className="absolute inset-y-0 left-0 w-1/2 rounded-l-full bg-confidence-medium" />
        </span>
      );
    case 'low':
      return <span className="block h-2 w-2 rounded-full border border-confidence-low" aria-hidden />;
    case 'unresolved':
      return (
        <span
          className="block h-2 w-2 rounded-full border border-dashed border-confidence-unresolved"
          aria-hidden
        />
      );
  }
}
