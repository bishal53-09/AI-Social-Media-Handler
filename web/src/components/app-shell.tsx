"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  CalendarDays,
  Clapperboard,
  FolderKanban,
  Image as ImageIcon,
  LayoutDashboard,
  Menu,
  Newspaper,
  Send,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { UpdateBanner } from "@/components/update-banner";
import { useApi } from "@/hooks/use-api";
import { api, API_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/posts", label: "Posts", icon: Newspaper },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/media", label: "Media Library", icon: ImageIcon },
  { href: "/editor", label: "AI Editor", icon: Sparkles },
  { href: "/publishing", label: "Publishing", icon: Send },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function ApiStatus() {
  const { data, error } = useApi(() => api.health(), [], { pollMs: 15000 });
  if (error) {
    return (
      <Badge variant="destructive" title={error.message}>
        API offline
      </Badge>
    );
  }
  if (!data) return <Badge variant="outline">Connecting…</Badge>;
  return (
    <Badge variant={data.status === "ok" ? "success" : "warning"} title={`API ${API_URL}`}>
      API {data.status === "ok" ? "online" : "degraded"} · v{data.version}
    </Badge>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5 px-2" aria-label="Main">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground",
              active && "bg-sidebar-accent text-sidebar-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/posts" className="flex items-center gap-2 px-4 py-3">
      <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
        <Clapperboard className="size-4" />
      </span>
      <span className="text-[13px] leading-tight font-semibold">
        AI Social Media
        <br />
        Handler
      </span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <Brand />
        <NavLinks />
        <p className="mt-auto px-4 py-3 text-[11px] text-muted-foreground">
          Local-first. Your footage and credentials stay on this computer.
        </p>
      </aside>

      {open ? (
        <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true">
          <button
            aria-label="Close menu"
            className="absolute inset-0 bg-black/40"
            onClick={() => setOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 flex w-60 flex-col border-r border-sidebar-border bg-sidebar">
            <div className="flex items-center justify-between pr-2">
              <Brand />
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close menu"
                onClick={() => setOpen(false)}
              >
                <X />
              </Button>
            </div>
            <NavLinks onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open menu"
            onClick={() => setOpen(true)}
          >
            <Menu />
          </Button>
          <div className="ml-auto flex items-center gap-2">
            <ApiStatus />
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-5 md:px-6">
          <UpdateBanner />
          {children}
        </main>
      </div>
    </div>
  );
}
