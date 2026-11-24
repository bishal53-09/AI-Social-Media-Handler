"use client";

import { Check, CircleAlert, Download, LogIn, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ErrorState } from "@/components/error-state";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { ONBOARDED_KEY } from "@/lib/onboarding";
import type { SetupAccount, SetupStatus } from "@/types/api";

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="grid size-6 place-items-center rounded-full bg-primary text-xs text-primary-foreground">
            {n}
          </span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function AccountRow({
  a,
  onChanged,
  browserReady,
}: {
  a: SetupAccount;
  onChanged: () => void;
  browserReady: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const connect = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await api.startLogin(a.name);
      setOpened(true);
      setMsg(
        `A window for ${a.title} is opening on this computer. Sign in as you normally would, then close that window and press “I've signed in”.`,
      );
    } catch (e) {
      setMsg(
        e instanceof Error
          ? e.message
          : "Could not open the sign-in window. Make sure the connection browser is installed (step 1).",
      );
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const { signed_in } = await api.checkSession(a.name);
      setMsg(
        signed_in
          ? `You're signed in to ${a.title}.`
          : `You're not signed in to ${a.title} yet. Press “Sign in” and try again.`,
      );
      if (signed_in) setOpened(false);
      onChanged();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not check. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="border-b py-3 last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{a.title}</span>
        {a.connected ? (
          <Badge variant="success">Sign-in saved</Badge>
        ) : (
          <Badge variant="outline">Not connected</Badge>
        )}
        {!a.can_publish ? <Badge variant="outline">Posting not available yet</Badge> : null}
        <div className="ml-auto flex gap-2">
          <Button size="sm" disabled={busy || !browserReady} onClick={connect}>
            <LogIn />
            {a.connected ? "Sign in again" : "Sign in"}
          </Button>
          {opened || a.connected ? (
            <Button size="sm" variant="outline" disabled={busy} onClick={check}>
              {opened ? "I've signed in" : "Check it still works"}
            </Button>
          ) : null}
        </div>
      </div>
      {msg ? <p className="mt-1.5 text-xs text-muted-foreground">{msg}</p> : null}
    </div>
  );
}

function Checklist({ s, reload }: { s: SetupStatus; reload: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const installing = s.browser_install === "running";

  const install = async () => {
    setMsg(null);
    try {
      await api.installBrowser();
      reload();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not start the download.");
    }
  };

  return (
    <ul className="space-y-2">
      {s.items.map((i) => (
        <li key={i.id} className="flex items-start gap-2 text-sm">
          {i.ok ? (
            <Check className="mt-0.5 size-4 shrink-0 text-success" aria-label="ready" />
          ) : (
            <CircleAlert
              className={`mt-0.5 size-4 shrink-0 ${i.required ? "text-destructive" : "text-warning"}`}
              aria-label="needs attention"
            />
          )}
          <div className="min-w-0">
            <p className="font-medium">
              {i.title}
              {!i.required && !i.ok ? (
                <span className="ml-1.5 text-xs font-normal">(optional)</span>
              ) : null}
            </p>
            {!i.ok ? <p className="text-xs text-muted-foreground">{i.help}</p> : null}
            {i.id === "browser" && !i.ok ? (
              <>
                <Button size="sm" className="mt-1.5" disabled={installing} onClick={install}>
                  <Download />
                  {installing ? "Downloading… this can take a few minutes" : "Install it now"}
                </Button>
                {s.browser_install === "failed" ? (
                  <p className="mt-1 text-xs text-destructive">{s.browser_install_message}</p>
                ) : null}
                {msg ? <p className="mt-1 text-xs text-destructive">{msg}</p> : null}
              </>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function SetupPage() {
  const {
    data: s,
    error,
    reload,
  } = useApi(() => api.setupStatus(), [], {
    pollMs: (d) => (d?.browser_install === "running" ? 3000 : null),
  });

  const finish = () => {
    try {
      window.localStorage.setItem(ONBOARDED_KEY, "1");
    } catch {
      /* ignore: the guide will simply show again */
    }
  };

  return (
    <>
      <PageHeader
        title="Welcome — let's get you set up"
        description="Three short steps. No technical knowledge needed. You can come back to this page any time from the menu."
        actions={
          <Button variant="outline" size="sm" onClick={reload}>
            <RefreshCw />
            Re-check
          </Button>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : !s ? (
        <Skeleton className="h-64" />
      ) : (
        <div className="grid max-w-3xl gap-4">
          <Step n={1} title="Make sure this computer is ready">
            <Checklist s={s} reload={reload} />
          </Step>
          <Step n={2} title="Connect your accounts">
            <CardDescription className="mb-2">
              Press “Sign in” and a normal browser window opens on this computer. Log in the way you
              usually do (including any verification code), then close the window. Your password is
              typed into the real site, never into this app, and the sign-in stays on this computer.
            </CardDescription>
            {s.items.find((i) => i.id === "browser")?.ok === false ? (
              <p className="mb-2 text-xs text-warning">
                Install the connection browser in step 1 first.
              </p>
            ) : null}
            {s.accounts.map((a) => (
              <AccountRow
                key={a.name}
                a={a}
                onChanged={reload}
                browserReady={s.items.find((i) => i.id === "browser")?.ok !== false}
              />
            ))}
            <p className="mt-2 text-[11px] text-muted-foreground">
              Posting through these sites is experimental and they may change without notice. If
              something stops working, press “Sign in again”. The app always asks for your approval
              before anything is published.
            </p>
          </Step>
          <Step n={3} title="Start using the app">
            <p className="mb-3 text-sm text-muted-foreground">
              {s.ready
                ? s.any_account_connected
                  ? "Everything is ready."
                  : "You can connect accounts later from this page; you can already organise your videos."
                : "Something required is still missing (step 1). You can still look around."}
            </p>
            <Link href="/posts" onClick={finish}>
              <Button>Go to my posts</Button>
            </Link>
          </Step>
        </div>
      )}
    </>
  );
}
