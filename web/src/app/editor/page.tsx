"use client";

import { CheckCircle2, Circle, Sparkles } from "lucide-react";
import { EmptyState } from "@/components/empty-state";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

function Row({ ok, label, hint }: { ok: boolean; label: string; hint?: string }) {
  return (
    <li className="flex items-start gap-2">
      {ok ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" />
      ) : (
        <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground/50" />
      )}
      <div>
        <div>{label}</div>
        {hint ? <div className="text-[11px] text-muted-foreground">{hint}</div> : null}
      </div>
    </li>
  );
}

export default function EditorPage() {
  const settings = useApi(() => api.settings(), []);
  const s = settings.data;
  return (
    <>
      <PageHeader
        title="AI Editor"
        description="Claude acts as an editing director: it returns validated plans, and deterministic software executes them."
      />
      <EmptyState
        icon={Sparkles}
        badge="Not implemented in the dashboard yet"
        title="AI review interface is planned (Phase 5)"
        description="Footage analysis already exists as a command-line workflow. Highlight selection, edit plans and caption generation exist as validated backend modules; the interface to review them here is not built yet."
      />
      {settings.error ? (
        <div className="mt-4">
          <ErrorState error={settings.error} onRetry={settings.reload} />
        </div>
      ) : null}
      {s ? (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>AI readiness</CardTitle>
              <CardDescription>
                Provider: {s.ai_provider} · model: {s.ai_model}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-xs">
                <Row
                  ok={s.ai_key_configured}
                  label="API key configured"
                  hint="Set ANTHROPIC_API_KEY in .env (the key never reaches the browser)."
                />
                <Row
                  ok={s.ai_frame_upload_allowed}
                  label="Sending sampled frames is allowed"
                  hint="Off by default. Enable media_transmission.allow_frames in config/ai.yaml, or pass --allow-frames to the CLI for one run."
                />
                <Row ok={s.ffmpeg_available} label="FFmpeg available for frame sampling" />
              </ul>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Try it from the command line</CardTitle>
              <CardDescription>
                Sends a few downscaled frames of one clip, only with your consent.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="overflow-x-auto rounded-md bg-muted p-2.5 font-mono text-[11px]">
                python -m app.cli analyze ~/Content/MyProject media/raw/clip.mp4 --allow-frames
              </pre>
              <p className="mt-2 text-[11px] text-muted-foreground">
                Results are saved to <code className="font-mono">data/analysis/</code> in the
                project. Whole videos are never uploaded.{" "}
                <Badge variant="outline">Unverified against the live API in this milestone</Badge>
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </>
  );
}
