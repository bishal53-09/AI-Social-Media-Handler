"use client";

import { ArrowUpCircle, Copy, X } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { UpdateStatus } from "@/types/api";

/** How often the dashboard asks the API; the API itself fetches from git at most every 15 min. */
const POLL_MS = 10 * 60 * 1000;

export function UpdateInstructions({ status }: { status: UpdateStatus }) {
  const [copied, setCopied] = useState(false);
  const blocked = status.ahead > 0;
  return (
    <>
      <p>
        {status.message} You are on <code className="font-mono">{status.local_commit}</code>, the
        latest is <code className="font-mono">{status.remote_commit}</code>.
      </p>
      {blocked ? null : (
        <p className="mt-1.5 flex flex-wrap items-center gap-1.5">
          Stop the app (Ctrl+C), then run
          <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-foreground">
            {status.command}
          </code>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-1.5"
            onClick={() => {
              navigator.clipboard?.writeText(status.command).then(
                () => setCopied(true),
                () => setCopied(false),
              );
            }}
          >
            <Copy /> {copied ? "Copied" : "Copy"}
          </Button>
          and start it again with <code className="font-mono">make dev</code>.
        </p>
      )}
    </>
  );
}

/** Shows a banner when the local checkout is behind its upstream. Never applies the update. */
export function UpdateBanner() {
  const { data } = useApi(() => api.updateStatus(), [], { pollMs: POLL_MS });
  const [dismissed, setDismissed] = useState<string | null>(null);
  if (!data?.update_available || dismissed === data.remote_commit) return null;
  return (
    <Alert variant="warning" className="mb-4 flex gap-2.5 pr-10">
      <ArrowUpCircle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
      <div className="min-w-0">
        <AlertTitle>A new version is available</AlertTitle>
        <AlertDescription>
          <UpdateInstructions status={data} />
        </AlertDescription>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-1.5 right-1.5 size-7"
        aria-label="Dismiss until the next version"
        onClick={() => setDismissed(data.remote_commit)}
      >
        <X />
      </Button>
    </Alert>
  );
}
