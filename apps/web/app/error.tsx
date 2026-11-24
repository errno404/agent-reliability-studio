"use client";

import { ErrorState } from "@/components/ui";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="space-y-3">
      <ErrorState error={error} />
      <button type="button" onClick={reset} className="rounded-md border border-line bg-panel px-3 py-1.5 text-sm hover:bg-panel2">Retry</button>
    </div>
  );
}
