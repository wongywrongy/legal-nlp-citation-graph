import { cn } from '@/lib/utils';
import { classifyCourt, courtLabel, type CourtType } from '@/lib/court';
import { formatCourtShort } from '@/lib/format';

interface CourtPillProps {
  court?: string | null;
  className?: string;
  showLabel?: boolean;
}

const ringClasses: Record<CourtType, string> = {
  scotus: 'border-court-scotus',
  federal: 'border-court-federal',
  state: 'border-court-state',
  other: 'border-court-other',
};

const textClasses: Record<CourtType, string> = {
  scotus: 'text-court-scotus',
  federal: 'text-court-federal',
  state: 'text-court-state',
  other: 'text-court-other',
};

export function CourtPill({ court, className, showLabel = true }: CourtPillProps) {
  const type = classifyCourt(court);
  // Use the shorthand ("SCOTUS", "9th Circuit") so the pill stays a single
  // line in dense table rows. Full name lives on the `title` attribute.
  const display = showLabel
    ? court
      ? formatCourtShort(court)
      : courtLabel[type]
    : courtLabel[type];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border bg-transparent px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
        ringClasses[type],
        textClasses[type],
        className,
      )}
      title={court || 'Unknown court'}
    >
      <span className="h-1 w-1 rounded-full bg-current" aria-hidden />
      {display}
    </span>
  );
}
