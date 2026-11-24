import type {
  AnalyticsOverview,
  AppSettings,
  Comment,
  CommentList,
  ContentPostCreate,
  ContentPostDetail,
  ContentPostList,
  DayList,
  DayRead,
  Health,
  Job,
  JobCreate,
  JobDetail,
  JobList,
  MediaAsset,
  MediaList,
  PostList,
  Project,
  ProjectCreate,
  ProjectDetail,
  ProjectList,
  ScanResult,
  SyncReport,
  UpdateStatus,
} from "@/types/api";

/**
 * Base URL of the local FastAPI backend. Only a public, non-secret URL is used here;
 * the backend holds every credential.
 */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Build a query string, skipping empty values. */
export function qs(params: object): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params) as [string, unknown][]) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** Paging, search and sorting accepted by every list endpoint. */
export interface ListParams {
  q?: string;
  sort?: string;
  order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: {
        ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_URL}. Start it with: python -m app.cli serve`,
      0,
      "network_error",
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    let code: string | undefined;
    let details: Record<string, unknown> | undefined;
    try {
      const body = await response.json();
      if (body?.error) {
        message = body.error.message ?? message;
        code = body.error.code;
        details = body.error.details;
      } else if (Array.isArray(body?.detail)) {
        // FastAPI request-validation error
        message = body.detail
          .map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.slice(1).join(".")}: ${d.msg}`)
          .join("; ");
        code = "validation_error";
      }
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, response.status, code, details);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),
  settings: () => request<AppSettings>("/settings"),
  updateStatus: (refresh = false) =>
    request<UpdateStatus>(`/system/update${refresh ? "?refresh=true" : ""}`),
  projects: {
    list: (params: ListParams = {}) =>
      request<ProjectList>(`/projects${qs({ limit: 200, ...params })}`),
    get: (id: string) => request<ProjectDetail>(`/projects/${encodeURIComponent(id)}`),
    create: (body: ProjectCreate) => post<Project>("/projects", body),
    days: (id: string) => request<DayList>(`/projects/${encodeURIComponent(id)}/days`),
    day: (id: string, date: string) =>
      request<DayRead>(`/projects/${encodeURIComponent(id)}/days/${date}`),
    media: (
      id: string,
      params: ListParams & {
        stage?: string;
        kind?: string;
        media_type?: string;
        day_from?: string;
        day_to?: string;
        postable?: boolean;
      } = {},
    ) => request<MediaList>(`/projects/${encodeURIComponent(id)}/media${qs(params)}`),
    uploadMedia: (id: string, files: File[]) => {
      const form = new FormData();
      for (const f of files) form.append("files", f);
      return request<MediaAsset[]>(`/projects/${encodeURIComponent(id)}/media/upload`, {
        method: "POST",
        body: form,
      });
    },
    renameMedia: (id: string, assetId: string, displayName: string | null) =>
      request<MediaAsset>(
        `/projects/${encodeURIComponent(id)}/media/${encodeURIComponent(assetId)}`,
        { method: "PATCH", body: JSON.stringify({ display_name: displayName }) },
      ),
    /** Streams the file for in-app preview. `auto` uses the proxy when one exists. */
    fileUrl: (id: string, assetId: string, variant: "auto" | "original" | "proxy" = "auto") =>
      `${API_URL}/api/v1/projects/${encodeURIComponent(id)}/media/${encodeURIComponent(assetId)}/file${variant === "auto" ? "" : `?variant=${variant}`}`,
    thumbnailUrl: (id: string, assetId: string) =>
      `${API_URL}/api/v1/projects/${encodeURIComponent(id)}/media/${encodeURIComponent(assetId)}/thumbnail`,
    scan: (id: string, probe = true) =>
      post<ScanResult>(`/projects/${encodeURIComponent(id)}/media/scan`, { probe }),
  },
  jobs: {
    list: (
      params: ListParams & {
        project_id?: string;
        status?: string;
        type?: string;
        created_from?: string;
        created_to?: string;
      } = {},
    ) => request<JobList>(`/jobs${qs(params)}`),
    get: (id: string) => request<JobDetail>(`/jobs/${encodeURIComponent(id)}`),
    create: (body: JobCreate) => post<Job>("/jobs", body),
    cancel: (id: string) => post<Job>(`/jobs/${encodeURIComponent(id)}/cancel`),
  },
  posts: {
    list: (params: ListParams & { project_id?: string; status?: string; platform?: string } = {}) =>
      request<PostList>(`/posts${qs(params)}`),
  },
  contentPosts: {
    list: (
      params: ListParams & {
        project_id?: string;
        status?: string;
        platform?: string;
        created_from?: string;
        created_to?: string;
      } = {},
    ) => request<ContentPostList>(`/content-posts${qs(params)}`),
    get: (id: string) => request<ContentPostDetail>(`/content-posts/${encodeURIComponent(id)}`),
    create: (body: ContentPostCreate) => post<ContentPostDetail>("/content-posts", body),
  },
  engagement: {
    comments: (postId: string) =>
      request<CommentList>(`/posts/${encodeURIComponent(postId)}/comments?limit=500`),
    sync: (postId: string) => post<SyncReport>(`/posts/${encodeURIComponent(postId)}/sync`),
    reply: (postId: string, commentId: string, text: string) =>
      post<Comment>(
        `/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}/reply`,
        { text },
      ),
    like: (postId: string, commentId: string, like: boolean) =>
      post<Comment>(
        `/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}/like`,
        { like },
      ),
    hide: (postId: string, commentId: string, hidden: boolean) =>
      post<Comment>(
        `/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}/hide`,
        { hidden },
      ),
    remove: (postId: string, commentId: string) =>
      request<void>(
        `/posts/${encodeURIComponent(postId)}/comments/${encodeURIComponent(commentId)}`,
        { method: "DELETE" },
      ),
    likePost: (postId: string, like: boolean) =>
      post<void>(`/posts/${encodeURIComponent(postId)}/like`, { like }),
  },
  analytics: {
    overview: (project_id?: string) =>
      request<AnalyticsOverview>(
        `/analytics/overview${project_id ? `?project_id=${encodeURIComponent(project_id)}` : ""}`,
      ),
  },
};
