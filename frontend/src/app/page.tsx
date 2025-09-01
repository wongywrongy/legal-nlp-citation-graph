'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect directly to the citation graph
    router.replace('/graph');
  }, [router]);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Redirecting to Citation Graph...
        </h1>
        <p className="text-gray-600">
          Loading your legal citation analysis...
        </p>
      </div>
    </div>
  );
}

