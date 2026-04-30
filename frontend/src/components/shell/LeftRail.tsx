'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Network, FileText, Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/graph', label: 'Graph', icon: Network },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/upload', label: 'Upload', icon: Upload },
];

export function LeftRail() {
  const pathname = usePathname();
  return (
    <aside className="hidden w-[220px] shrink-0 border-r border-border bg-background lg:flex lg:flex-col">
      <div className="flex h-12 items-center border-b border-border px-4">
        <span className="font-mono text-[13px] font-semibold tracking-tight">citegraph</span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {navItems.map((item) => {
          const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] transition-colors',
                active ? 'bg-muted text-foreground' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
              )}
            >
              <item.icon className="h-3.5 w-3.5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto border-t border-border p-3 text-2xs text-muted-foreground">
        <div>Press <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono">?</kbd> for shortcuts</div>
      </div>
    </aside>
  );
}
