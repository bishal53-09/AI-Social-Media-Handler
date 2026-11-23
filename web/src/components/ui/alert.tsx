import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border px-3 py-2.5 text-[13px]", {
  variants: {
    variant: {
      default: "bg-card",
      destructive: "border-destructive/40 bg-destructive/8 text-destructive",
      warning: "border-warning/40 bg-warning/10",
    },
  },
  defaultVariants: { variant: "default" },
});

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return <div role="alert" className={cn(alertVariants({ variant }), className)} {...props} />;
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("mb-0.5 font-semibold", className)} {...props} />;
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("text-xs opacity-90", className)} {...props} />;
}

export { Alert, AlertTitle, AlertDescription };
