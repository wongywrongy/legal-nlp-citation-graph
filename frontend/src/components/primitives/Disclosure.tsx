'use client';

/**
 * Lightweight disclosure component — a single expandable panel with a
 * chevron that rotates on open. Built on plain React state to avoid pulling
 * in @radix-ui/react-accordion just for one section.
 *
 * Default style fits the inspector's dense aesthetic: a left-aligned label
 * row with a small chevron, animated open/close on the body. Uses our
 * standard 11px uppercase tracking-wide muted label convention so it reads
 * as a peer of the other inspector sections.
 */
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DisclosureProps {
  label: string;
  defaultOpen?: boolean;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}

export function Disclosure({
  label,
  defaultOpen = false,
  hint,
  children,
  className,
}: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn('flex flex-col', className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          'flex items-center justify-between gap-2 rounded-md px-1 py-1 text-left',
          'text-[11px] uppercase tracking-wide text-muted-foreground',
          'transition-colors hover:text-foreground focus-visible:outline-none',
          'focus-visible:ring-2 focus-visible:ring-ring/50',
        )}
      >
        <span className="flex items-center gap-2">
          <span>{label}</span>
          {hint && (
            <span className="text-muted-foreground/70 normal-case tracking-normal">
              {hint}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            'h-3 w-3 shrink-0 transition-transform duration-200',
            open && 'rotate-180',
          )}
          aria-hidden
        />
      </button>
      <div
        className={cn(
          'grid overflow-hidden transition-all duration-200',
          open ? 'mt-2 grid-rows-[1fr]' : 'grid-rows-[0fr]',
        )}
      >
        <div className="min-h-0 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
