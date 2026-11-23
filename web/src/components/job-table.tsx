import Link from "next/link";
import { Progress } from "@/components/ui/progress";
import { JobStatusBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime } from "@/lib/utils";
import type { Job } from "@/types/api";

export function JobTable({ jobs }: { jobs: Job[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Job</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
          <TableHead className="w-40">Progress</TableHead>
          <TableHead>Created</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => (
          <TableRow key={job.id}>
            <TableCell>
              <Link
                href={`/jobs/${job.id}`}
                className="font-mono text-xs text-primary hover:underline"
              >
                {job.id}
              </Link>
            </TableCell>
            <TableCell>{job.type}</TableCell>
            <TableCell>
              <JobStatusBadge status={job.status} />
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <Progress value={job.progress * 100} />
                <span className="w-9 text-right text-xs text-muted-foreground tabular-nums">
                  {Math.round(job.progress * 100)}%
                </span>
              </div>
              {job.current_stage && job.status === "running" ? (
                <div className="text-[11px] text-muted-foreground">{job.current_stage}</div>
              ) : null}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {formatDateTime(job.created_at)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export const hasActiveJob = (jobs: Job[] | undefined) =>
  !!jobs?.some((j) => j.status === "queued" || j.status === "running");
