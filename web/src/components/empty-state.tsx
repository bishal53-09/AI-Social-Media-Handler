import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function EmptyState({
  icon: Icon,
  title,
  description,
  badge,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  /** e.g. "Not implemented yet" — makes clear this is a placeholder, not missing data */
  badge?: string;
  children?: React.ReactNode;
}) {
  return (
    <Card className="items-center gap-2 border-dashed px-6 py-10 text-center shadow-none">
      <Icon className="size-8 text-muted-foreground/60" strokeWidth={1.5} />
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">{title}</h2>
        {badge ? <Badge variant="warning">{badge}</Badge> : null}
      </div>
      {description ? <p className="max-w-md text-xs text-muted-foreground">{description}</p> : null}
      {children ? <div className="mt-2">{children}</div> : null}
    </Card>
  );
}
