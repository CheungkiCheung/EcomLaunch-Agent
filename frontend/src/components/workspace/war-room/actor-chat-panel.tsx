"use client";

import { BotIcon, HistoryIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import {
  InputBox,
  type InputBoxContext,
} from "@/components/workspace/input-box";
import { ThreadContext } from "@/components/workspace/messages/context";
import { MarkdownContent } from "@/components/workspace/messages/markdown-content";
import { useI18n } from "@/core/i18n/hooks";
import { useThreadSettings } from "@/core/settings";
import { humanMessagePlugins } from "@/core/streamdown";
import { useThreads, useThreadStream } from "@/core/threads/hooks";
import { uuid } from "@/core/utils/uuid";
import { cn } from "@/lib/utils";

import type { ActorView } from "./office-scene";
import type { WarRoomActorSnapshot } from "./types";

const CHAT_AGENT_NAMES: Record<string, string> = {
  "ecom-launch": "ecom-launch",
  "data-inspector": "data-inspector",
  "market-voc-researcher": "market-voc-researcher",
  "offer-architect": "offer-architect",
  "asset-studio": "asset-studio",
  "evidence-checker": "evidence-checker",
};

export function ActorChatPanel({
  actor,
  initialView = "chat",
}: {
  actor: WarRoomActorSnapshot;
  initialView?: ActorView;
}) {
  const { t } = useI18n();
  const copy = t.warRoom;
  const agentName = CHAT_AGENT_NAMES[actor.id];
  const [view, setView] = useState(initialView);
  // When the selected actor or requested view changes, reset the view
  useEffect(() => {
    setView(initialView);
  }, [actor.id, initialView]);
  // Before the first send, pass undefined to useThreadStream so it never
  // fetches history for a phantom thread id (which would 404 on the
  // backend). After onStart the real thread id is used for history and
  // subsequent messages.
  const [isNewThread, setIsNewThread] = useState(true);
  const [threadId, setThreadId] = useState<string>(() => uuid());
  const [settings, setSettings] = useThreadSettings(threadId);
  const [showHistory, setShowHistory] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // Past threads for this agent (each specialist holds its own session)
  const historyQuery = useThreads({
    limit: 20,
    sortBy: "updated_at",
    sortOrder: "desc",
    select: ["thread_id", "updated_at", "values", "metadata"],
    metadata: { agent_name: agentName },
  });
  const historyThreads = historyQuery.data ?? [];

  const { thread, sendMessage, isUploading } = useThreadStream({
    threadId: isNewThread ? undefined : threadId,
    context: { ...settings.context, agent_name: agentName },
    runtimeContext:
      actor.id === "ecom-launch"
        ? {
            is_plan_mode: false,
            subagent_enabled: settings.context.mode !== "flash",
            max_concurrent_subagents: 2,
          }
        : undefined,
    onStart: (createdThreadId) => {
      setThreadId(createdThreadId);
      setIsNewThread(false);
    },
  });

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [thread.messages.length]);

  const handleSubmit = useCallback(
    (message: Parameters<typeof sendMessage>[1]) => {
      // Pass the local uuid — the SDK auto-creates the thread on first
      // submit; useThreadStream's own threadId stays undefined until
      // onStart returns the real id.
      const sendPromise = sendMessage(threadId, message, {
        agent_name: agentName,
      });
      if (message.files.length > 0) {
        return sendPromise;
      }
      void sendPromise;
    },
    [sendMessage, threadId, agentName],
  );

  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  const handleContextChange = useCallback(
    (context: InputBoxContext) => {
      const nextContext =
        context.mode === "ultra" && context.model_name === "deepseek-chat"
          ? { ...context, model_name: "deepseek-reasoner" }
          : context;
      setSettings("context", nextContext);
    },
    [setSettings],
  );

  const lastAssistantText = [...thread.messages]
    .reverse()
    .map((m) => {
      if (m.type !== "ai") return "";
      const content = m.content;
      if (typeof content === "string") return content;
      if (Array.isArray(content)) {
        return content
          .map((part) => (part.type === "text" ? part.text : ""))
          .join("");
      }
      return "";
    })
    .find((t) => t && t.trim().length > 0);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* View tabs: chat / task / output */}
      <div className="flex shrink-0 gap-1 px-1 pb-1">
        {(
          [
            { id: "chat", label: copy.chat },
            { id: "task", label: copy.task },
            { id: "output", label: copy.output },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setView(tab.id)}
            className={cn(
              "rounded-md px-2 py-0.5 text-[10px] font-medium transition",
              view === tab.id
                ? "bg-orange-500 text-white"
                : "bg-stone-100 text-stone-500 hover:bg-stone-200",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {view === "task" && (
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-1 py-1">
          {actor.taskDetail ? (
            <div className="rounded-xl border border-stone-200 bg-stone-50/80 p-3">
              <p className="text-[11px] font-medium text-stone-600">
                {actor.taskDetail.description}
              </p>
              <p
                className={cn(
                  "mt-1 inline-block rounded-full px-2 py-0.5 text-[10px]",
                  actor.taskDetail.status === "completed"
                    ? "bg-emerald-100 text-emerald-700"
                    : actor.taskDetail.status === "failed"
                      ? "bg-red-100 text-red-700"
                      : "bg-amber-100 text-amber-700",
                )}
              >
                {actor.taskDetail.status === "completed"
                  ? copy.chatPanel.taskCompleted
                  : actor.taskDetail.status === "failed"
                    ? copy.chatPanel.taskFailed
                    : copy.chatPanel.taskRunning}
              </p>
            </div>
          ) : (
            <p className="py-4 text-center text-[11px] text-stone-400">
              {copy.chatPanel.noTask}
            </p>
          )}
        </div>
      )}

      {view === "output" && (
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-1 py-1">
          {actor.taskDetail?.output ? (
            <pre className="max-h-full overflow-auto rounded-xl border border-stone-200 bg-stone-50/80 p-3 text-[11px] leading-4 whitespace-pre-wrap text-stone-600">
              {actor.taskDetail.output}
            </pre>
          ) : (
            <p className="py-4 text-center text-[11px] text-stone-400">
              {copy.chatPanel.noOutput}
            </p>
          )}
        </div>
      )}

      {view === "chat" && (
        <>
          {/* Session history toggle */}
          <div className="shrink-0">
            <button
              type="button"
              onClick={() => {
                setShowHistory((v) => !v);
                if (!showHistory) void historyQuery.refetch();
              }}
              className="flex w-full items-center gap-1.5 rounded-lg px-1 py-1 text-[10px] text-stone-400 transition hover:bg-stone-100 hover:text-stone-600"
            >
              <HistoryIcon className="size-3" />
              {copy.chatPanel.history(historyThreads.length)}
              <span className="ml-auto">{showHistory ? "▾" : "▸"}</span>
            </button>
            {showHistory && (
              <div className="mb-1 max-h-28 space-y-1 overflow-y-auto rounded-lg border border-stone-100 bg-stone-50/60 p-1.5">
                {historyThreads.length === 0 ? (
                  <p className="px-1 py-1 text-[10px] text-stone-400">
                    {copy.chatPanel.noHistory}
                  </p>
                ) : (
                  historyThreads.map((t) => (
                    <button
                      key={t.thread_id}
                      type="button"
                      onClick={() => {
                        setThreadId(t.thread_id);
                        setIsNewThread(false);
                        setShowHistory(false);
                      }}
                      className={cn(
                        "flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-left text-[10px] transition hover:bg-white",
                        t.thread_id === threadId && "bg-white shadow-sm",
                      )}
                    >
                      <HistoryIcon className="size-2.5 shrink-0 text-stone-300" />
                      <span className="truncate text-stone-600">
                        {t.values?.title ?? copy.chatPanel.untitled}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Message list */}
          <div
            ref={listRef}
            className="min-h-0 flex-1 space-y-2 overflow-y-auto px-1 py-2"
          >
            {thread.messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center py-8 text-center">
                <BotIcon className="size-8 text-stone-300" />
                <p className="mt-2 text-xs font-medium text-stone-500">
                  {copy.chatPanel.startChat(actor.name)}
                </p>
                <p className="mt-1 text-[11px] text-stone-400">
                  {copy.chatPanel.startChatHint}
                </p>
              </div>
            ) : (
              thread.messages.map((message, index) => {
                const isUser = message.type === "human";
                const text = isUser
                  ? typeof message.content === "string"
                    ? message.content
                    : Array.isArray(message.content)
                      ? message.content
                          .map((part) =>
                            part.type === "text" ? part.text : "",
                          )
                          .join("")
                      : ""
                  : typeof message.content === "string"
                    ? message.content
                    : "";
                if (!text.trim() && !isUser) return null;
                return (
                  <div
                    key={message.id ?? index}
                    className={cn(
                      "flex",
                      isUser ? "justify-end" : "justify-start",
                    )}
                  >
                    <div
                      className={cn(
                        "max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-5",
                        isUser
                          ? "bg-orange-500 text-white"
                          : "border border-stone-200 bg-white text-stone-700",
                      )}
                    >
                      {isUser ? (
                        text
                      ) : (
                        <MarkdownContent
                          content={text}
                          isLoading={false}
                          rehypePlugins={humanMessagePlugins.rehypePlugins}
                        />
                      )}
                    </div>
                  </div>
                );
              })
            )}
            {thread.isLoading && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-stone-200 bg-white px-3 py-2">
                  <span className="flex gap-1">
                    <span className="size-1.5 animate-bounce rounded-full bg-stone-400 [animation-delay:-0.3s]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-stone-400 [animation-delay:-0.15s]" />
                    <span className="size-1.5 animate-bounce rounded-full bg-stone-400" />
                  </span>
                </div>
              </div>
            )}
            {!thread.isLoading && lastAssistantText && (
              <p className="pt-1 text-right text-[10px] text-stone-400">
                {copy.chatPanel.responseComplete}
              </p>
            )}
          </div>

          {/* Input */}
          <div className="shrink-0 border-t border-stone-100 pt-2">
            <ThreadContext.Provider value={{ thread }}>
              <PromptInputProvider>
                <InputBox
                  threadId={threadId}
                  context={settings.context}
                  autoFocus={false}
                  status={
                    thread.error
                      ? "error"
                      : thread.isLoading
                        ? "streaming"
                        : "ready"
                  }
                  availableModes={
                    actor.id === "ecom-launch" ? ["flash", "ultra"] : undefined
                  }
                  disabled={isUploading}
                  onContextChange={handleContextChange}
                  onSubmit={handleSubmit}
                  onStop={handleStop}
                />
              </PromptInputProvider>
            </ThreadContext.Provider>
          </div>
        </>
      )}
    </div>
  );
}
