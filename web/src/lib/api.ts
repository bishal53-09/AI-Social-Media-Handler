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
  MediaList,
  PostList,
  Project,
  ProjectCreate,
  ProjectDetail,
  ProjectList,
  ScanResult,
  SyncReport,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
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
  projects: {
    list: () => request<ProjectList>("/projects"),
    get: (id: string) => request<ProjectDetail>(`/projects/${encodeURIComponent(id)}`),
    create: (body: ProjectCreate) => post<Project>("/projects", body),
    days: (id: string) => request<DayList>(`/projects/${encodeURIComponent(id)}/days`),
    day: (id: string, date: string) =>
      request<DayRead>(`/projects/${encodeURIComponent(id)}/days/${date}`),
    media: (id: string, params: { stage?: string; kind?: string; limit?: number } = {}) => {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
      const qs = q.toString();
      return request<MediaList>(`/projects/${encodeURIComponent(id)}/media${qs ? `?${qs}` : ""}`);
    },
    scan: (id: string, probe = true) =>
      post<ScanResult>(`/projects/${encodeURIComponent(id)}/media/scan`, { probe }),
  },
  jobs: {
    list: (params: { project_id?: string; status?: string; limit?: number } = {}) => {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
      const qs = q.toString();
      return request<JobList>(`/jobs${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<JobDetail>(`/jobs/${encodeURIComponent(id)}`),
    create: (body: JobCreate) => post<Job>("/jobs", body),
    cancel: (id: string) => post<Job>(`/jobs/${encodeURIComponent(id)}/cancel`),
  },
  posts: {
    list: (params: { project_id?: string } = {}) => {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
      const qs = q.toString();
      return request<PostList>(`/posts${qs ? `?${qs}` : ""}`);
    },
  },
  contentPosts: {
    list: (params: { project_id?: string; limit?: number } = {}) => {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) if (v !== undefined) q.set(k, String(v));
      const qs = q.toString();
      return request<ContentPostList>(`/content-posts${qs ? `?${qs}` : ""}`);
    },
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
