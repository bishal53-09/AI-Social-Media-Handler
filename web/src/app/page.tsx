"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ONBOARDED_KEY } from "@/lib/onboarding";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    let done = false;
    try {
      done = window.localStorage.getItem(ONBOARDED_KEY) === "1";
    } catch {
      /* storage unavailable: treat as first run */
    }
    router.replace(done ? "/posts" : "/setup");
  }, [router]);
  return <p className="text-xs text-muted-foreground">Loading…</p>;
}
