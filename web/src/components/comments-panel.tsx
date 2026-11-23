"use client";

import { CornerDownRight, EyeOff, Eye, Heart, MessageSquare, Trash2 } from "lucide-react";
import { useState } from "react";
import { whyDisabled } from "@/components/capability-list";
import { ErrorState } from "@/components/error-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { api, ApiError } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";
import type { Comment, PlatformPostDetail } from "@/types/api";

export function CommentsPanel({
  post,
  refreshKey,
  onChanged,
}: {
  post: PlatformPostDetail;
  /** Bump to reload after a sync. */
  refreshKey: number;
  onChanged: () => void;
}) {
  const comments = useApi(() => api.engagement.comments(post.id), [post.id, refreshKey]);
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const cap = post.capabilities;
  const published = post.status === "published";

  async function run(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await fn();
      comments.reload();
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (comments.error) return <ErrorState error={comments.error} onRetry={comments.reload} />;
  if (!comments.data) return <Skeleton className="h-24" />;

  const items = comments.data.items;
  const byParent = new Map<string, Comment[]>();
  for (const c of items) {
    if (c.parent_external_id) {
      byParent.set(c.parent_external_id, [...(byParent.get(c.parent_external_id) ?? []), c]);
    }
  }
  const known = new Set(items.map((c) => c.external_id));
  const top = items.filter((c) => !c.parent_external_id || !known.has(c.parent_external_id));

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed px-4 py-6 text-center text-xs text-muted-foreground">
        <MessageSquare className="mx-auto mb-2 size-6 opacity-60" strokeWidth={1.5} />
        {published
          ? cap.list_comments === "implemented"
            ? "No comments yet. Use “Sync from platform” to check again."
            : "Comments cannot be loaded because this platform's comment listing is not available here (see Capabilities)."
          : "Comments appear after the post is published and synced."}
      </div>
    );
  }

  function renderRow(c: Comment, depth: number): React.ReactNode {
    const replies = byParent.get(c.external_id) ?? [];
    const replyOff = whyDisabled(cap.reply_comment, post.platform_name);
    const likeOff = whyDisabled(cap.like_comment, post.platform_name);
    const hideOff = whyDisabled(cap.hide_comment, post.platform_name);
    const delOff = whyDisabled(cap.delete_comment, post.platform_name);
    return (
      <li key={c.id} className={depth ? "ml-6 border-l pl-3" : ""}>
        <div
          className={`rounded-md border px-3 py-2 ${c.hidden || c.removed_remotely ? "opacity-60" : ""}`}
        >
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span className="font-medium text-foreground">{c.author_name ?? "Unknown"}</span>
            {c.is_own ? <Badge variant="default">you</Badge> : null}
            {c.hidden ? <Badge variant="outline">hidden</Badge> : null}
            {c.removed_remotely ? <Badge variant="warning">deleted on platform</Badge> : null}
            <span>{formatDateTime(c.posted_at)}</span>
            <span className="inline-flex items-center gap-1">
              <Heart className="size-3" /> {c.like_count}
            </span>
            {c.reply_count ? (
              <span>
                {c.reply_count} {c.reply_count === 1 ? "reply" : "replies"}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-[13px] break-words whitespace-pre-wrap">{c.text}</p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            <Button
              size="sm"
              variant="ghost"
              disabled={!!replyOff || busy !== null || c.removed_remotely}
              title={replyOff ?? "Reply on the platform"}
              onClick={() => {
                setReplyTo(replyTo === c.id ? null : c.id);
                setText("");
              }}
            >
              <CornerDownRight /> Reply
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!likeOff || busy !== null}
              title={likeOff ?? undefined}
              onClick={() =>
                run(`like-${c.id}`, () => api.engagement.like(post.id, c.id, !c.liked_by_me))
              }
            >
              <Heart className={c.liked_by_me ? "fill-current" : ""} />{" "}
              {c.liked_by_me ? "Unlike" : "Like"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!hideOff || busy !== null}
              title={hideOff ?? undefined}
              onClick={() =>
                run(`hide-${c.id}`, () => api.engagement.hide(post.id, c.id, !c.hidden))
              }
            >
              {c.hidden ? <Eye /> : <EyeOff />} {c.hidden ? "Unhide" : "Hide"}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!!delOff || busy !== null}
              title={delOff ?? "Delete on the platform (cannot be undone)"}
              onClick={() => {
                if (window.confirm("Delete this comment on the platform? This cannot be undone.")) {
                  void run(`del-${c.id}`, () => api.engagement.remove(post.id, c.id));
                }
              }}
            >
              <Trash2 /> Delete
            </Button>
          </div>
          {replyTo === c.id ? (
            <form
              className="mt-2 flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void run(`reply-${c.id}`, async () => {
                  await api.engagement.reply(post.id, c.id, text);
                  setReplyTo(null);
                  setText("");
                });
              }}
            >
              <Input
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={`Reply on ${post.platform_name}…`}
                maxLength={2000}
                autoFocus
                aria-label="Reply text"
              />
              <Button type="submit" size="sm" disabled={!text.trim() || busy !== null}>
                Send reply
              </Button>
            </form>
          ) : null}
        </div>
        {replies.length ? (
          <ul className="mt-1.5 space-y-1.5">{replies.map((r) => renderRow(r, depth + 1))}</ul>
        ) : null}
      </li>
    );
  }

  return (
    <div className="space-y-2">
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <p className="text-[11px] text-muted-foreground">
        {comments.data.total} comment{comments.data.total === 1 ? "" : "s"} as last synced. Actions
        are sent to {post.platform_name} immediately.
      </p>
      <ul className="space-y-1.5">{top.map((c) => renderRow(c, 0))}</ul>
    </div>
  );
}
