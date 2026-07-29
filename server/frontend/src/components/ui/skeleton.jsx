import { cn } from "@/lib/utils"

// Shimmering placeholder for content that is still loading. Prefer this over
// ad-hoc spinners for list/card/table loading so the layout doesn't jump.
function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

export { Skeleton }
