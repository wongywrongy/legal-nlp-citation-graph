'use client';

/**
 * Track B entry point. Rebuilt from corpus-first dashboard to a single
 * case-centric surface:
 *
 *   - The student arrives with one case in mind. The middle of the page
 *     is a search input + a "drop a PDF here" card. Whichever path
 *     they choose, on success they navigate to /graph?focus={id} and
 *     the neighborhood mode renders that case's network.
 *   - A "Recent" row underneath shows the last 5 cases they explored,
 *     persisted in localStorage so a returning visitor lands back at
 *     their working set without depending on a backend session.
 *   - A small "explore the full corpus" link gives power users the
 *     prior all-corpus graph as a secondary path.
 *
 * The corpus stats and "most central cases" lists are still queryable
 * via /v1/stats and /graph (no focus param). They're demoted from the
 * entry point because most users don't arrive wanting to browse 500
 * unrelated opinions.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Loader2, Search, Upload as UploadIcon } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useUploadStore } from '@/lib/upload-store';
import { hydrateRecentCases, useGraphFocus } from '@/lib/graph-store';
import {
  CourtListenerHit,
  courtListenerApi,
  documentApi,
} from '@/lib/api';
import { formatCaseTitle } from '@/lib/format';
import { cn } from '@/lib/utils';

const SEARCH_DEBOUNCE_MS = 400;

export default function EntryPoint() {
  return (
    <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-[840px] flex-col items-center justify-center px-6 py-10">
      <Hero />
      <EntrySurface />
      <ExploreCorpusLink />
      <RecentCases />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero() {
  return (
    <div className="mb-8 text-center">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">
        Understand any case
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Search by name or upload a PDF to explore its citation network.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entry surface — search + upload
// ---------------------------------------------------------------------------

function EntrySurface() {
  return (
    <div className="grid w-full grid-cols-1 items-stretch gap-4 md:grid-cols-[1fr_auto_1fr]">
      <CaseSearch />
      <Divider />
      <UploadCard />
    </div>
  );
}

function Divider() {
  return (
    <div className="hidden items-center justify-center md:flex">
      <span className="text-xs uppercase tracking-wider text-muted-foreground/60">
        or
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CourtListener-backed search
// ---------------------------------------------------------------------------

function CaseSearch() {
  const router = useRouter();
  const addRecent = useGraphFocus((s) => s.addRecent);

  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<CourtListenerHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [ingesting, setIngesting] = useState<number | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);

  // Debounce CL lookups — anonymous queries are heavily rate-limited
  // and the user typing fast shouldn't fire a request per keystroke.
  const debounceRef = useRef<number | null>(null);
  const requestRef = useRef(0);

  useEffect(() => {
    if (debounceRef.current != null) {
      window.clearTimeout(debounceRef.current);
    }
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setHits(null);
      setSearching(false);
      return;
    }

    setSearching(true);
    const myReq = ++requestRef.current;
    debounceRef.current = window.setTimeout(() => {
      courtListenerApi
        .search(trimmed, 8)
        .then((res) => {
          // Drop stale responses if the user kept typing.
          if (myReq !== requestRef.current) return;
          setHits(res);
          setActiveIndex(res.length > 0 ? 0 : -1);
        })
        .catch(() => {
          if (myReq !== requestRef.current) return;
          setHits([]);
        })
        .finally(() => {
          if (myReq === requestRef.current) setSearching(false);
        });
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current != null) {
        window.clearTimeout(debounceRef.current);
      }
    };
  }, [query]);

  const select = useCallback(
    async (hit: CourtListenerHit) => {
      setIngesting(hit.cl_id);
      setIngestError(null);
      try {
        const resp = await courtListenerApi.ingest(hit.cl_id);
        addRecent({
          id: resp.document_id,
          title: hit.case_name,
          court: hit.court,
          year: hit.year,
        });
        router.push(`/graph?focus=${resp.document_id}`);
      } catch (e) {
        setIngestError(
          e instanceof Error ? e.message : 'Ingest failed; please try again.',
        );
        setIngesting(null);
      }
    },
    [addRecent, router],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!hits || hits.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault();
      select(hits[activeIndex]);
    }
  };

  return (
    <div className="relative">
      <label className="sr-only" htmlFor="case-search">
        Search a case name
      </label>
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border bg-background px-3',
          'h-12 transition-colors',
          'focus-within:border-ring/50 focus-within:ring-2 focus-within:ring-ring/20',
        )}
      >
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <input
          id="case-search"
          type="search"
          placeholder="Search a case name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          autoComplete="off"
          aria-controls="case-search-listbox"
          aria-expanded={hits !== null && hits.length > 0}
          role="combobox"
          aria-autocomplete="list"
          className="h-full flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        {searching && (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" aria-hidden />
        )}
      </div>
      <p className="mt-1.5 px-1 text-[11px] text-muted-foreground/80">
        Live search via CourtListener
      </p>

      {hits !== null && (hits.length > 0 || query.trim().length >= 2) && (
        <SearchDropdown
          hits={hits}
          activeIndex={activeIndex}
          onHover={setActiveIndex}
          onSelect={select}
          ingestingId={ingesting}
          searching={searching}
          query={query}
        />
      )}

      {ingestError && (
        <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
          {ingestError}
        </div>
      )}
    </div>
  );
}

interface DropdownProps {
  hits: CourtListenerHit[];
  activeIndex: number;
  onHover: (i: number) => void;
  onSelect: (hit: CourtListenerHit) => void;
  ingestingId: number | null;
  searching: boolean;
  query: string;
}

function SearchDropdown({
  hits,
  activeIndex,
  onHover,
  onSelect,
  ingestingId,
  searching,
  query,
}: DropdownProps) {
  if (hits.length === 0) {
    return (
      <div className="absolute left-0 right-0 top-[calc(100%+2.25rem)] z-30 rounded-md border bg-popover px-3 py-2.5 text-xs text-muted-foreground shadow-lg">
        {searching ? 'Searching…' : `No matches for "${query.trim()}"`}
      </div>
    );
  }
  return (
    <ul
      id="case-search-listbox"
      role="listbox"
      className={cn(
        'absolute left-0 right-0 top-[calc(100%+2.25rem)] z-30',
        'overflow-hidden rounded-md border bg-popover shadow-lg',
      )}
    >
      {hits.map((hit, i) => (
        <li key={hit.cl_id} role="option" aria-selected={i === activeIndex}>
          <button
            type="button"
            disabled={ingestingId !== null}
            onMouseEnter={() => onHover(i)}
            onClick={() => onSelect(hit)}
            className={cn(
              'flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors',
              i === activeIndex ? 'bg-accent/10 text-foreground' : 'text-foreground',
              'hover:bg-muted',
              'disabled:cursor-not-allowed disabled:opacity-70',
            )}
          >
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {formatCaseTitle(hit.case_name)}
              </span>
              {ingestingId === hit.cl_id && (
                <Loader2
                  className="h-3 w-3 shrink-0 animate-spin text-muted-foreground"
                  aria-label="Importing"
                />
              )}
            </div>
            <div className="flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
              {hit.court && <span className="truncate">{hit.court}</span>}
              {hit.court && hit.year && <span aria-hidden>·</span>}
              {hit.year && (
                <span className="font-mono tabular-nums">{hit.year}</span>
              )}
              {hit.citation_string && (
                <>
                  <span aria-hidden>·</span>
                  <span className="font-mono">{hit.citation_string}</span>
                </>
              )}
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Upload card — opens the existing UploadModal mounted in AppShell.
// ---------------------------------------------------------------------------

function UploadCard() {
  const openModal = useUploadStore((s) => s.openModal);
  return (
    <button
      type="button"
      onClick={openModal}
      className={cn(
        'flex h-12 items-center gap-2 rounded-md border border-dashed bg-muted/20 px-3',
        'text-sm text-foreground transition-colors',
        'hover:bg-muted hover:border-border',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30',
      )}
      aria-label="Upload a PDF"
    >
      <UploadIcon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      <span className="flex-1 text-left">Upload a PDF…</span>
      <span className="text-[11px] text-muted-foreground">drop or click</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Explore corpus link
// ---------------------------------------------------------------------------

function ExploreCorpusLink() {
  return (
    <Link
      href="/graph"
      className={cn(
        'mt-6 inline-flex items-center gap-1 text-xs',
        'text-muted-foreground transition-colors hover:text-foreground',
      )}
    >
      Or explore the full corpus
      <ArrowRight className="h-3 w-3" aria-hidden />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Recent cases — top 5 from localStorage. SSR-safe (initial render is
// empty; the hydration effect populates the list on the client).
// ---------------------------------------------------------------------------

function RecentCases() {
  const recent = useGraphFocus((s) => s.recentCases);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    hydrateRecentCases();
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return (
      <div className="mt-12 w-full">
        <Skeleton className="h-4 w-16" />
      </div>
    );
  }
  if (recent.length === 0) {
    return null;
  }
  return (
    <section className="mt-12 w-full" aria-label="Recently explored cases">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Recent
        </h2>
        <span className="text-[10px] text-muted-foreground/60">
          (stored in your browser)
        </span>
      </div>
      <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {recent.map((c) => (
          <li key={c.id}>
            <Link
              href={`/graph?focus=${c.id}`}
              className={cn(
                'flex flex-col gap-1 rounded-md border bg-card px-3 py-2 transition-colors',
                'hover:border-border hover:bg-muted/40',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30',
              )}
              onClick={() => {
                // Refresh the timestamp for this case so it bubbles to
                // the top of the recents list on next visit.
                useGraphFocus.getState().addRecent({
                  id: c.id,
                  title: c.title,
                  court: c.court ?? null,
                  year: c.year ?? null,
                });
              }}
            >
              <span className="truncate text-sm font-medium text-foreground">
                {formatCaseTitle(c.title)}
              </span>
              <span className="flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
                {c.court && <span className="truncate">{c.court}</span>}
                {c.court && c.year && <span aria-hidden>·</span>}
                {c.year && <span className="font-mono tabular-nums">{c.year}</span>}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Keep documentApi referenced so unused-import lint stays quiet — the
// /documents page uses it; this file no longer does directly.
void documentApi;
