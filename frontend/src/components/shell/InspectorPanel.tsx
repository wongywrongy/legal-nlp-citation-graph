'use client';

/**
 * Inspector panel — the user's primary reading surface after they land on a
 * case. Treated as a research-tool sidebar (Linear / Figma vibe), not a
 * data table. Layout invariants:
 *
 *   • Header bar (h-12)        — kind label + close
 *   • Title block              — case name dominant, court/year/docket muted
 *   • Summary section          — 3-4 sentence opinion snippet
 *   • Cites section            — outbound citations, clickable rows pulse the graph
 *   • Cited by section         — reverse citations, same row pattern
 *   • Similar cases section    — top-5 with a CSS bar showing similarity
 *   • Citation details         — collapsed Disclosure for confidence breakdown
 *   • Footer (sticky)          — "Center graph here" CTA
 *
 * Visual hierarchy:
 *   - Section labels: text-[11px] uppercase tracking-wide muted
 *   - Body content: text-sm
 *   - Case names: text-sm font-medium
 *   - Metadata: text-xs muted
 *   - gap-6 between sections, gap-2 within
 *
 * Empty states never collapse a section — they show a single muted "none"
 * line so the panel doesn't shift between cases.
 */
import { useEffect, useMemo, useState } from 'react';
import { BookOpen, Crosshair, ExternalLink, Loader2, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Disclosure } from '@/components/primitives/Disclosure';
import { ConfidenceBadge } from '@/components/primitives/ConfidenceBadge';
import { ConfidenceBreakdown } from '@/components/primitives/ConfidenceBreakdown';
import { CitationText } from '@/components/primitives/CitationText';
import { CourtPill } from '@/components/primitives/CourtPill';
import { useInspector } from '@/lib/inspector-store';
import { useGraphFocus } from '@/lib/graph-store';
import {
  CitationItem,
  CitationOutgoing,
  DocumentDetail,
  DocumentSummary,
  RelatedCase,
  SimilarDocument,
  documentApi,
  searchApi,
} from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCaseTitle } from '@/lib/format';

const CITES_INITIAL_LIMIT = 8;
const CITES_PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

export function InspectorPanel() {
  const { open, target, hide } = useInspector();

  return (
    <aside className="hidden w-[380px] shrink-0 flex-col border-l border-border bg-background xl:flex">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-border px-4">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {target ? labelForKind(target.kind) : 'Inspector'}
        </span>
        {open && target && (
          <Button
            variant="ghost"
            size="icon"
            onClick={hide}
            aria-label="Close inspector"
            className="h-7 w-7 transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </header>

      {!open || !target ? (
        <EmptyInspector />
      ) : (
        <ScrollArea className="flex-1">
          <div className="px-5 py-5">
            {target.kind === 'document' && <DocumentInspector id={target.id} />}
            {target.kind === 'citation' && (
              <CitationInspector id={target.id} documentId={target.documentId} />
            )}
            {target.kind === 'similarity' && (
              <SimilarityInspector
                sourceId={target.sourceId}
                targetId={target.targetId}
                score={target.score}
              />
            )}
            {target.kind === 'edge' && <EdgeInspector id={target.id} />}
          </div>
        </ScrollArea>
      )}
    </aside>
  );
}

function labelForKind(kind: string): string {
  switch (kind) {
    case 'document':
      return 'Case';
    case 'citation':
      return 'Citation';
    case 'similarity':
      return 'Similarity';
    case 'edge':
      return 'Edge';
    default:
      return 'Inspector';
  }
}

function EmptyInspector() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
        <Crosshair className="h-4 w-4 text-muted-foreground" aria-hidden />
      </div>
      <p className="mt-3 text-sm font-medium text-foreground">
        Select a case on the graph
      </p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        Click any node to inspect its citations, similar cases, and confidence
        breakdown.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Document inspector — the main case-reading view
// ---------------------------------------------------------------------------

function DocumentInspector({ id }: { id: string }) {
  const [data, setData] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pulseGraph = useGraphFocus((s) => s.pulse);
  const setConstellation = useGraphFocus((s) => s.setConstellation);
  const constellationFocus = useGraphFocus((s) => s.constellationFocus);

  useEffect(() => {
    let mounted = true;
    setData(null);
    setError(null);
    documentApi
      .getDocument(id)
      .then((d) => mounted && setData(d))
      .catch(
        (e) =>
          mounted && setError(e instanceof Error ? e.message : 'Failed to load case'),
      );
    return () => {
      mounted = false;
    };
  }, [id]);

  if (error) return <ErrorBlock>{error}</ErrorBlock>;
  if (!data) return <DocumentSkeleton />;

  const { document: doc } = data;
  const inConstellation = constellationFocus === id;

  return (
    // Each child uses motion-safe:animate-in + slide-in with an
    // animation-delay so the panel reveals top-to-bottom like a brief
    // unfolding. Pinned via inline style because Tailwind doesn't have
    // a delay-X arbitrary value plugin.
    <div className="flex flex-col gap-6">
      <Reveal delay={0}>
        <DocumentHeader doc={doc} />
      </Reveal>
      <Reveal delay={40}>
        <SummarySection documentId={id} />
      </Reveal>
      <Reveal delay={80}>
        <CitesSection documentId={id} />
      </Reveal>
      <Reveal delay={120}>
        <CitedBySection documentId={id} />
      </Reveal>
      <Reveal delay={160}>
        <SimilarSection documentId={id} />
      </Reveal>
      <Reveal delay={200}>
        <CitationDetailsDisclosure citations={data.citations} />
      </Reveal>
      <Reveal delay={240}>
        <div className="flex flex-col gap-2">
          <FullTextSheet documentId={id} title={formatCaseTitle(doc.title)} />
          <FooterAction
            label={
              inConstellation
                ? 'Exit constellation view'
                : 'Constellation view'
            }
            icon={<Sparkles className="h-3.5 w-3.5" />}
            onClick={() =>
              setConstellation(inConstellation ? null : id)
            }
            tone={inConstellation ? 'accent' : 'default'}
          />
          <FooterAction
            label="Center graph on this case"
            icon={<Crosshair className="h-3.5 w-3.5" />}
            onClick={() => pulseGraph(id)}
          />
        </div>
      </Reveal>
    </div>
  );
}

function Reveal({
  delay,
  children,
}: {
  delay: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className="motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1 motion-safe:duration-300 motion-safe:fill-mode-backwards"
      style={{ animationDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

// ---- Section: Full text Sheet --------------------------------------------

function FullTextSheet({
  documentId,
  title,
}: {
  documentId: string;
  title: string;
}) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || text !== null) return;
    setLoading(true);
    setError(null);
    documentApi
      .getDocumentFullText(documentId)
      .then((r) => setText(r.full_text || ''))
      .catch((e) =>
        setError(e instanceof Error ? e.message : 'Failed to load text'),
      )
      .finally(() => setLoading(false));
  }, [open, documentId, text]);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          className={cn(
            'inline-flex items-center justify-center gap-1.5 rounded-md',
            'border border-border bg-card py-2 text-sm font-medium',
            'transition-colors hover:bg-muted',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
          )}
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span>View full text</span>
        </button>
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="leading-snug">{title}</SheetTitle>
          <SheetDescription>
            Full extracted opinion text. Use ⌘F (or Ctrl+F) to search within.
          </SheetDescription>
        </SheetHeader>
        <ScrollArea className="mt-4 h-[calc(100vh-9rem)] pr-2">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-xs text-muted-foreground">
              <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> Loading…
            </div>
          ) : error ? (
            <ErrorBlock>{error}</ErrorBlock>
          ) : text ? (
            <article
              className={cn(
                'prose prose-sm max-w-none dark:prose-invert',
                'whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground/90',
              )}
            >
              {text}
            </article>
          ) : (
            <EmptyLine>No body text extracted from this opinion.</EmptyLine>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

function DocumentHeader({ doc }: { doc: DocumentSummary }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-base font-semibold leading-snug text-foreground">
        {formatCaseTitle(doc.title)}
      </h2>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        {doc.court && <CourtPill court={doc.court} />}
        {doc.year && <span className="font-mono tabular-nums">{doc.year}</span>}
        {doc.docket && (
          <>
            <span aria-hidden>·</span>
            <span className="font-mono">{doc.docket}</span>
          </>
        )}
      </div>
    </div>
  );
}

function DocumentSkeleton() {
  return (
    <div className="flex flex-col gap-6 px-5 py-5">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
      <Skeleton className="h-20" />
      <Skeleton className="h-32" />
    </div>
  );
}

// ---- Section: Summary -----------------------------------------------------

function SummarySection({ documentId }: { documentId: string }) {
  const [snippet, setSnippet] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    documentApi
      .getDocumentSummary(documentId)
      .then((r) => mounted && setSnippet(r.snippet))
      .catch(() => mounted && setSnippet(''))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [documentId]);

  return (
    <Section label="Summary">
      {loading ? (
        <Skeleton className="h-16" />
      ) : snippet ? (
        <p className="text-sm leading-relaxed text-foreground/90">{snippet}</p>
      ) : (
        <EmptyLine>No body text extracted from this opinion.</EmptyLine>
      )}
    </Section>
  );
}

// ---- Section: Cites out ---------------------------------------------------

// Visual baseline: a case with this many cites is "average". Above 1.0
// means above-average (teal); above 1.5 means a hub (amber). Tuned for a
// SCOTUS corpus where most opinions cite ~5-15 other cases.
const CITES_AVG_REFERENCE = 8;
const CITED_BY_AVG_REFERENCE = 4;

function CitesSection({ documentId }: { documentId: string }) {
  const [rows, setRows] = useState<CitationOutgoing[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const pulseGraph = useGraphFocus((s) => s.pulse);

  useEffect(() => {
    let mounted = true;
    setRows(null);
    setError(null);
    setShowAll(false);
    documentApi
      .getAllCitations(documentId, CITES_INITIAL_LIMIT)
      .then((r) => mounted && setRows(r))
      .catch(
        (e) => mounted && setError(e instanceof Error ? e.message : 'Failed'),
      );
    return () => {
      mounted = false;
    };
  }, [documentId]);

  const loadAll = async () => {
    setLoadingMore(true);
    try {
      const all = await documentApi.getAllCitations(documentId, CITES_PAGE_SIZE * 5);
      setRows(all);
      setShowAll(true);
    } finally {
      setLoadingMore(false);
    }
  };

  // Spark scales by resolved count (the "in-corpus connectivity" signal).
  // External + unresolved rows count toward the total in the hint label
  // but not toward the average-comparison spark, since they're not graph
  // edges.
  const resolvedCount = rows?.filter((r) => r.state === 'resolved').length ?? 0;

  return (
    <Section
      label="Cites"
      hint={rows ? String(rows.length) : undefined}
      hintTone="default"
      spark={rows ? resolvedCount / CITES_AVG_REFERENCE : null}
    >
      {error ? (
        <EmptyLine tone="error">{error}</EmptyLine>
      ) : !rows ? (
        <ListSkeleton lines={3} />
      ) : rows.length === 0 ? (
        <EmptyLine>This opinion does not contain any extractable citations.</EmptyLine>
      ) : (
        <>
          <ul className="flex flex-col gap-1">
            {rows.map((row) => (
              <li key={row.citation_id}>
                <CitationRow
                  row={row}
                  onClick={() => row.doc_id && pulseGraph(row.doc_id)}
                />
              </li>
            ))}
          </ul>
          {!showAll && rows.length === CITES_INITIAL_LIMIT && (
            <button
              type="button"
              onClick={loadAll}
              disabled={loadingMore}
              className={cn(
                'mt-2 inline-flex items-center justify-center gap-1.5 rounded-md',
                'border border-border bg-background px-2.5 py-1 text-xs',
                'text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
                'disabled:opacity-50',
              )}
            >
              {loadingMore && <Loader2 className="h-3 w-3 animate-spin" />}
              View all citations
            </button>
          )}
        </>
      )}
    </Section>
  );
}

// ---- Section: Cited by ----------------------------------------------------

function CitedBySection({ documentId }: { documentId: string }) {
  const [rows, setRows] = useState<RelatedCase[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pulseGraph = useGraphFocus((s) => s.pulse);

  useEffect(() => {
    let mounted = true;
    setRows(null);
    setError(null);
    documentApi
      .getCitedBy(documentId, 50)
      .then((r) => mounted && setRows(r))
      .catch(
        (e) => mounted && setError(e instanceof Error ? e.message : 'Failed'),
      );
    return () => {
      mounted = false;
    };
  }, [documentId]);

  return (
    <Section
      label="Cited by"
      hint={rows ? String(rows.length) : undefined}
      spark={rows ? rows.length / CITED_BY_AVG_REFERENCE : null}
    >
      {error ? (
        <EmptyLine tone="error">{error}</EmptyLine>
      ) : !rows ? (
        <ListSkeleton lines={2} />
      ) : rows.length === 0 ? (
        <EmptyLine>No indexed cases cite this opinion.</EmptyLine>
      ) : (
        <ul className="flex flex-col gap-1">
          {rows.map((row) => (
            <li key={row.citation_id}>
              <RelatedRow
                row={row}
                onClick={() => pulseGraph(row.doc_id)}
              />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// ---- Section: Similar cases ----------------------------------------------

function SimilarSection({ documentId }: { documentId: string }) {
  const [rows, setRows] = useState<SimilarDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pulseGraph = useGraphFocus((s) => s.pulse);

  useEffect(() => {
    let mounted = true;
    setRows(null);
    setError(null);
    searchApi
      .getSimilar(documentId, 5, 0)
      .then((r) => mounted && setRows(r))
      .catch(
        (e) => mounted && setError(e instanceof Error ? e.message : 'Failed'),
      );
    return () => {
      mounted = false;
    };
  }, [documentId]);

  return (
    <Section label="Similar cases" hint={rows ? String(rows.length) : undefined}>
      {error ? (
        <EmptyLine tone="error">{error}</EmptyLine>
      ) : !rows ? (
        <ListSkeleton lines={2} />
      ) : rows.length === 0 ? (
        <EmptyLine>No semantically similar cases yet.</EmptyLine>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rows.map((row) => (
            <li key={row.doc_id}>
              <SimilarRow
                row={row}
                onClick={() => pulseGraph(row.doc_id)}
              />
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// ---- Section: Citation details (collapsed) -------------------------------

function CitationDetailsDisclosure({ citations }: { citations: CitationItem[] }) {
  const linked = citations.filter((c) => c.to_doc_id).length;
  const avgConfidence = citations.length
    ? citations.reduce((sum, c) => sum + c.confidence, 0) / citations.length
    : 0;

  return (
    <Disclosure label="Citation details">
      <div className="grid grid-cols-3 gap-3 rounded-md border border-border bg-muted/30 p-3 text-center">
        <Stat value={citations.length} label="Total" />
        <Stat value={linked} label="Linked" />
        <Stat value={`${(avgConfidence * 100).toFixed(0)}%`} label="Avg conf." />
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
        Confidence reflects how strongly the parser linked each citation to a
        document in your corpus. Click an edge in the graph to see a
        per-citation breakdown.
      </p>
    </Disclosure>
  );
}

// ---------------------------------------------------------------------------
// Citation inspector — single citation edge, drilled into for confidence
// ---------------------------------------------------------------------------

function CitationInspector({ id, documentId }: { id: string; documentId?: string }) {
  const [citation, setCitation] = useState<CitationItem | null>(null);
  const [resolvedDoc, setResolvedDoc] = useState<DocumentSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pulseGraph = useGraphFocus((s) => s.pulse);

  useEffect(() => {
    let mounted = true;
    setCitation(null);
    setResolvedDoc(null);
    setError(null);
    if (!documentId) {
      setError('Missing document context');
      return;
    }
    documentApi
      .getDocument(documentId)
      .then((d) => {
        if (!mounted) return;
        const found = d.citations.find((c) => c.id === id);
        setCitation(found ?? null);
        if (found?.to_doc_id) {
          documentApi
            .getDocument(found.to_doc_id)
            .then((other) => mounted && setResolvedDoc(other.document))
            .catch(() => {});
        }
      })
      .catch(
        (e) => mounted && setError(e instanceof Error ? e.message : 'Failed to load'),
      );
    return () => {
      mounted = false;
    };
  }, [id, documentId]);

  if (error) return <ErrorBlock>{error}</ErrorBlock>;
  if (!citation) return <DocumentSkeleton />;

  const notes: string[] = (() => {
    try {
      const raw = citation.resolution_notes;
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return citation.resolution_notes ? [citation.resolution_notes] : [];
    }
  })();

  return (
    <div className="flex flex-col gap-6">
      <Section label="Citation">
        <div className="flex flex-col gap-2">
          <CitationText
            text={citation.raw_text}
            normalizedKey={citation.normalized_key}
          />
          <ConfidenceBadge value={citation.confidence} resolved={!!citation.to_doc_id} />
        </div>
      </Section>

      <Section label="Resolved to">
        {citation.to_doc_id ? (
          resolvedDoc ? (
            <button
              type="button"
              onClick={() => pulseGraph(resolvedDoc.id)}
              className="block w-full rounded-md border border-border bg-card p-3 text-left transition-colors hover:bg-muted"
            >
              <div className="text-sm font-medium leading-snug">
                {formatCaseTitle(resolvedDoc.title)}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
                {resolvedDoc.court && <CourtPill court={resolvedDoc.court} />}
                {resolvedDoc.year && (
                  <span className="font-mono tabular-nums">{resolvedDoc.year}</span>
                )}
              </div>
            </button>
          ) : (
            <Skeleton className="h-12" />
          )
        ) : (
          <div className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
            <div className="mb-1 font-medium text-foreground">Unresolved</div>
            No matching document found in the corpus.
            {notes.length > 0 && (
              <ul className="mt-2 list-disc pl-4">
                {notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Section>

      <Section label="Metadata">
        <div className="flex flex-col gap-1">
          <DataRow label="Reporter" value={citation.reporter ?? '—'} />
          <DataRow label="Volume" value={citation.volume ?? '—'} mono />
          <DataRow label="Page" value={citation.page ?? '—'} mono />
          <DataRow label="Year" value={citation.year ?? '—'} mono />
          <DataRow label="Source page" value={citation.page_number ?? '—'} mono />
          <DataRow label="Type" value={citation.citation_type} />
        </div>
      </Section>

      <Disclosure label="Confidence breakdown">
        <ConfidenceBreakdown
          breakdown={citation.confidence_breakdown}
          total={citation.confidence}
        />
        {notes.length > 0 && (
          <ul className="mt-2 list-disc pl-4 text-xs text-muted-foreground">
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        )}
      </Disclosure>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Similarity inspector — clicked semantic edge between two docs
// ---------------------------------------------------------------------------

function SimilarityInspector({
  sourceId,
  targetId,
  score,
}: {
  sourceId: string;
  targetId: string;
  score: number;
}) {
  const [source, setSource] = useState<DocumentSummary | null>(null);
  const [target, setTarget] = useState<DocumentSummary | null>(null);
  const pulseGraph = useGraphFocus((s) => s.pulse);

  useEffect(() => {
    let mounted = true;
    setSource(null);
    setTarget(null);
    documentApi.getDocument(sourceId).then((d) => mounted && setSource(d.document)).catch(() => {});
    documentApi.getDocument(targetId).then((d) => mounted && setTarget(d.document)).catch(() => {});
    return () => {
      mounted = false;
    };
  }, [sourceId, targetId]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/5 p-4">
        <span className="text-[11px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
          Cosine similarity
        </span>
        <span className="font-mono text-3xl font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
          {(score * 100).toFixed(1)}%
        </span>
      </div>
      <Section label="Source">
        <DocCard doc={source} fallbackId={sourceId} onPulse={pulseGraph} />
      </Section>
      <Section label="Target">
        <DocCard doc={target} fallbackId={targetId} onPulse={pulseGraph} />
      </Section>
    </div>
  );
}

function DocCard({
  doc,
  fallbackId,
  onPulse,
}: {
  doc: DocumentSummary | null;
  fallbackId: string;
  onPulse: (id: string) => void;
}) {
  if (!doc) {
    return (
      <div className="rounded-md border border-border bg-muted/30 p-3 font-mono text-xs text-muted-foreground">
        {fallbackId.slice(0, 8)}…
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onPulse(doc.id)}
      className="block w-full rounded-md border border-border bg-card p-3 text-left transition-colors hover:bg-muted"
    >
      <div className="text-sm font-medium leading-snug">{formatCaseTitle(doc.title)}</div>
      <div className="mt-1 flex items-center gap-x-2 text-xs text-muted-foreground">
        {doc.court && <CourtPill court={doc.court} />}
        {doc.year && <span className="font-mono tabular-nums">{doc.year}</span>}
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Edge inspector (rare path)
// ---------------------------------------------------------------------------

function EdgeInspector({ id }: { id: string }) {
  return (
    <div className="flex flex-col gap-3 text-xs text-muted-foreground">
      <p>
        Edge <span className="font-mono text-foreground">{id.slice(0, 8)}…</span> selected.
      </p>
      <p>
        Open one of the endpoint cases to inspect the citation breakdown.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable section primitives — tight design system within the panel
// ---------------------------------------------------------------------------

function Section({
  label,
  hint,
  hintTone = 'default',
  /** Optional 0-1 ratio rendered as a tiny inline horizontal bar next to
   *  the label. Communicates "this case has a lot of cites" or "this
   *  case has very few" relative to the corpus average without numbers. */
  spark,
  children,
}: {
  label: string;
  hint?: string;
  hintTone?: 'default' | 'accent';
  spark?: number | null;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </h3>
          {spark != null && spark > 0 && <Spark ratio={spark} />}
        </div>
        {hint != null && (
          <span
            className={cn(
              'rounded-sm px-1.5 py-0 font-mono text-[10px] tabular-nums',
              hintTone === 'accent'
                ? 'bg-accent/10 text-accent'
                : 'bg-muted text-muted-foreground',
            )}
          >
            {hint}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

function Spark({ ratio }: { ratio: number }) {
  // Clamp 0–2 (so a node 2× the corpus average reads as "full bar"). The
  // bar fills proportionally; tone shifts above 1.5 (notable) and 1.0
  // (above-average).
  const clamped = Math.max(0, Math.min(2, ratio));
  const pct = (clamped / 2) * 100;
  const tone =
    clamped >= 1.5
      ? 'bg-amber-500 dark:bg-amber-400'
      : clamped >= 1
      ? 'bg-teal-500 dark:bg-teal-400'
      : 'bg-slate-400 dark:bg-slate-500';
  return (
    <span
      className="relative inline-block h-1 w-12 overflow-hidden rounded-full bg-muted"
      title={`${(clamped * 100).toFixed(0)}% of corpus average`}
      aria-hidden
    >
      <span
        className={cn('absolute inset-y-0 left-0 rounded-full transition-all duration-300', tone)}
        style={{ width: `${pct}%` }}
      />
    </span>
  );
}

/**
 * Polymorphic citation row supporting three resolution states:
 *   - resolved: the cited work is in the corpus → clickable, pulses the
 *     graph node on click; renders title + court/year + confidence pill.
 *   - external: CourtListener resolved the cite but the work isn't in
 *     the corpus → "Not in corpus" pill, opens external URL in a new tab.
 *   - unresolved: neither path produced a hit → muted italic raw_text,
 *     non-interactive (no useful destination to click through to).
 *
 * Why a single component instead of three: the row chrome (padding,
 * confidence pill placement, hover affordance) needs to stay aligned
 * across states so the user reads them as one list, not three.
 */
function CitationRow({
  row,
  onClick,
}: {
  row: CitationOutgoing;
  onClick: () => void;
}) {
  if (row.state === 'resolved') {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'group flex w-full items-center gap-3 rounded-md border border-transparent',
          'px-2 py-1.5 text-left transition-colors',
          'hover:border-border hover:bg-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        )}
      >
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">
            {row.title ? formatCaseTitle(row.title) : row.raw_text}
          </div>
          <div className="mt-0.5 flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
            {row.court && <span className="truncate">{row.court}</span>}
            {row.court && row.year && <span aria-hidden>·</span>}
            {row.year && <span className="font-mono tabular-nums">{row.year}</span>}
            {row.citation_type !== 'full' && (
              <span className="rounded-sm bg-muted px-1 py-0 font-mono uppercase text-muted-foreground/70">
                {row.citation_type}
              </span>
            )}
          </div>
        </div>
        <ConfidencePill value={row.confidence} />
      </button>
    );
  }

  if (row.state === 'external') {
    const href = row.external_url
      ? `https://www.courtlistener.com${row.external_url}`
      : null;
    const Wrapper: React.ElementType = href ? 'a' : 'div';
    const wrapperProps = href
      ? { href, target: '_blank', rel: 'noopener noreferrer' as const }
      : {};
    return (
      <Wrapper
        {...wrapperProps}
        className={cn(
          'group flex w-full items-center gap-3 rounded-md border border-transparent',
          'px-2 py-1.5 text-left transition-colors',
          href && 'hover:border-border hover:bg-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        )}
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 truncate text-sm font-medium text-foreground">
            <span className="truncate">
              {row.external_case_name
                ? formatCaseTitle(row.external_case_name)
                : row.raw_text}
            </span>
            {href && (
              <ExternalLink
                className="h-3 w-3 shrink-0 text-muted-foreground/70"
                aria-hidden
              />
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
            <span className="rounded-sm bg-amber-500/10 px-1 py-0 font-mono text-[9px] uppercase tracking-wide text-amber-700 dark:text-amber-400">
              Not in corpus
            </span>
            {row.external_year && (
              <span className="font-mono tabular-nums">{row.external_year}</span>
            )}
            {row.citation_type !== 'full' && (
              <span className="rounded-sm bg-muted px-1 py-0 font-mono uppercase text-muted-foreground/70">
                {row.citation_type}
              </span>
            )}
          </div>
        </div>
      </Wrapper>
    );
  }

  // state === 'unresolved'
  return (
    <div className="flex w-full items-center gap-3 rounded-md px-2 py-1.5">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm italic text-muted-foreground/80">
          {row.raw_text}
        </div>
        <div className="mt-0.5 text-[11px] text-muted-foreground/70">
          Unresolved
          {row.citation_type !== 'full' && (
            <span className="ml-1.5 rounded-sm bg-muted px-1 py-0 font-mono uppercase text-muted-foreground/70">
              {row.citation_type}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function RelatedRow({
  row,
  onClick,
}: {
  row: RelatedCase;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex w-full items-center gap-3 rounded-md border border-transparent',
        'px-2 py-1.5 text-left transition-colors',
        'hover:border-border hover:bg-muted',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium text-foreground">{formatCaseTitle(row.title)}</div>
        <div className="mt-0.5 flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
          {row.court && <span className="truncate">{row.court}</span>}
          {row.court && row.year && <span aria-hidden>·</span>}
          {row.year && <span className="font-mono tabular-nums">{row.year}</span>}
          {row.citation_type !== 'full' && (
            <span className="rounded-sm bg-muted px-1 py-0 font-mono uppercase text-muted-foreground/70">
              {row.citation_type}
            </span>
          )}
        </div>
      </div>
      <ConfidencePill value={row.confidence} />
    </button>
  );
}

function ConfidencePill({ value }: { value: number }) {
  const tone =
    value >= 0.9
      ? 'high'
      : value >= 0.7
      ? 'medium'
      : value >= 0.4
      ? 'low'
      : 'unresolved';
  const classes = {
    high: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    medium: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    low: 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
    unresolved: 'bg-muted text-muted-foreground',
  }[tone];
  return (
    <span
      className={cn(
        'shrink-0 rounded-sm px-1.5 py-0.5 font-mono text-[10px] tabular-nums',
        classes,
      )}
      title={`Confidence ${(value * 100).toFixed(0)}%`}
    >
      {(value * 100).toFixed(0)}
    </span>
  );
}

function SimilarRow({
  row,
  onClick,
}: {
  row: SimilarDocument;
  onClick: () => void;
}) {
  const pct = Math.max(0, Math.min(1, row.similarity_score));
  const widthStyle = { width: `${(pct * 100).toFixed(1)}%` };
  // Color encodes strength so the eye can scan the list and feel which
  // neighbours are tightly bound vs merely related. Tiers chosen to be
  // intuitive without legend: warm = strong, cool = mid, gray = weak.
  const tone =
    pct >= 0.9
      ? {
          bar: 'bg-amber-500 dark:bg-amber-400',
          text: 'text-amber-700 dark:text-amber-400',
        }
      : pct >= 0.75
      ? {
          bar: 'bg-teal-500 dark:bg-teal-400',
          text: 'text-teal-700 dark:text-teal-400',
        }
      : {
          bar: 'bg-slate-400 dark:bg-slate-500',
          text: 'text-muted-foreground',
        };
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group flex w-full flex-col gap-1.5 rounded-md border border-transparent',
        'px-2 py-1.5 text-left transition-colors duration-150',
        'hover:border-border hover:bg-muted',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-foreground">{formatCaseTitle(row.title)}</span>
        <span
          className={cn(
            'shrink-0 font-mono text-[10px] tabular-nums',
            tone.text,
          )}
        >
          {(pct * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all duration-300', tone.bar)}
          style={widthStyle}
        />
      </div>
      {(row.court || row.year) && (
        <div className="flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
          {row.court && <span className="truncate">{row.court}</span>}
          {row.court && row.year && <span aria-hidden>·</span>}
          {row.year && <span className="font-mono tabular-nums">{row.year}</span>}
        </div>
      )}
    </button>
  );
}

function FooterAction({
  label,
  icon,
  onClick,
  tone = 'default',
}: {
  label: string;
  icon?: React.ReactNode;
  onClick: () => void;
  tone?: 'default' | 'accent';
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md',
        'py-2 text-sm font-medium',
        'transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50',
        tone === 'accent'
          ? 'border border-amber-500/40 bg-amber-500/10 text-amber-700 hover:bg-amber-500/15 dark:text-amber-400'
          : 'border border-border bg-card hover:bg-muted',
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className="font-mono text-base font-semibold tabular-nums">{value}</span>
      <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
    </div>
  );
}

function DataRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          'text-right text-sm text-foreground',
          mono && 'font-mono tabular-nums',
        )}
      >
        {value}
      </span>
    </div>
  );
}

function ListSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-1.5">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="h-9" />
      ))}
    </div>
  );
}

function EmptyLine({
  children,
  tone = 'muted',
}: {
  children: React.ReactNode;
  tone?: 'muted' | 'error';
}) {
  return (
    <p
      className={cn(
        'text-xs',
        tone === 'error' ? 'text-destructive' : 'text-muted-foreground',
      )}
    >
      {children}
    </p>
  );
}

function ErrorBlock({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
      {children}
    </div>
  );
}
