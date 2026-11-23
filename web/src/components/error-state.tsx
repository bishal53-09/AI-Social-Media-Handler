import { AlertTriangle, RefreshCw } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { ApiError } from "@/lib/api";

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const offline = error.status === 0;
  return (
    <Alert variant="destructive">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div className="min-w-0 flex-1">
          <AlertTitle>{offline ? "Backend not reachable" : "Something went wrong"}</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </div>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw /> Retry
          </Button>
        ) : null}
      </div>
    </Alert>
  );
}
