'use client';

/**
 * Reusable empty-state surface — icon + heading + 1-2 sentence explanation
 * + optional primary/secondary CTAs. Intended as a centered card on a page
 * that would otherwise show a blank canvas, table, or list.
 *
 * Design intent: an empty state is a teaching surface. The icon orients the
 * user, the heading names the absence, the description explains the next
 * step, and the CTA makes the next step trivial. We never ship a bare
 * "No data" message — every empty state has an action.
 */
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'mx-auto flex w-full max-w-md flex-col items-center px-6 py-12 text-center',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border bg-muted/40">
        <Icon className="h-5 w-5 text-muted-foreground" aria-hidden />
      </div>
      <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
      {description && (
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      )}
      {actions && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {actions}
        </div>
      )}
    </div>
  );
}
