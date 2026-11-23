"use client";

import { Check, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { UpdateInstructions } from "@/components/update-banner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api, API_URL } from "@/lib/api";
import type { UpdateStatus } from "@/types/api";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b py-1.5 text-xs last:border-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right break-all">{children}</dd>
    </div>
  );
}

const Yes = ({ ok }: { ok: boolean }) =>
  ok ? (
    <Check className="inline size-4 text-success" aria-label="yes" />
  ) : (
    <X className="inline size-4 text-destructive" aria-label="no" />
  );

function UpdatesCard() {
  const initial = useApi(() => api.updateStatus(), []);
  const [fresh, setFresh] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState<string | null>(null);
  const u = fresh ?? initial.data;

  const checkNow = async () => {
    setChecking(true);
    setCheckError(null);
    try {
      setFresh(await api.updateStatus(true));
    } catch (e) {
      setCheckError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Updates</CardTitle>
        <CardDescription>
          Compares this install with its git remote. Nothing is installed automatically.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!u ? (
          initial.error ? (
            <p className="text-xs text-destructive">{initial.error.message}</p>
          ) : (
            <Skeleton className="h-16" />
          )
        ) : (
          <>
            <dl>
              <Row label="Status">
                {!u.supported ? (
                  <Badge variant="outline">not available</Badge>
                ) : u.update_available ? (
                  <Badge variant="warning">update available</Badge>
                ) : u.upstream ? (
                  <Badge variant="success">up to date</Badge>
                ) : (
                  <Badge variant="outline">no upstream</Badge>
                )}
              </Row>
              {u.branch ? (
                <Row label="Branch">
                  <span className="font-mono">
                    {u.branch}
                    {u.upstream ? ` → ${u.upstream}` : ""}
                  </span>
                </Row>
              ) : null}
              <Row label="Installed version">
                <span className="font-mono">{u.local_commit ?? "unknown"}</span>
              </Row>
              {u.remote_commit ? (
                <Row label="Latest version">
                  <span className="font-mono">{u.remote_commit}</span>
                </Row>
              ) : null}
              <Row label="Checked">{new Date(u.checked_at).toLocaleString()}</Row>
            </dl>
            <div className="mt-2 text-[11px] text-muted-foreground">
              {u.update_available ? <UpdateInstructions status={u} /> : u.message}
            </div>
          </>
        )}
        {checkError ? <p className="mt-2 text-[11px] text-destructive">{checkError}</p> : null}
        <Button variant="outline" size="sm" className="mt-3" onClick={checkNow} disabled={checking}>
          <RefreshCw className={checking ? "animate-spin" : undefined} />
          {checking ? "Checking…" : "Check now"}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { data: s, error, reload } = useApi(() => api.settings(), []);
  return (
    <>
      <PageHeader
        title="Settings"
        description="Read-only view of the effective configuration. Edit config/*.yaml and .env, then restart the API."
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !s ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {!s.localhost_only ? (
            <Alert variant="warning" className="lg:col-span-2">
              <AlertTitle>The API is not bound to localhost</AlertTitle>
              <AlertDescription>
                Anyone on your network can reach it. Set APP_HOST=127.0.0.1 in .env unless you know
                what you are doing.
              </AlertDescription>
            </Alert>
          ) : null}
          <Card>
            <CardHeader>
              <CardTitle>Server</CardTitle>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="Environment">{s.app_env}</Row>
                <Row label="Bind address">
                  {s.host}:{s.port}{" "}
                  {s.localhost_only ? (
                    <Badge variant="success">localhost only</Badge>
                  ) : (
                    <Badge variant="warning">exposed</Badge>
                  )}
                </Row>
                <Row label="Dashboard → API URL">
                  <span className="font-mono">{API_URL}</span>
                </Row>
                <Row label="Database">
                  <span className="font-mono">{s.database}</span>
                </Row>
                <Row label="Projects folder">
                  <span className="font-mono">{s.media_root}</span>
                </Row>
              </dl>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Media tools</CardTitle>
              <CardDescription>Required for probing, thumbnails and proxies.</CardDescription>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="FFmpeg">
                  <Yes ok={s.ffmpeg_available} />
                </Row>
                <Row label="ffprobe">
                  <Yes ok={s.ffprobe_available} />
                </Row>
              </dl>
              {!s.ffmpeg_available || !s.ffprobe_available ? (
                <p className="mt-2 text-[11px] text-warning">
                  Install FFmpeg (macOS: <code className="font-mono">brew install ffmpeg</code>,
                  Debian/Ubuntu: <code className="font-mono">sudo apt install ffmpeg</code>).
                </p>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>AI</CardTitle>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="Provider">{s.ai_provider}</Row>
                <Row label="Model">
                  <span className="font-mono">{s.ai_model}</span>
                </Row>
                <Row label="API key configured">
                  <Yes ok={s.ai_key_configured} />
                </Row>
                <Row label="Sending video frames allowed">
                  <Yes ok={s.ai_frame_upload_allowed} />
                </Row>
              </dl>
              <p className="mt-2 text-[11px] text-muted-foreground">
                Secret values are never shown or sent to the browser.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Publishing</CardTitle>
            </CardHeader>
            <CardContent>
              <dl>
                <Row label="Human approval required">
                  <Yes ok={s.require_publish_approval} />
                </Row>
                {s.platforms.map((p) => (
                  <Row key={p.name} label={p.name}>
                    {p.enabled ? "enabled" : "disabled"} · credentials{" "}
                    {p.credentials_configured ? "set" : "missing"} ·{" "}
                    {p.publishing_implemented ? "can publish" : "cannot publish yet"}
                  </Row>
                ))}
              </dl>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Pipeline stages</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {s.pipeline_stages.map((st) => (
                <Badge key={st.name} variant={st.implemented ? "success" : "outline"}>
                  {st.name}
                  {st.implemented ? "" : " (planned)"}
                </Badge>
              ))}
            </CardContent>
          </Card>
          <UpdatesCard />
          <Card>
            <CardHeader>
              <CardTitle>Export presets</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-1.5">
              {s.export_presets.map((p) => (
                <Badge key={p} variant="secondary">
                  {p}
                </Badge>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
