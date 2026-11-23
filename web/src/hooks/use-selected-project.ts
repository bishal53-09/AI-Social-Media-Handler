"use client";

import { useCallback, useEffect, useState } from "react";
import type { Project } from "@/types/api";

const KEY = "asmh.selectedProject";

function readStored(): string | null {
  try {
    return window.localStorage.getItem(KEY);
  } catch {
    return null; // private mode / blocked storage: the page still works
  }
}

/** Remembers which project a page is showing (a per-browser convenience only). */
export function useSelectedProject(projects: Project[] | undefined) {
  const [chosen, setChosen] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate from localStorage after mount
    setChosen(readStored());
  }, []);

  const select = useCallback((id: string) => {
    setChosen(id);
    try {
      window.localStorage.setItem(KEY, id);
    } catch {
      /* ignore */
    }
  }, []);

  const selected =
    projects?.find((p) => p.id === chosen)?.id ?? (projects && projects[0] ? projects[0].id : null);
  return { selected, select };
}
