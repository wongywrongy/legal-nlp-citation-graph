'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { commands } from '@/lib/commands';
import { useInspector } from '@/lib/inspector-store';

const PREFIX_TIMEOUT_MS = 1200;

/**
 * Two-character chord shortcuts (`g g`, `g d`, …) plus single-key actions
 * (`i`, `t`, `?`). Skipped when an input/textarea is focused.
 */
export function KeyboardShortcuts() {
  const [helpOpen, setHelpOpen] = useState(false);
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const inspector = useInspector();
  const prefixRef = useRef<{ key: string; expires: number } | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      // ?-key opens help, regardless of prefix.
      if (e.key === '?') {
        e.preventDefault();
        setHelpOpen(true);
        return;
      }

      const ctx = {
        router,
        toggleInspector: () => inspector.toggle(),
        toggleTheme: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
      };

      // Two-key chord ("g d", "g g", ...).
      if (prefixRef.current && Date.now() < prefixRef.current.expires) {
        const combo = `${prefixRef.current.key} ${e.key}`;
        prefixRef.current = null;
        const match = commands.find((c) => c.shortcut === combo);
        if (match) {
          e.preventDefault();
          match.run(ctx);
          return;
        }
      } else if (e.key === 'g') {
        prefixRef.current = { key: 'g', expires: Date.now() + PREFIX_TIMEOUT_MS };
        return;
      }

      // Single-key actions.
      const single = commands.find((c) => c.shortcut === e.key);
      if (single) {
        e.preventDefault();
        single.run(ctx);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [router, theme, setTheme, inspector]);

  return (
    <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Press the keys in sequence (e.g. <span className="font-mono">g d</span>).</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-1 gap-1 text-[13px]">
          {commands
            .filter((c) => c.shortcut)
            .map((c) => (
              <div key={c.id} className="flex items-center justify-between rounded-sm px-2 py-1.5 hover:bg-muted">
                <span>{c.label}</span>
                <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-2xs">{c.shortcut}</kbd>
              </div>
            ))}
          <div className="flex items-center justify-between rounded-sm px-2 py-1.5">
            <span>Open command palette</span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-2xs">⌘K</kbd>
          </div>
          <div className="flex items-center justify-between rounded-sm px-2 py-1.5">
            <span>Show this help</span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-2xs">?</kbd>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
