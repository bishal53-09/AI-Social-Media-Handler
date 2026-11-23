import * as React from "react";
import { cn } from "@/lib/utils";

const field =
  "w-full min-w-0 rounded-md border border-input bg-card px-2.5 text-[13px] shadow-xs transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return <input type={type} className={cn(field, "h-8", className)} {...props} />;
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(field, "min-h-16 py-1.5", className)} {...props} />;
}

export { Input, Textarea };
