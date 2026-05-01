'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  FileText,
  Upload,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useToast } from '@/components/ui/use-toast';
import { Trash2 } from 'lucide-react';
import { documentApi as docApi } from '@/lib/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { CourtPill } from '@/components/primitives/CourtPill';
import { EmptyState } from '@/components/primitives/EmptyState';
import { CitationSparkline } from '@/components/primitives/CitationSparkline';
import { StatusBadge } from '@/components/upload/UploadModal';
import { formatCaseTitle, formatRelativeDate } from '@/lib/format';
import { useUploadStore, UploadItem } from '@/lib/upload-store';
import {
  documentApi,
  graphApi,
  DocumentSummary,
  GraphResponse,
} from '@/lib/api';
import { cn } from '@/lib/utils';

interface RowMetrics {
  inDegree: number;
  outDegree: number;
}

type SortKey = 'title' | 'court' | 'year' | 'inDegree' | 'outDegree' | 'created_at';

export default function DocumentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const openModal = useUploadStore((s) => s.openModal);
  const pendingItems = useUploadStore((s) => s.items);

  const { toast } = useToast();
  const [docs, setDocs] = useState<DocumentSummary[] | null>(null);
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  // Track B — confirmation dialog for "Remove from library".
  const [pendingDelete, setPendingDelete] =
    useState<{ id: string; title: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleRemove = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    try {
      await docApi.remove(pendingDelete.id);
      setDocs((prev) =>
        prev ? prev.filter((d) => d.id !== pendingDelete.id) : prev,
      );
      toast({
        title: 'Removed',
        description: `${pendingDelete.title} removed from your library.`,
      });
      setPendingDelete(null);
    } catch (e) {
      toast({
        title: 'Could not remove',
        description: e instanceof Error ? e.message : 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setDeleting(false);
    }
  };

  // Refresh on every "ready" transition so freshly-processed cases appear
  // in the table without manual reload.
  const readyVersion = useMemo(
    () => pendingItems.filter((i) => i.status === 'ready').length,
    [pendingItems],
  );

  useEffect(() => {
    let mounted = true;
    Promise.all([
      documentApi.getDocuments(0, 500),
      graphApi.getGraph({ minConfidence: 0 }),
    ])
      .then(([d, g]) => {
        if (!mounted) return;
        setDocs(d.items);
        setGraph(g);
      })
      .catch(
        (e) => mounted && setError(e instanceof Error ? e.message : 'Failed to load'),
      );
    return () => {
      mounted = false;
    };
  }, [readyVersion]);

  // Auto-open the upload modal on ?upload=1 so /upload links land here
  // already in the right state. We only run this once per arrival.
  useEffect(() => {
    if (searchParams?.get('upload') === '1') {
      openModal();
      // Strip the query param so reload doesn't re-trigger.
      router.replace('/documents');
    }
  }, [searchParams, openModal, router]);

  const metrics = useMemo<Record<string, RowMetrics>>(() => {
    if (!graph) return {};
    const result: Record<string, RowMetrics> = {};
    for (const node of graph.nodes) result[node.id] = { inDegree: 0, outDegree: 0 };
    for (const edge of graph.edges) {
      if (result[edge.source]) result[edge.source].outDegree += 1;
      if (result[edge.target]) result[edge.target].inDegree += 1;
    }
    return result;
  }, [graph]);

  // Pending items that haven't been confirmed in the API list yet — the
  // optimistic rows that appear above real documents.
  const pendingRows = useMemo(() => {
    if (!docs) return pendingItems.filter((i) => i.status !== 'ready');
    const liveIds = new Set(docs.map((d) => d.id));
    return pendingItems.filter(
      (i) => i.status !== 'ready' || (i.documentId && !liveIds.has(i.documentId)),
    );
  }, [pendingItems, docs]);

  const rows = useMemo(() => {
    if (!docs) return [];
    const lower = query.trim().toLowerCase();
    const filtered = lower
      ? docs.filter(
          (d) =>
            d.title.toLowerCase().includes(lower) ||
            (d.court ?? '').toLowerCase().includes(lower) ||
            (d.docket ?? '').toLowerCase().includes(lower),
        )
      : docs;
    const sorted = [...filtered].sort((a, b) => {
      const valueA = sortValue(a, metrics, sortKey);
      const valueB = sortValue(b, metrics, sortKey);
      const dir = sortDir === 'asc' ? 1 : -1;
      if (valueA == null && valueB == null) return 0;
      if (valueA == null) return 1;
      if (valueB == null) return -1;
      if (valueA < valueB) return -1 * dir;
      if (valueA > valueB) return 1 * dir;
      return 0;
    });
    return sorted;
  }, [docs, query, metrics, sortKey, sortDir]);

  const onSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const corpusEmpty =
    docs !== null && docs.length === 0 && pendingRows.length === 0;

  if (corpusEmpty) {
    return (
      <div className="mx-auto flex h-full max-w-[1400px] items-center justify-center px-6 py-6">
        <EmptyState
          icon={FileText}
          title="No documents yet"
          description="Upload a PDF or seed your corpus with SCOTUS opinions to start exploring citations."
          actions={
            <>
              <Button variant="accent" size="sm" onClick={openModal}>
                <Upload className="h-3.5 w-3.5" /> Upload PDF
              </Button>
              <Link href="/graph">
                <Button variant="outline" size="sm">
                  Open empty graph
                </Button>
              </Link>
            </>
          }
        />
      </div>
    );
  }

  // Stats for the dashboard bar — derived from data we already have.
  const stats = useMemo(() => {
    if (!docs || docs.length === 0) return null;
    const years = docs
      .map((d) => d.year)
      .filter((y): y is number => typeof y === 'number');
    const minYear = years.length ? Math.min(...years) : null;
    const maxYear = years.length ? Math.max(...years) : null;
    let mostCited: { title: string; count: number } | null = null;
    let mostConnected: { title: string; count: number } | null = null;
    for (const d of docs) {
      const m = metrics[d.id];
      if (!m) continue;
      const formattedTitle = formatCaseTitle(d.title);
      if (!mostCited || m.inDegree > mostCited.count) {
        mostCited = { title: formattedTitle, count: m.inDegree };
      }
      const total = m.inDegree + m.outDegree;
      if (!mostConnected || total > mostConnected.count) {
        mostConnected = { title: formattedTitle, count: total };
      }
    }
    return { count: docs.length, minYear, maxYear, mostCited, mostConnected };
  }, [docs, metrics]);

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-6">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Your library</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {docs ? `${docs.length} ${docs.length === 1 ? 'case' : 'cases'} saved` : 'Loading…'}
            {pendingRows.length > 0 && (
              <>
                <span aria-hidden> · </span>
                <span className="text-amber-700 dark:text-amber-400">
                  {pendingRows.length} processing
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by title, court, docket…"
            className="w-64"
          />
          <Button variant="accent" size="sm" onClick={openModal}>
            <Upload className="h-3.5 w-3.5" /> Upload
          </Button>
        </div>
      </div>

      {stats && (
        <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCell label="Total cases" value={stats.count.toString()} />
          <StatCell
            label="Date range"
            value={
              stats.minYear && stats.maxYear
                ? `${stats.minYear} – ${stats.maxYear}`
                : '—'
            }
          />
          <StatCell
            label="Most cited"
            value={stats.mostCited?.title ?? '—'}
            hint={stats.mostCited ? `${stats.mostCited.count} citations in` : undefined}
            truncate
          />
          <StatCell
            label="Most connected"
            value={stats.mostConnected?.title ?? '—'}
            hint={stats.mostConnected ? `${stats.mostConnected.count} edges` : undefined}
            truncate
          />
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="rounded-md border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <SortableHeader onClick={() => onSort('title')} active={sortKey === 'title'} dir={sortDir}>
                Title
              </SortableHeader>
              <SortableHeader onClick={() => onSort('court')} active={sortKey === 'court'} dir={sortDir}>
                Court
              </SortableHeader>
              <SortableHeader onClick={() => onSort('year')} active={sortKey === 'year'} dir={sortDir} numeric>
                Year
              </SortableHeader>
              <SortableHeader
                onClick={() => onSort('inDegree')}
                active={sortKey === 'inDegree'}
                dir={sortDir}
                numeric
              >
                Cited by
              </SortableHeader>
              <SortableHeader
                onClick={() => onSort('outDegree')}
                active={sortKey === 'outDegree'}
                dir={sortDir}
                numeric
              >
                Cites
              </SortableHeader>
              <SortableHeader
                onClick={() => onSort('created_at')}
                active={sortKey === 'created_at'}
                dir={sortDir}
              >
                Added
              </SortableHeader>
              <TableHead className="w-[42px]" aria-label="Actions" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pendingRows.map((it) => (
              <PendingRow key={it.localId} item={it} />
            ))}
            {!docs &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={i}>
                  <TableCell colSpan={7}>
                    <Skeleton className="h-5" />
                  </TableCell>
                </TableRow>
              ))}
            {docs && rows.length === 0 && pendingRows.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-xs text-muted-foreground">
                  No documents match.
                </TableCell>
              </TableRow>
            )}
            {rows.map((doc) => {
              const m = metrics[doc.id] ?? { inDegree: 0, outDegree: 0 };
              return (
                <TableRow
                  key={doc.id}
                  className="group cursor-pointer transition-colors duration-150 hover:bg-muted/50"
                  onClick={() => router.push(`/graph?focus=${doc.id}`)}
                >
                  <TableCell className="max-w-[420px] font-medium">
                    <div className="flex items-center gap-2.5">
                      <CitationSparkline
                        outgoing={m.outDegree}
                        incoming={m.inDegree}
                      />
                      <span className="truncate transition-colors duration-150 group-hover:text-accent">
                        {formatCaseTitle(doc.title)}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {doc.court ? (
                      <CourtPill court={doc.court} />
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="font-mono tabular-nums">{doc.year ?? '—'}</TableCell>
                  <TableCell className="font-mono tabular-nums">{m.inDegree}</TableCell>
                  <TableCell className="font-mono tabular-nums">{m.outDegree}</TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {formatRelativeDate(doc.created_at)}
                  </TableCell>
                  <TableCell>
                    {/* Stop click propagation so the row's onClick to
                        navigate to /graph doesn't fire when the user is
                        opening the confirm dialog. */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setPendingDelete({ id: doc.id, title: doc.title });
                      }}
                      className={cn(
                        'inline-flex h-7 w-7 items-center justify-center rounded',
                        'text-muted-foreground/60 transition-colors',
                        'opacity-0 group-hover:opacity-100',
                        'hover:bg-destructive/10 hover:text-destructive',
                        'focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30',
                      )}
                      aria-label={`Remove ${doc.title} from library`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Remove from library?</DialogTitle>
            <DialogDescription>
              {pendingDelete && (
                <>
                  &ldquo;{formatCaseTitle(pendingDelete.title)}&rdquo; will be
                  removed along with its citations and semantic neighbours.
                  This cannot be undone.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPendingDelete(null)}
              disabled={deleting}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleRemove}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? 'Removing…' : 'Remove'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Optimistic pending row (matches table column count)
// ---------------------------------------------------------------------------

function PendingRow({ item }: { item: UploadItem }) {
  return (
    <TableRow className="bg-amber-500/5">
      <TableCell className="max-w-[480px] truncate font-medium">
        <span className="text-foreground">
          {item.resolvedTitle || item.fileName}
        </span>
      </TableCell>
      <TableCell colSpan={4}>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <StatusBadge status={item.status} />
          {item.status === 'uploading' && <span>{item.progress}%</span>}
          {item.status === 'processing' && <span>extracting citations…</span>}
          {item.status === 'failed' && (
            <span className="text-destructive">{item.error}</span>
          )}
        </div>
      </TableCell>
      <TableCell className="font-mono tabular-nums text-muted-foreground">
        just now
      </TableCell>
      <TableCell />
    </TableRow>
  );
}

function sortValue(
  d: DocumentSummary,
  metrics: Record<string, RowMetrics>,
  key: SortKey,
): number | string | null {
  switch (key) {
    case 'title':
      return d.title.toLowerCase();
    case 'court':
      return (d.court ?? '').toLowerCase();
    case 'year':
      return d.year ?? null;
    case 'inDegree':
      return metrics[d.id]?.inDegree ?? 0;
    case 'outDegree':
      return metrics[d.id]?.outDegree ?? 0;
    case 'created_at':
      return d.created_at;
  }
}

function StatCell({
  label,
  value,
  hint,
  truncate = false,
}: {
  label: string;
  value: string;
  hint?: string;
  truncate?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-border bg-card px-3 py-2.5">
      <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          'text-sm font-semibold leading-tight',
          truncate && 'truncate',
        )}
        title={truncate ? value : undefined}
      >
        {value}
      </span>
      {hint && (
        <span className="text-[11px] tabular-nums text-muted-foreground">{hint}</span>
      )}
    </div>
  );
}

function SortableHeader({
  children,
  active,
  dir,
  numeric,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  dir: 'asc' | 'desc';
  numeric?: boolean;
  onClick: () => void;
}) {
  return (
    <TableHead
      className={cn(
        'cursor-pointer select-none transition-colors hover:text-foreground',
        numeric && 'text-right',
      )}
      onClick={onClick}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {active ? (
          dir === 'asc' ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-40" />
        )}
      </span>
    </TableHead>
  );
}
