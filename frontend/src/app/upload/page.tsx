'use client';

/**
 * /upload — preserved as a stable URL but now redirects to
 * /documents?upload=1, which opens the global upload modal. Users land
 * back on the document list (the meaningful destination after uploading)
 * with the upload affordance already open. The Documents page strips the
 * query param after handling so a reload doesn't re-trigger.
 */
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function UploadRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/documents?upload=1');
  }, [router]);

  return (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> Opening upload…
    </div>
  );
}
