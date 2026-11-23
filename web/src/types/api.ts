// Mirrors the FastAPI response schemas (app/schemas/*). Keep in sync when the API changes.

export interface Health {
  status: "ok" | "degraded";
  version: string;
  database: string;
  ffmpeg: boolean;
  ffprobe: boolean;
  python: string;
}

export interface Project {
  id: string;
  name: string;
  path: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectSettings {
  default_camera: string | null;
  color_profile: string | null;
  platforms: string[];
}

export interface ProjectDetail extends Project {
  exists_on_disk: boolean;
  settings: ProjectSettings | null;
  day_count: number;
  media_count: number;
}

export interface ProjectList {
  items: Project[];
  total: number;
}

export interface ProjectCreate {
  name: string;
  path?: string;
  description?: string;
  default_camera?: string;
}

export interface DaySummary {
  date: string;
  clip_count: number;
}

export interface DayList {
  items: DaySummary[];
}

export interface Clip {
  id: string;
  title: string;
  source: { file: string; type: string; camera?: string | null };
  processing: { status: string; thumbnail?: string | null; proxy?: string | null };
  outputs: unknown[];
  posts: string[];
}

export interface DayRead {
  date: string;
  project_id: string;
  notes: string | null;
  clips: Clip[];
}

export interface ProbeData {
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  duration?: number | null;
  video_codec?: string | null;
  audio_codec?: string | null;
  is_equirectangular?: boolean;
  projection_source?: string | null;
  warnings?: string[];
}

export interface MediaAsset {
  id: string;
  project_id: string;
  relative_path: string;
  kind: "video" | "image";
  stage: string;
  day: string | null;
  size_bytes: number;
  sha256: string | null;
  media_type: string;
  camera: string | null;
  probe: ProbeData | null;
  probe_error: string | null;
  thumbnail_path: string | null;
  proxy_path: string | null;
  missing: boolean;
  created_at: string;
  updated_at: string;
}

export interface MediaList {
  items: MediaAsset[];
  total: number;
  limit: number;
  offset: number;
}

export interface ScanResult {
  new: number;
  changed: number;
  unchanged: number;
  missing: number;
  skipped: number;
  probed: number;
  probe_failed: number;
  days_written: number;
  warnings: string[];
}

export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  project_id: string | null;
  type: string;
  status: JobStatus;
  progress: number;
  current_stage: string | null;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface JobEvent {
  id: string;
  stage: string | null;
  event: string;
  message: string | null;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface JobDetail extends Job {
  events: JobEvent[];
}

export interface JobList {
  items: Job[];
  total: number;
}

export interface JobCreate {
  type: "media.scan" | "pipeline.process";
  project_id: string;
  params?: Record<string, unknown>;
}

export interface Post {
  id: string;
  project_id: string;
  platform: string;
  variant: string | null;
  output_file: string;
  caption: string | null;
  hashtags: string[];
  scheduled_at: string | null;
  status: string;
  external_post_id: string | null;
  external_url: string | null;
  published_at: string | null;
  created_at: string;
}

export interface PostList {
  items: Post[];
  total: number;
}

export interface PlatformInfo {
  name: string;
  enabled: boolean;
  api: string | null;
  credentials_configured: boolean;
  publishing_implemented: boolean;
  capabilities: Partial<Record<CapabilityName, CapabilityState>>;
  engagement_notes: string;
}

export interface AppSettings {
  app_env: string;
  host: string;
  port: number;
  localhost_only: boolean;
  media_root: string;
  database: string;
  require_publish_approval: boolean;
  ai_provider: string;
  ai_model: string;
  ai_key_configured: boolean;
  ai_frame_upload_allowed: boolean;
  ffmpeg_available: boolean;
  ffprobe_available: boolean;
  pipeline_stages: { name: string; implemented: boolean }[];
  platforms: PlatformInfo[];
  export_presets: string[];
}

// ---- Posts, engagement and analytics ---------------------------------------------------

export type CapabilityState = "implemented" | "planned" | "unavailable";
export type CapabilityName =
  | "publish"
  | "analytics"
  | "list_comments"
  | "reply_comment"
  | "like_comment"
  | "hide_comment"
  | "delete_comment"
  | "like_post";

export type Metrics = Record<string, number>;

export interface PlatformPostSummary {
  id: string;
  platform: string;
  platform_name: string;
  variant: string | null;
  status: string;
  external_post_id: string | null;
  external_url: string | null;
  published_at: string | null;
  scheduled_at: string | null;
  error: string | null;
  metrics: Metrics;
  metrics_collected_at: string | null;
  comment_count: number;
}

export interface PostAttempt {
  attempt: number;
  started_at: string;
  finished_at: string | null;
  outcome: string;
  error: string | null;
}

export interface MetricSnapshot {
  collected_at: string;
  metrics: Metrics;
}

export interface EngagementAction {
  id: string;
  comment_external_id: string | null;
  action: string;
  outcome: string;
  detail: string | null;
  error: string | null;
  created_at: string;
}

export interface PlatformPostDetail extends PlatformPostSummary {
  caption: string | null;
  hashtags: string[];
  approved_by: string | null;
  approved_at: string | null;
  attempts: PostAttempt[];
  capabilities: Partial<Record<CapabilityName, CapabilityState>>;
  engagement_notes: string;
  snapshots: MetricSnapshot[];
  actions: EngagementAction[];
}

export interface ContentPostSummary {
  id: string;
  project_id: string;
  title: string;
  output_file: string | null;
  caption: string | null;
  hashtags: string[];
  created_at: string;
  platform_posts: PlatformPostSummary[];
  totals: Metrics;
  comment_total: number;
}

export interface ContentPostDetail extends Omit<ContentPostSummary, "platform_posts"> {
  platform_posts: PlatformPostDetail[];
}

export interface ContentPostList {
  items: ContentPostSummary[];
  total: number;
}

export interface ContentPostCreate {
  project_id: string;
  title: string;
  output_file: string;
  caption?: string;
  hashtags: string[];
  platforms: { platform: string; variant?: string }[];
}

export interface Comment {
  id: string;
  post_id: string;
  external_id: string;
  parent_external_id: string | null;
  author_name: string | null;
  text: string;
  like_count: number;
  reply_count: number;
  posted_at: string | null;
  fetched_at: string;
  is_own: boolean;
  hidden: boolean;
  liked_by_me: boolean;
  removed_remotely: boolean;
}

export interface CommentList {
  items: Comment[];
  total: number;
}

export interface SyncPart {
  status: "ok" | "unsupported" | "error" | "skipped";
  count: number;
  message: string | null;
}

export interface SyncReport {
  post_id: string;
  comments: SyncPart;
  analytics: SyncPart;
  synced_at: string;
}

export interface AnalyticsOverview {
  published_posts: number;
  posts_with_data: number;
  totals: Metrics;
  by_platform: {
    platform: string;
    platform_name: string;
    published_posts: number;
    posts_with_data: number;
    totals: Metrics;
  }[];
  top_posts: {
    content_post_id: string | null;
    title: string;
    platform: string;
    platform_post_id: string;
    external_url: string | null;
    metrics: Metrics;
  }[];
  last_collected_at: string | null;
}
