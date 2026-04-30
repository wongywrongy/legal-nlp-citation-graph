'use client';

/**
 * Upload modal — a Dialog hosting the dropzone + recent activity.
 *
 * Drives the upload queue store. Drag-and-drop is handled here AND at the
 * page level (Documents page listens to window dragover/drop for a full-
 * page highlight) — this dropzone is the explicit affordance.
 *
 * Validation:
 *   • PDF only (extension OR mime type)
 *   • Max 50 MB per file
 *   • Invalid files surface inline errors and are not enqueued
 *
 * Lifecycle:
 *   1. User selects files → addFiles() validates → enqueues with status 'queued'
 *   2. UploadOrchestrator kicks off every queued item exactly once (tracked
 *      via a ref Set so effect re-runs don't double-start). Uploads run
 *      in parallel — backend processing is gated by ARQ's max_jobs anyway.
 *   3. POST /v1/ingest → server returns document_id; status → 'processing'
 *   4. Poll /v1/documents/{id}/status every 3s → status → 'ready' on completed
 *   5. Toast notification fires; entry stays for ~5s as feedback then auto-clears
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  FileText,
  Loader2,
  Upload as UploadIcon,
  X,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/components/ui/use-toast';
import { useUploadStore, UploadItem } from '@/lib/upload-store';
import { useGraphFocus } from '@/lib/graph-store';
import { documentApi, ingestApi } from '@/lib/api';
import { cn } from '@/lib/utils';

const MAX_BYTES = 50 * 1024 * 1024; // 50 MB
const POLL_MS = 3000;
const READY_LINGER_MS = 5000;

export function UploadModal() {
  const open = useUploadStore((s) => s.modalOpen);
  const closeModal = useUploadStore((s) => s.closeModal);
  const items = useUploadStore((s) => s.items);

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? null : closeModal())}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Upload PDF</DialogTitle>
          <DialogDescription>
            Drop one or many PDF opinions. Citation extraction starts as soon
            as each file is received.
          </DialogDescription>
        </DialogHeader>
        <Dropzone />
        {items.length > 0 && (
          <ScrollArea className="max-h-[260px] pr-1">
            <ul className="flex flex-col gap-1.5">
              {items.map((it) => (
                <li key={it.localId}>
                  <UploadRow item={it} />
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
        <UploadOrchestrator />
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Dropzone — the affordance inside the modal
// ---------------------------------------------------------------------------

function Dropzone() {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const handleFiles = useFileHandler();
  const [drag, setDrag] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        if (e.dataTransfer?.files?.length) {
          handleFiles(Array.from(e.dataTransfer.files));
        }
      }}
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed py-8 text-center transition-colors',
        drag
          ? 'border-accent bg-accent/5'
          : 'border-border bg-muted/30 hover:bg-muted/50',
      )}
    >
      <UploadIcon className="h-7 w-7 text-muted-foreground" aria-hidden />
      <p className="text-sm">Drop a PDF here</p>
      <p className="text-xs text-muted-foreground">
        or
      </p>
      <Button
        size="sm"
        variant="accent"
        type="button"
        onClick={() => inputRef.current?.click()}
      >
        Choose file
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        multiple
        onChange={(e) => {
          if (e.target.files) handleFiles(Array.from(e.target.files));
          if (inputRef.current) inputRef.current.value = '';
        }}
        className="hidden"
      />
      <p className="mt-1 text-[11px] text-muted-foreground/70">
        PDF only · 50 MB max per file
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// File acceptance + validation
// ---------------------------------------------------------------------------

export function useFileHandler() {
  const add = useUploadStore((s) => s.add);
  const { toast } = useToast();

  return useCallback(
    (files: File[]) => {
      const accepted: File[] = [];
      const rejected: { file: File; reason: string }[] = [];
      for (const file of files) {
        const isPdf =
          file.type === 'application/pdf' ||
          file.name.toLowerCase().endsWith('.pdf');
        if (!isPdf) {
          rejected.push({ file, reason: 'Only PDF files are accepted' });
          continue;
        }
        if (file.size > MAX_BYTES) {
          rejected.push({ file, reason: 'File exceeds 50 MB' });
          continue;
        }
        accepted.push(file);
      }

      for (const { file, reason } of rejected) {
        toast({
          title: `${file.name} rejected`,
          description: reason,
          variant: 'destructive',
        });
      }
      for (const file of accepted) {
        const localId = `${Date.now()}-${file.name}-${Math.random().toString(36).slice(2, 8)}`;
        add({
          localId,
          fileName: file.name,
          fileSize: file.size,
          status: 'queued',
          progress: 0,
          startedAt: Date.now(),
        });
        // Stash the File object on a window-level map so the orchestrator
        // can pick it up — zustand state stays JSON-serialisable.
        QUEUED_FILES.set(localId, file);
      }
    },
    [add, toast],
  );
}

const QUEUED_FILES = new Map<string, File>();

// ---------------------------------------------------------------------------
// Orchestrator — drives uploads + polling. Runs whenever the modal mounts.
// ---------------------------------------------------------------------------

function UploadOrchestrator() {
  const items = useUploadStore((s) => s.items);
  const patch = useUploadStore((s) => s.patch);
  const remove = useUploadStore((s) => s.remove);
  const spawnNode = useGraphFocus((s) => s.spawn);
  const { toast } = useToast();

  // Track uploads we've already kicked off so the effect re-running (every
  // store change) doesn't restart an in-flight upload — and so we don't
  // need a cancellation flag, which previously could swallow the .then()
  // callback that transitions 'uploading' → 'processing'.
  const startedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    for (const item of items) {
      if (item.status !== 'queued') continue;
      if (startedRef.current.has(item.localId)) continue;
      startedRef.current.add(item.localId);

      const file = QUEUED_FILES.get(item.localId);
      if (!file) {
        patch(item.localId, {
          status: 'failed',
          error: 'File not found in queue',
        });
        continue;
      }

      patch(item.localId, { status: 'uploading', progress: 0 });
      ingestApi
        .upload(file, (loaded, total) => {
          const pct = total > 0 ? Math.round((loaded / total) * 100) : 0;
          patch(item.localId, { progress: pct });
        })
        .then((res) => {
          QUEUED_FILES.delete(item.localId);
          patch(item.localId, {
            status: 'processing',
            documentId: res.document_id,
            progress: 100,
          });
        })
        .catch((e) => {
          QUEUED_FILES.delete(item.localId);
          patch(item.localId, {
            status: 'failed',
            error: e instanceof Error ? e.message : 'Upload failed',
          });
        });
    }
  }, [items, patch]);

  // Poll any items in 'processing' state.
  useEffect(() => {
    const processing = items.filter(
      (i) => i.status === 'processing' && i.documentId,
    );
    if (processing.length === 0) return;
    let cancelled = false;
    const tick = async () => {
      for (const item of processing) {
        if (cancelled) return;
        try {
          const status = await documentApi.getDocumentStatus(item.documentId!);
          if (status.status === 'completed') {
            // Try to upgrade the displayed title — the worker may have
            // extracted a real case name.
            try {
              const { document } = await documentApi.getDocument(item.documentId!);
              patch(item.localId, {
                status: 'ready',
                resolvedTitle: document.title,
              });
              // Spawn animation: when the user navigates to the graph,
              // this node grows in from 0 instead of just appearing.
              spawnNode(document.id);
              toast({
                title: 'Case ready',
                description: document.title,
                action: (
                  <Link
                    href={`/graph?focus=${document.id}`}
                    className="text-xs font-medium text-accent hover:underline"
                  >
                    View in graph
                  </Link>
                ) as React.ReactElement,
              });
            } catch {
              patch(item.localId, { status: 'ready' });
              if (item.documentId) spawnNode(item.documentId);
              toast({ title: 'Case ready' });
            }
            // Remove from queue after a brief linger so the user sees the
            // "Ready" state before it disappears.
            setTimeout(() => remove(item.localId), READY_LINGER_MS);
          } else if (status.status === 'failed') {
            patch(item.localId, {
              status: 'failed',
              error: 'Processing failed',
            });
          }
        } catch {
          // Ignore transient poll errors; next tick will retry.
        }
      }
    };
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [items, patch, remove, toast]);

  return null;
}

// ---------------------------------------------------------------------------
// Per-row UI inside the modal
// ---------------------------------------------------------------------------

function UploadRow({ item }: { item: UploadItem }) {
  const remove = useUploadStore((s) => s.remove);

  return (
    <div className="flex items-start gap-3 rounded-md border border-border bg-card px-2.5 py-2">
      <StatusGlyph status={item.status} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm">
            {item.resolvedTitle || item.fileName}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {formatBytes(item.fileSize)}
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
          <StatusBadge status={item.status} />
          <span>{statusHint(item)}</span>
        </div>
        {item.status === 'uploading' && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-accent transition-all duration-150"
              style={{ width: `${item.progress}%` }}
            />
          </div>
        )}
        {item.status === 'failed' && item.error && (
          <p className="mt-1 text-[11px] text-destructive">{item.error}</p>
        )}
        {item.status === 'ready' && item.documentId && (
          <Link
            href={`/graph?focus=${item.documentId}`}
            className="mt-1 inline-flex items-center gap-1 text-[11px] font-medium text-accent hover:underline"
          >
            View in graph <ExternalLink className="h-2.5 w-2.5" />
          </Link>
        )}
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6"
        onClick={() => remove(item.localId)}
        aria-label="Dismiss row"
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
}

function StatusGlyph({ status }: { status: UploadItem['status'] }) {
  if (status === 'ready')
    return (
      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" aria-hidden />
    );
  if (status === 'failed')
    return (
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
    );
  if (status === 'uploading' || status === 'processing')
    return (
      <Loader2
        className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-amber-500"
        aria-hidden
      />
    );
  return <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />;
}

export function StatusBadge({ status }: { status: UploadItem['status'] }) {
  const map: Record<UploadItem['status'], { label: string; cls: string }> = {
    queued: {
      label: 'Queued',
      cls: 'bg-muted text-muted-foreground',
    },
    uploading: {
      label: 'Uploading',
      cls: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
    },
    processing: {
      label: 'Processing',
      cls: 'bg-amber-500/10 text-amber-700 dark:text-amber-400 animate-pulse',
    },
    ready: {
      label: 'Ready',
      cls: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
    },
    failed: {
      label: 'Failed',
      cls: 'bg-destructive/10 text-destructive',
    },
  };
  const meta = map[status];
  return (
    <span
      className={cn(
        'rounded-sm px-1.5 py-0 font-mono text-[10px] uppercase tracking-wide',
        meta.cls,
      )}
    >
      {meta.label}
    </span>
  );
}

function statusHint(item: UploadItem): string {
  if (item.status === 'queued') return 'waiting…';
  if (item.status === 'uploading') return `${item.progress}%`;
  if (item.status === 'processing') return 'extracting citations';
  if (item.status === 'ready') return 'all set';
  return '';
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
