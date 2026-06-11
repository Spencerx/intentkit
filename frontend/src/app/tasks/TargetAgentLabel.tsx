"use client";

import Link from "next/link";
import { Bot } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { AgentInfo } from "@/lib/api";
import { getImageUrl } from "@/lib/utils";

/**
 * Renders a task's target agent as avatar + name linking to the agent page.
 * Falls back to the raw id when the agent no longer exists, and to
 * "Team lead decides" when no target agent is pinned.
 */
export function TargetAgentLabel({
  targetAgentId,
  targetAgent,
}: {
  targetAgentId?: string | null;
  targetAgent?: AgentInfo | null;
}) {
  if (!targetAgentId) {
    return <>Team lead decides</>;
  }
  if (!targetAgent) {
    return <span className="font-mono">{targetAgentId}</span>;
  }
  return (
    <Link
      href={`/agent/${targetAgent.slug || targetAgent.id}`}
      className="inline-flex items-center gap-1.5 align-middle hover:underline"
    >
      <Avatar className="h-4 w-4">
        <AvatarImage
          src={getImageUrl(targetAgent.picture) || undefined}
          alt={targetAgent.name || targetAgent.id}
          className="object-cover"
        />
        <AvatarFallback className="bg-background">
          <Bot className="h-3 w-3" />
        </AvatarFallback>
      </Avatar>
      <span>{targetAgent.name || targetAgent.id}</span>
    </Link>
  );
}
