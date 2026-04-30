import { cn } from '@/lib/utils';

interface ConfidenceBreakdownProps {
  breakdown: Record<string, number> | null | undefined;
  total?: number | null;
  className?: string;
}

const componentLabels: Record<string, string> = {
  eyecite_base: 'Eyecite baseline',
  match_boost: 'Match boost',
  llm_resolved: 'LLM tie-break',
  year_boost: 'Year match',
  court_boost: 'Court match',
};

/**
 * Shows the additive components of a Citation.confidence value so a researcher
 * can sanity-check why a citation scored what it scored. Source: the
 * `confidence_breakdown` JSON column populated by DocumentProcessor.
 */
export function ConfidenceBreakdown({ breakdown, total, className }: ConfidenceBreakdownProps) {
  if (!breakdown || Object.keys(breakdown).length === 0) {
    return (
      <div className={cn('text-xs text-muted-foreground', className)}>
        No breakdown recorded.
      </div>
    );
  }
  const entries = Object.entries(breakdown);
  return (
    <table className={cn('w-full text-[12px]', className)}>
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key} className="border-b border-border/60 last:border-0">
            <td className="py-1.5 pr-2 text-muted-foreground">{componentLabels[key] ?? key}</td>
            <td className="py-1.5 text-right font-mono tabular-nums">+{value.toFixed(2)}</td>
          </tr>
        ))}
        {total != null && (
          <tr>
            <td className="py-1.5 pr-2 font-medium">Total</td>
            <td className="py-1.5 text-right font-mono font-semibold tabular-nums">{total.toFixed(2)}</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
