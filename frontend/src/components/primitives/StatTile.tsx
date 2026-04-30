import { cn } from '@/lib/utils';

interface StatTileProps {
  label: string;
  value: string | number;
  hint?: string;
  /** Optional small accent applied to the value — e.g. for the "active"
   *  stat that the user is most likely to click into. */
  tone?: 'default' | 'accent';
  className?: string;
}

/**
 * Compact stat tile used on the dashboard. Tighter than the previous
 * version: smaller label, smaller value, less empty space, and a subtle
 * top-border accent on the active variant so the eye has a hierarchy
 * even when all four tiles share a row.
 */
export function StatTile({
  label,
  value,
  hint,
  tone = 'default',
  className,
}: StatTileProps) {
  return (
    <div
      className={cn(
        'group relative flex flex-col gap-1 rounded-md border border-border bg-card px-4 py-3',
        'transition-colors duration-150 hover:border-border/80',
        tone === 'accent' &&
          'before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-accent/60',
        className,
      )}
    >
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          'font-mono text-xl font-semibold tabular-nums leading-none',
          tone === 'accent' ? 'text-accent' : 'text-foreground',
        )}
      >
        {value}
      </div>
      {hint && <div className="text-[11px] leading-tight text-muted-foreground">{hint}</div>}
    </div>
  );
}
