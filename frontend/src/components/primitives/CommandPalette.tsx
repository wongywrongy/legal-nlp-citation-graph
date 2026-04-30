'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from '@/components/ui/command';
import { commands } from '@/lib/commands';
import { useInspector } from '@/lib/inspector-store';

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const inspector = useInspector();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const ctx = {
    router,
    toggleInspector: () => inspector.toggle(),
    toggleTheme: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
  };

  const grouped = {
    navigate: commands.filter((c) => c.group === 'navigate'),
    action: commands.filter((c) => c.group === 'action'),
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search…" />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {grouped.navigate.map((c) => (
            <CommandItem
              key={c.id}
              onSelect={() => {
                c.run(ctx);
                setOpen(false);
              }}
            >
              {c.label}
              {c.shortcut && <CommandShortcut>{c.shortcut}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Actions">
          {grouped.action.map((c) => (
            <CommandItem
              key={c.id}
              onSelect={() => {
                c.run(ctx);
                setOpen(false);
              }}
            >
              {c.label}
              {c.shortcut && <CommandShortcut>{c.shortcut}</CommandShortcut>}
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
