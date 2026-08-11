import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { useThread } from "@/components/workspace/messages/context";

import { loadArtifactContent, loadArtifactContentFromToolCall } from "./loader";

export function useArtifactContent({
  filepath,
  threadId,
  enabled,
}: {
  filepath: string;
  threadId: string;
  enabled?: boolean;
}) {
  const isWriteFile = useMemo(() => {
    return filepath.startsWith("write-file:");
  }, [filepath]);
  const { thread, isMock } = useThread();
  const content = useMemo(() => {
    if (isWriteFile) {
      return loadArtifactContentFromToolCall({ url: filepath, thread });
    }
    return null;
  }, [filepath, isWriteFile, thread]);
  const artifactRevision = useMemo(() => {
    for (let index = thread.messages.length - 1; index >= 0; index -= 1) {
      const message = thread.messages[index];
      if (
        message?.type === "tool" &&
        message.status !== "error" &&
        (message.name === "present_files" ||
          message.name === "render_launch_pack")
      ) {
        return message.id ?? message.tool_call_id ?? index;
      }
    }
    return "no-completed-presentation";
  }, [thread.messages]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["artifact", filepath, threadId, isMock, artifactRevision],
    queryFn: () => {
      return loadArtifactContent({ filepath, threadId, isMock });
    },
    enabled,
    // Cache artifact content for 5 minutes to avoid repeated fetches (especially for .skill ZIP extraction)
    staleTime: 5 * 60 * 1000,
  });
  return {
    content: isWriteFile ? content : data?.content,
    url: isWriteFile ? undefined : data?.url,
    isLoading,
    error,
    refetch,
  };
}
