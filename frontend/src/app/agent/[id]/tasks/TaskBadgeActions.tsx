import Link from "next/link";

import { badgeVariants } from "@/components/ui/badge";

interface TaskBadgeActionsProps {
  enabled: boolean;
  logsHref: string;
  onToggle: () => void;
}

export function TaskBadgeActions({
  enabled,
  logsHref,
  onToggle,
}: TaskBadgeActionsProps) {
  return (
    <>
      <Link href={logsHref} className={badgeVariants({ variant: "outline" })}>
        Logs
      </Link>
      <button
        type="button"
        className={badgeVariants({ variant: enabled ? "default" : "secondary" })}
        onClick={onToggle}
      >
        {enabled ? "Enabled" : "Disabled"}
      </button>
    </>
  );
}
