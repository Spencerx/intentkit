"use client";

import { useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleX,
  History,
  Loader2,
  Play,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toast } from "@/hooks/use-toast";
import { AutonomousExecution, autonomousApi } from "@/lib/api";
import type { ChatMessage, ChatMessageToolCall } from "@/types/chat";

// Keep polling for a short while after a manual trigger so the new run
// appears even before its row reports a running status.
const POLL_AFTER_RUN_MS = 15000;
const POLL_INTERVAL_MS = 4000;

function formatDuration(execution: AutonomousExecution): string {
  if (!execution.started_at) return "-";
  const start = new Date(execution.started_at).getTime();
  const end = execution.finished_at
    ? new Date(execution.finished_at).getTime()
    : Date.now();
  const seconds = Math.max(0, (end - start) / 1000);
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${Math.round(seconds % 60)}s`;
}

function formatCredits(cost: AutonomousExecution["credit_cost"]): string | null {
  if (cost === null || cost === undefined) return null;
  const value = Number(cost);
  if (Number.isNaN(value)) return String(cost);
  return value.toFixed(4).replace(/\.?0+$/, "") || "0";
}

function StatusBadge({ status }: { status: AutonomousExecution["status"] }) {
  if (status === "running") {
    return (
      <Badge
        variant="secondary"
        className="bg-blue-100 text-blue-800 hover:bg-blue-100"
      >
        <Loader2 className="mr-1 h-3 w-3 animate-spin" />
        Running
      </Badge>
    );
  }
  if (status === "error") {
    return (
      <Badge variant="destructive">
        <CircleX className="mr-1 h-3 w-3" />
        Error
      </Badge>
    );
  }
  return (
    <Badge
      variant="secondary"
      className="bg-green-100 text-green-800 hover:bg-green-100"
    >
      <CircleCheck className="mr-1 h-3 w-3" />
      Success
    </Badge>
  );
}

function ToolCallItem({ call }: { call: ChatMessageToolCall }) {
  const params = JSON.stringify(call.parameters);
  const detail = call.success ? call.response : call.error_message;
  return (
    <div className="rounded border border-border/60 bg-background/60 p-2">
      <div className="flex items-center gap-2 text-xs font-medium">
        {call.success ? (
          <CircleCheck className="h-3 w-3 text-green-600" />
        ) : (
          <CircleX className="h-3 w-3 text-destructive" />
        )}
        <span className="font-mono">{call.name}</span>
      </div>
      {params && params !== "{}" && (
        <div className="mt-1 font-mono text-xs text-muted-foreground break-all">
          {params.length > 300 ? `${params.slice(0, 300)}…` : params}
        </div>
      )}
      {detail && (
        <div className="mt-1 text-xs whitespace-pre-wrap break-words">
          {detail.length > 500 ? `${detail.slice(0, 500)}…` : detail}
        </div>
      )}
    </div>
  );
}

function MessageItem({ message }: { message: ChatMessage }) {
  const time = new Date(message.created_at).toLocaleTimeString();

  if (message.author_type === "trigger") {
    return (
      <div>
        <div className="mb-1 text-xs font-semibold text-muted-foreground">
          Prompt · {time}
        </div>
        <div className="rounded-md bg-muted/50 p-3 font-mono text-xs whitespace-pre-wrap">
          {message.message}
        </div>
      </div>
    );
  }

  if (message.author_type === "tool") {
    return (
      <div>
        <div className="mb-1 text-xs font-semibold text-muted-foreground">
          Tool Calls · {time}
        </div>
        <div className="space-y-2">
          {(message.tool_calls ?? []).map((call, i) => (
            <ToolCallItem key={call.id ?? i} call={call} />
          ))}
        </div>
      </div>
    );
  }

  if (message.author_type === "thinking") {
    return (
      <details>
        <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">
          Thinking · {time}
        </summary>
        <div className="mt-1 rounded-md bg-muted/30 p-3 text-xs whitespace-pre-wrap text-muted-foreground">
          {message.message}
        </div>
      </details>
    );
  }

  if (message.author_type === "system") {
    return (
      <div>
        <div className="mb-1 text-xs font-semibold text-destructive">
          System · {time}
        </div>
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive whitespace-pre-wrap">
          {message.message}
        </div>
      </div>
    );
  }

  // Agent reply (and any other output type).
  return (
    <div>
      <div className="mb-1 text-xs font-semibold text-muted-foreground">
        Agent · {time}
      </div>
      <div className="rounded-md border border-border/60 p-3 text-sm whitespace-pre-wrap">
        {message.message}
      </div>
    </div>
  );
}

function ExecutionLogView({
  taskId,
  executionId,
}: {
  taskId: string;
  executionId: string;
}) {
  const {
    data: messages = [],
    isLoading,
    error,
  } = useQuery({
    queryKey: ["execution-log", taskId, executionId],
    queryFn: () => autonomousApi.getExecutionMessages(taskId, executionId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading log…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-3 text-sm text-destructive">
        {error instanceof Error ? error.message : "Failed to load log."}
      </div>
    );
  }
  if (messages.length === 0) {
    return (
      <div className="p-3 text-sm text-muted-foreground">
        No log messages recorded for this run.
      </div>
    );
  }
  return (
    <div className="space-y-3 p-3">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  );
}

function ExecutionRow({
  taskId,
  execution,
  expanded,
  onToggle,
}: {
  taskId: string;
  execution: AutonomousExecution;
  expanded: boolean;
  onToggle: () => void;
}) {
  const credits = formatCredits(execution.credit_cost);
  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 p-3 text-left hover:bg-muted/40"
      >
        {expanded ? (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={execution.status} />
            {execution.trigger === "manual" && (
              <Badge variant="outline">Manual</Badge>
            )}
            <span className="text-sm">
              {execution.started_at
                ? new Date(execution.started_at).toLocaleString()
                : "-"}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatDuration(execution)}
            </span>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
            <span>
              Tokens: {execution.input_tokens} in / {execution.output_tokens}{" "}
              out
            </span>
            {credits && <span>Credits: {credits}</span>}
            <span>Messages: {execution.message_count}</span>
            {execution.triggered_by && (
              <span className="font-mono">by {execution.triggered_by}</span>
            )}
          </div>
          {execution.status === "error" && execution.error && (
            <div className="mt-1 truncate text-xs text-destructive">
              {execution.error}
            </div>
          )}
          {execution.status === "success" && execution.result && (
            <div className="mt-1 truncate text-xs">{execution.result}</div>
          )}
        </div>
      </button>
      {expanded && (
        <div className="border-t border-border bg-muted/20">
          <ExecutionLogView taskId={taskId} executionId={execution.id} />
        </div>
      )}
    </div>
  );
}

export function ExecutionsSection({ taskId }: { taskId: string }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pollUntil, setPollUntil] = useState(0);
  const [runPending, setRunPending] = useState(false);

  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: ["task-executions", taskId],
    queryFn: ({ pageParam }) =>
      autonomousApi.listExecutions(taskId, pageParam as string | undefined),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) =>
      lastPage.has_more ? (lastPage.next_cursor ?? undefined) : undefined,
    refetchInterval: (query) => {
      const executions =
        query.state.data?.pages.flatMap((page) => page.data) ?? [];
      const hasRunning = executions.some((e) => e.status === "running");
      return hasRunning || Date.now() < pollUntil ? POLL_INTERVAL_MS : false;
    },
  });

  const executions = data?.pages.flatMap((page) => page.data) ?? [];

  const handleRunNow = async () => {
    setRunPending(true);
    try {
      await autonomousApi.executeTask(taskId);
      setPollUntil(Date.now() + POLL_AFTER_RUN_MS);
      toast({
        title: "Task started",
        description: "A manual run has been triggered.",
      });
      setTimeout(() => refetch(), 1000);
    } catch (error) {
      toast({
        title: "Failed to run task",
        description:
          error instanceof Error ? error.message : "Please try again later.",
        variant: "destructive",
      });
    } finally {
      setRunPending(false);
    }
  };

  return (
    <div className="mt-8">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Runs</h2>
        <Button onClick={handleRunNow} disabled={runPending}>
          {runPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Play className="mr-2 h-4 w-4" />
          )}
          Run Now
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive">
          <p className="font-medium">Error loading runs</p>
          <p className="mt-1 text-sm">
            {error instanceof Error ? error.message : "Please try again later."}
          </p>
        </div>
      ) : executions.length === 0 ? (
        <div className="rounded-lg border border-border p-8 text-center text-muted-foreground">
          <History className="mx-auto mb-3 h-10 w-10 opacity-20" />
          <p className="text-sm">
            No runs yet. The next scheduled run will appear here, or use Run
            Now to start one.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {executions.map((execution) => (
            <ExecutionRow
              key={execution.id}
              taskId={taskId}
              execution={execution}
              expanded={expandedId === execution.id}
              onToggle={() =>
                setExpandedId(expandedId === execution.id ? null : execution.id)
              }
            />
          ))}
          {hasNextPage && (
            <div className="pt-2 text-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Load more
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
