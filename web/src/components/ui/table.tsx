import * as React from "react";
import { cn } from "@/lib/utils";

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom text-[13px]", className)} {...props} />
    </div>
  );
}
const TableHeader = (p: React.ComponentProps<"thead">) => (
  <thead {...p} className={cn("[&_tr]:border-b", p.className)} />
);
const TableBody = (p: React.ComponentProps<"tbody">) => (
  <tbody {...p} className={cn("[&_tr:last-child]:border-0", p.className)} />
);
const TableRow = (p: React.ComponentProps<"tr">) => (
  <tr {...p} className={cn("border-b transition-colors hover:bg-muted/50", p.className)} />
);
const TableHead = (p: React.ComponentProps<"th">) => (
  <th
    {...p}
    className={cn(
      "h-8 px-3 text-left align-middle text-[11px] font-medium tracking-wide text-muted-foreground uppercase whitespace-nowrap",
      p.className,
    )}
  />
);
const TableCell = (p: React.ComponentProps<"td">) => (
  <td {...p} className={cn("px-3 py-1.5 align-middle", p.className)} />
);

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell };
