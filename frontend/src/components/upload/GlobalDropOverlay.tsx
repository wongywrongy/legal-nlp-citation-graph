'use client';

/**
 * Page-wide drag-and-drop affordance.
 *
 * Listens to window-level dragenter/dragover/dragleave/drop events. When
 * a user drags a file over any part of the app, an overlay slides in
 * indicating the entire page is a drop target. Dropping a file:
 *   • opens the upload modal
 *   • passes the file(s) through the same validation pipeline as the
 *     in-modal dropzone
 *
 * We only treat drags whose payload contains files (dataTransfer.types
 * includes 'Files') — internal drag operations (text selection, etc.)
 * don't trigger the overlay.
 */
import { useEffect, useState } from 'react';
import { Upload } from 'lucide-react';
import { useUploadStore } from '@/lib/upload-store';
import { useFileHandler } from './UploadModal';
import { cn } from '@/lib/utils';

export function GlobalDropOverlay() {
  const [over, setOver] = useState(false);
  const openModal = useUploadStore((s) => s.openModal);
  const handleFiles = useFileHandler();

  useEffect(() => {
    let depth = 0;

    const containsFiles = (e: DragEvent) =>
      Array.from(e.dataTransfer?.types ?? []).includes('Files');

    const onEnter = (e: DragEvent) => {
      if (!containsFiles(e)) return;
      depth += 1;
      setOver(true);
    };
    const onOver = (e: DragEvent) => {
      if (!containsFiles(e)) return;
      e.preventDefault(); // allow drop
    };
    const onLeave = () => {
      depth = Math.max(0, depth - 1);
      if (depth === 0) setOver(false);
    };
    const onDrop = (e: DragEvent) => {
      if (!containsFiles(e)) return;
      e.preventDefault();
      depth = 0;
      setOver(false);
      const files = e.dataTransfer?.files;
      if (files && files.length) {
        openModal();
        handleFiles(Array.from(files));
      }
    };

    window.addEventListener('dragenter', onEnter);
    window.addEventListener('dragover', onOver);
    window.addEventListener('dragleave', onLeave);
    window.addEventListener('drop', onDrop);
    return () => {
      window.removeEventListener('dragenter', onEnter);
      window.removeEventListener('dragover', onOver);
      window.removeEventListener('dragleave', onLeave);
      window.removeEventListener('drop', onDrop);
    };
  }, [openModal, handleFiles]);

  if (!over) return null;

  return (
    <div
      className={cn(
        'pointer-events-none fixed inset-0 z-[60] flex items-center justify-center',
        'border-4 border-accent/60 bg-accent/5',
        'animate-in fade-in-0 duration-150',
      )}
      aria-hidden
    >
      <div className="rounded-md border border-accent/50 bg-background/90 px-5 py-4 text-center shadow-lg backdrop-blur">
        <Upload className="mx-auto h-6 w-6 text-accent" aria-hidden />
        <p className="mt-2 text-sm font-medium">Drop to upload</p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          PDF only · 50 MB max
        </p>
      </div>
    </div>
  );
}
