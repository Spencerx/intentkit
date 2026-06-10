export const buildChatThreadPath = (
  agentId: string,
  threadId?: string | null,
) => {
  if (!threadId) return `/agent/${agentId}`;
  const params = new URLSearchParams({ thread: threadId });
  return `/agent/${agentId}?${params.toString()}`;
};
