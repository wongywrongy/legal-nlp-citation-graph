'use client';

/**
 * TopBar — breadcrumbs + global semantic search + theme/inspector controls.
 *
 * The search field is a type-ahead combobox (Spotlight / Linear pattern):
 *   • Debounced 300ms
 *   • Up to 6 results, scrollable past that
 *   • Keyboard nav: ArrowUp/Down move highlight, Enter selects, Esc dismisses
 *   • Clicking outside or navigating to a new route dismisses
 *   • On select: pulse the matching node — graph-store animates the camera
 *     and CitationGraph's NodeHighlightReducer pulses the node for 1.5s
 *
 * On non-/graph routes, selecting a result navigates to /graph?q=<query>
 * which seeds the graph page's pulse via its existing useEffect.
 */
import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  ChevronRight,
  Command,
  Loader2,
  Moon,
  PanelRightOpen,
  Search,
  Sun,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useInspector } from '@/lib/inspector-store';
import { useGraphFocus } from '@/lib/graph-store';
import { searchApi, SearchHit } from '@/lib/api';
import { cn } from '@/lib/utils';
import { formatCaseTitle } from '@/lib/format';

const DEBOUNCE_MS = 300;
const MIN_QUERY_LENGTH = 2;

function useBreadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split('/').filter(Boolean);
  if (segments.length === 0) return [{ label: 'Dashboard', href: '/' }];
  return [
    { label: 'Dashboard', href: '/' },
    ...segments.map((seg, i) => ({
      label: seg.startsWith('[')
        ? seg.replace(/[\[\]]/g, '')
        : seg.replace(/^[a-z]/, (c) => c.toUpperCase()),
      href: '/' + segments.slice(0, i + 1).join('/'),
    })),
  ];
}

export function TopBar() {
  const { theme, setTheme } = useTheme();
  const inspector = useInspector();
  const breadcrumbs = useBreadcrumbs();
  const router = useRouter();
  const pathname = usePathname();
  const pulseGraph = useGraphFocus((s) => s.pulse);

  return (
    <header className="flex h-12 items-center gap-3 border-b border-border bg-background px-4">
      <nav className="flex min-w-0 shrink items-center gap-1.5 overflow-hidden text-[13px]">
        {breadcrumbs.map((b, i) => (
          <span key={b.href} className="flex items-center gap-1.5">
            {i > 0 && (
              <ChevronRight
                className="h-3 w-3 text-muted-foreground"
                aria-hidden
              />
            )}
            {i === breadcrumbs.length - 1 ? (
              <span className="truncate text-foreground">{b.label}</span>
            ) : (
              <Link
                href={b.href}
                className="truncate text-muted-foreground transition-colors hover:text-foreground"
              >
                {b.label}
              </Link>
            )}
          </span>
        ))}
      </nav>

      <SearchCombobox
        pathname={pathname}
        router={router}
        pulseGraph={pulseGraph}
      />

      <div className="ml-auto flex shrink-0 items-center gap-1.5 md:ml-0">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const ev = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
            window.dispatchEvent(ev);
          }}
          className="hidden gap-1.5 sm:inline-flex"
        >
          <Command className="h-3 w-3" />
          <span className="font-mono text-2xs">⌘K</span>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => inspector.toggle()}
          aria-label="Toggle inspector"
          className="transition-colors"
        >
          <PanelRightOpen className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          aria-label="Toggle theme"
          className="transition-colors"
        >
          {theme === 'dark' ? (
            <Sun className="h-3.5 w-3.5" />
          ) : (
            <Moon className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Search combobox
// ---------------------------------------------------------------------------

interface ComboboxProps {
  pathname: string;
  router: ReturnType<typeof useRouter>;
  pulseGraph: (id: string) => void;
}

function SearchCombobox({ pathname, router, pulseGraph }: ComboboxProps) {
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const debounceRef = useRef<number | null>(null);
  const requestIdRef = useRef(0);
  const setSearchPulse = useGraphFocus((s) => s.setSearchPulse);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    const trimmed = query.trim();
    if (trimmed.length < MIN_QUERY_LENGTH) {
      setHits(null);
      setLoading(false);
      setError(null);
      // Clear the live graph pulse when the query is empty.
      setSearchPulse([]);
      return;
    }

    setLoading(true);
    debounceRef.current = window.setTimeout(async () => {
      const myRequest = ++requestIdRef.current;
      try {
        const res = await searchApi.search(trimmed, 10, 0.3);
        if (myRequest !== requestIdRef.current) return;
        setHits(res.hits);
        setActiveIndex(0);
        setError(null);
        // Live preview: tint matching nodes on the graph behind the
        // dropdown so the canvas reacts to the query in real time.
        setSearchPulse(res.hits.map((h) => h.doc_id));
      } catch (e) {
        if (myRequest !== requestIdRef.current) return;
        setHits([]);
        setError(e instanceof Error ? e.message : 'Search unavailable');
        setSearchPulse([]);
      } finally {
        if (myRequest === requestIdRef.current) setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [query, setSearchPulse]);

  // Clear the live pulse on unmount so a stale tint doesn't linger.
  useEffect(() => {
    return () => setSearchPulse([]);
  }, [setSearchPulse]);

  // Click outside dismisses
  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    window.addEventListener('pointerdown', onPointer);
    return () => window.removeEventListener('pointerdown', onPointer);
  }, [open]);

  // Route change dismisses
  useEffect(() => {
    setOpen(false);
    setQuery('');
    setHits(null);
  }, [pathname]);

  const dismiss = () => {
    setOpen(false);
    setActiveIndex(0);
  };

  const select = (hit: SearchHit) => {
    if (pathname !== '/graph') {
      router.push(`/graph?q=${encodeURIComponent(query.trim())}&focus=${hit.doc_id}`);
    } else {
      pulseGraph(hit.doc_id);
    }
    dismiss();
    setQuery('');
    setHits(null);
    inputRef.current?.blur();
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!hits || hits.length === 0) return;
    select(hits[Math.min(activeIndex, hits.length - 1)]);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      setOpen(true);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      if (query) {
        setQuery('');
        setHits(null);
      } else {
        dismiss();
        inputRef.current?.blur();
      }
      return;
    }
    if (!hits || hits.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(hits.length - 1, i + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      select(hits[Math.min(activeIndex, hits.length - 1)]);
    }
  };

  const showDropdown =
    open && query.trim().length >= MIN_QUERY_LENGTH && (hits !== null || loading);

  return (
    <div
      ref={containerRef}
      className="relative ml-auto hidden min-w-[200px] max-w-[460px] flex-1 md:block"
    >
      <form
        role="search"
        onSubmit={onSubmit}
        className={cn(
          'flex items-center gap-2 rounded-md border bg-muted/40 px-2 transition-colors',
          'border-border',
          open && query && 'border-accent/50 bg-background',
        )}
      >
        <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (query.trim().length >= MIN_QUERY_LENGTH) setOpen(true);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search cases…"
          autoComplete="off"
          aria-label="Semantic search"
          aria-controls="topbar-search-listbox"
          aria-autocomplete="list"
          aria-expanded={showDropdown}
          role="combobox"
          className="h-8 min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
        />
        {loading ? (
          <Loader2
            className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground"
            aria-hidden
          />
        ) : query ? (
          <button
            type="button"
            onClick={() => {
              setQuery('');
              setHits(null);
              setOpen(false);
              inputRef.current?.focus();
            }}
            aria-label="Clear search"
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            <span className="text-[11px]">Esc</span>
          </button>
        ) : null}
      </form>

      {showDropdown && (
        <SearchDropdown
          hits={hits}
          loading={loading}
          error={error}
          activeIndex={activeIndex}
          onHover={setActiveIndex}
          onSelect={select}
        />
      )}
    </div>
  );
}

interface DropdownProps {
  hits: SearchHit[] | null;
  loading: boolean;
  error: string | null;
  activeIndex: number;
  onHover: (i: number) => void;
  onSelect: (hit: SearchHit) => void;
}

function SearchDropdown({
  hits,
  loading,
  error,
  activeIndex,
  onHover,
  onSelect,
}: DropdownProps) {
  if (loading && (!hits || hits.length === 0)) {
    return (
      <DropdownShell>
        <div className="px-3 py-2.5 text-xs text-muted-foreground">
          Searching…
        </div>
      </DropdownShell>
    );
  }
  if (error) {
    return (
      <DropdownShell>
        <div className="px-3 py-2.5 text-xs text-destructive">{error}</div>
      </DropdownShell>
    );
  }
  if (!hits || hits.length === 0) {
    return (
      <DropdownShell>
        <div className="px-3 py-2.5 text-xs text-muted-foreground">
          No matching cases — try broader terms.
        </div>
      </DropdownShell>
    );
  }

  return (
    <DropdownShell>
      <ul
        id="topbar-search-listbox"
        role="listbox"
        className="flex max-h-[320px] flex-col overflow-y-auto py-1"
      >
        {hits.map((hit, i) => (
          <li key={hit.doc_id} role="option" aria-selected={i === activeIndex}>
            <button
              type="button"
              onPointerEnter={() => onHover(i)}
              onClick={() => onSelect(hit)}
              className={cn(
                'flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors',
                'focus-visible:outline-none',
                i === activeIndex
                  ? 'bg-accent/10 text-foreground'
                  : 'text-foreground hover:bg-muted',
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-sm font-medium">{formatCaseTitle(hit.title)}</span>
                {hit.scored_by === 'crossencoder' && (
                  <span className="shrink-0 rounded-sm bg-emerald-500/10 px-1 py-0 font-mono text-[9px] uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
                    Reranked
                  </span>
                )}
                {hit.scored_by === 'lexical' && (
                  <span className="shrink-0 rounded-sm bg-amber-500/10 px-1 py-0 font-mono text-[9px] uppercase tracking-wide text-amber-700 dark:text-amber-400">
                    Title match
                  </span>
                )}
              </div>
              <div className="flex items-center gap-x-1.5 text-[11px] text-muted-foreground">
                {hit.court && <span className="truncate">{hit.court}</span>}
                {hit.court && hit.year && <span aria-hidden>·</span>}
                {hit.year && <span className="font-mono tabular-nums">{hit.year}</span>}
              </div>
              {hit.snippet && (
                <p className="line-clamp-2 text-xs leading-snug text-muted-foreground/90">
                  {hit.snippet}
                </p>
              )}
            </button>
          </li>
        ))}
      </ul>
      <div className="border-t border-border bg-muted/30 px-3 py-1.5 text-[10px] text-muted-foreground">
        <span className="font-mono">↑↓</span> navigate ·
        <span className="ml-1.5 font-mono">Enter</span> select ·
        <span className="ml-1.5 font-mono">Esc</span> dismiss
      </div>
    </DropdownShell>
  );
}

function DropdownShell({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={cn(
        'absolute left-0 right-0 top-[calc(100%+4px)] z-40 overflow-hidden',
        'rounded-md border border-border bg-popover shadow-lg',
        'animate-in fade-in-0 slide-in-from-top-1 duration-150',
      )}
    >
      {children}
    </div>
  );
}
