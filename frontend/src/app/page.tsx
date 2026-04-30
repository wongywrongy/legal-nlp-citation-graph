'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Network, FileText, Upload } from 'lucide-react';
import { StatTile } from '@/components/primitives/StatTile';
import { CourtPill } from '@/components/primitives/CourtPill';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { documentApi, graphApi, statsApi, DocumentSummary, GraphNode, StatsResponse } from '@/lib/api';
import { formatCaseTitle, formatRelativeDate } from '@/lib/format';

export default function Dashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [topCases, setTopCases] = useState<GraphNode[]>([]);
  const [recent, setRecent] = useState<DocumentSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    // Stats first — if the corpus is empty, skip the graph + documents
    // round-trips entirely; the EmptyState section will render instead.
    statsApi
      .getStats()
      .then((s) => {
        if (!mounted) return;
        setStats(s);
        if (s.total_documents === 0) {
          setTopCases([]);
          setRecent([]);
          return;
        }
        return Promise.all([
          graphApi.getGraph({ minConfidence: 0 }),
          documentApi.getDocuments(0, 5),
        ]).then(([g, d]) => {
          if (!mounted) return;
          const sorted = [...g.nodes]
            .filter((n) => (n.meta?.centrality ?? 0) > 0)
            .sort((a, b) => (b.meta?.centrality ?? 0) - (a.meta?.centrality ?? 0))
            .slice(0, 10);
          setTopCases(sorted);
          setRecent(d.items);
        });
      })
      .catch((e) => mounted && setError(e instanceof Error ? e.message : 'Failed to load'));
    return () => {
      mounted = false;
    };
  }, []);

  const isEmpty = stats?.total_documents === 0;

  return (
    <div className="mx-auto max-w-[1280px] px-6 py-6">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Corpus overview</h1>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Citation extraction status, central cases, and recent ingest activity.
          </p>
        </div>
        <Link href="/upload">
          <Button variant="outline" size="sm">
            <Upload className="h-3.5 w-3.5" /> Upload PDF
          </Button>
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stats ? (
          <>
            <StatTile label="Documents" value={stats.total_documents} hint="In corpus" />
            <StatTile label="Citations" value={stats.total_citations} hint="Extracted" />
            <StatTile
              label="Resolution rate"
              value={`${(stats.resolution_rate * 100).toFixed(0)}%`}
              hint={`${stats.resolved_citations} / ${stats.total_citations} linked`}
            />
            <StatTile
              label="Avg confidence"
              value={`${(stats.avg_confidence * 100).toFixed(0)}%`}
              hint="Across resolved + unresolved"
            />
          </>
        ) : (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[88px]" />)
        )}
      </div>

      {isEmpty ? (
        <EmptyState />
      ) : (
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold">Most central cases</h2>
              <Link href="/graph" className="text-xs text-muted-foreground hover:text-foreground">
                Open graph <ArrowRight className="inline h-3 w-3" />
              </Link>
            </div>
            <div className="rounded-md border border-border">
              {topCases.length === 0 ? (
                <div className="p-4 text-xs text-muted-foreground">
                  No centrality data yet. Add more citing documents.
                </div>
              ) : (
                <ul className="divide-y divide-border">
                  {topCases.map((node, i) => (
                    <li key={node.id}>
                      <Link
                        href={`/graph?focus=${node.id}`}
                        className="flex items-center gap-3 px-3 py-2 hover:bg-muted/40"
                      >
                        <span className="w-5 text-right font-mono text-2xs text-muted-foreground">{i + 1}.</span>
                        <span className="flex-1 truncate text-[13px]">{formatCaseTitle(node.label)}</span>
                        {node.meta?.court && <CourtPill court={node.meta.court} showLabel={false} />}
                        {node.meta?.year && <span className="font-mono text-2xs text-muted-foreground">{node.meta.year}</span>}
                        <span className="font-mono text-2xs tabular-nums text-muted-foreground">
                          {(node.meta?.centrality ?? 0).toFixed(3)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold">Recent uploads</h2>
              <Link href="/documents" className="text-xs text-muted-foreground hover:text-foreground">
                All <ArrowRight className="inline h-3 w-3" />
              </Link>
            </div>
            <div className="rounded-md border border-border">
              {recent.length === 0 ? (
                <div className="p-4 text-xs text-muted-foreground">No documents yet.</div>
              ) : (
                <ul className="divide-y divide-border">
                  {recent.map((doc) => (
                    <li key={doc.id}>
                      <Link href={`/graph?focus=${doc.id}`} className="block px-3 py-2 hover:bg-muted/40">
                        <div className="truncate text-[13px]">{formatCaseTitle(doc.title)}</div>
                        <div className="mt-0.5 flex items-center gap-1.5 text-2xs text-muted-foreground">
                          {doc.court && <CourtPill court={doc.court} showLabel={false} />}
                          <span>{formatRelativeDate(doc.created_at)}</span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="mt-10 rounded-md border border-dashed border-border bg-card p-10 text-center">
      <h3 className="text-sm font-semibold">Empty corpus</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Upload a court opinion PDF to begin extracting citations.
      </p>
      <div className="mt-4 flex justify-center gap-2">
        <Link href="/upload">
          <Button size="sm" variant="accent">
            <Upload className="h-3.5 w-3.5" /> Upload your first PDF
          </Button>
        </Link>
        <Link href="/documents">
          <Button size="sm" variant="outline">
            <FileText className="h-3.5 w-3.5" /> Browse
          </Button>
        </Link>
      </div>
    </div>
  );
}
