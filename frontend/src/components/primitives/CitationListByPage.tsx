'use client';

import { useMemo } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ConfidenceBadge } from '@/components/primitives/ConfidenceBadge';
import { CitationItem } from '@/lib/api';
import { cn } from '@/lib/utils';

interface CitationListByPageProps {
  citations: CitationItem[];
  activeCitationId?: string | null;
  onCitationClick?: (citation: CitationItem) => void;
}

export function CitationListByPage({ citations, activeCitationId, onCitationClick }: CitationListByPageProps) {
  const groups = useMemo(() => {
    const map = new Map<number, CitationItem[]>();
    for (const c of citations) {
      const page = c.page_number ?? 0;
      if (!map.has(page)) map.set(page, []);
      map.get(page)!.push(c);
    }
    return Array.from(map.entries()).sort((a, b) => a[0] - b[0]);
  }, [citations]);

  if (citations.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-4 text-center text-xs text-muted-foreground">
        No citations extracted from this document.
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col">
        {groups.map(([page, items]) => (
          <section key={page}>
            <header className="sticky top-0 z-10 flex items-baseline justify-between border-b border-border bg-background/95 px-3 py-1.5 backdrop-blur">
              <span className="text-2xs font-medium uppercase tracking-wide text-muted-foreground">
                Page {page || '—'}
              </span>
              <span className="font-mono text-2xs text-muted-foreground">{items.length}</span>
            </header>
            <ul className="divide-y divide-border">
              {items.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => onCitationClick?.(c)}
                    className={cn(
                      'flex w-full flex-col items-start gap-1 px-3 py-2 text-left transition-colors hover:bg-muted/40',
                      activeCitationId === c.id && 'bg-accent/10',
                    )}
                  >
                    <span className="line-clamp-2 font-mono text-[12px] leading-snug text-foreground">{c.raw_text}</span>
                    <span className="flex items-center gap-2">
                      <ConfidenceBadge value={c.confidence} resolved={!!c.to_doc_id} />
                      {!c.to_doc_id && (
                        <span className="text-2xs uppercase tracking-wide text-muted-foreground">unresolved</span>
                      )}
                      {c.citation_type !== 'full' && (
                        <span className="font-mono text-2xs text-muted-foreground">{c.citation_type}</span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </ScrollArea>
  );
}
