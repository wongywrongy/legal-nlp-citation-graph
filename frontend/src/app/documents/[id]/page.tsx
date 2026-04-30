'use client';

/**
 * /documents/[id] — preserved as a stable URL for sharing/back-compat, but
 * the document detail experience now lives in the inspector panel on the
 * graph page. This route redirects to /graph?focus={id}, which:
 *   • opens the inspector for that document
 *   • pulses the matching node so the user's eye lands on it
 *
 * The inspector exposes everything this page used to: case header, full
 * citation list with confidence breakdown, and a "View full text" Sheet
 * for the extracted opinion body. Keeping users on /graph preserves the
 * graph + inspector loop that is the product's core flow.
 */
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

export default function DocumentRedirect() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id as string;

  useEffect(() => {
    if (!id) return;
    router.replace(`/graph?focus=${id}`);
  }, [id, router]);

  return (
    <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> Opening case…
    </div>
  );
}
