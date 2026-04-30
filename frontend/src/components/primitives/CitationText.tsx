'use client';

import { useState } from 'react';
import { Copy, CopyCheck } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface CitationTextProps {
  text: string;
  normalizedKey?: string | null;
  className?: string;
}

export function CitationText({ text, normalizedKey, className }: CitationTextProps) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore — clipboard may be unavailable in iframes
    }
  };

  return (
    <TooltipProvider delayDuration={400}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onCopy}
            className={cn(
              'group inline-flex max-w-full items-center gap-1.5 rounded font-mono text-[12px] leading-snug text-foreground hover:text-accent',
              className,
            )}
          >
            <span className="truncate">{text}</span>
            {copied ? (
              <CopyCheck className="h-3 w-3 shrink-0 opacity-100" />
            ) : (
              <Copy className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-60" />
            )}
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <div className="font-mono text-[11px]">{text}</div>
          {normalizedKey && (
            <div className="mt-0.5 font-mono text-[10px] opacity-60">{normalizedKey}</div>
          )}
          <div className="mt-1 text-[10px] opacity-60">{copied ? 'Copied!' : 'Click to copy'}</div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
