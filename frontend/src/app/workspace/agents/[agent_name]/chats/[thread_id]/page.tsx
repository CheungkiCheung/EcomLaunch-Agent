"use client";

import {
  BotIcon,
  DatabaseIcon,
  PlusSquare,
  ShoppingBagIcon,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { AgentWelcome } from "@/components/workspace/agent-welcome";
import { ArtifactTrigger } from "@/components/workspace/artifacts";
import { ChatBox, useThreadChat } from "@/components/workspace/chats";
import { LaunchCrewPanel } from "@/components/workspace/ecom-launch";
import { ExportTrigger } from "@/components/workspace/export-trigger";
import {
  InputBox,
  type InputBoxContext,
} from "@/components/workspace/input-box";
import {
  MessageList,
  MESSAGE_LIST_DEFAULT_PADDING_BOTTOM,
} from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import { ThreadTitle } from "@/components/workspace/thread-title";
import { TodoList } from "@/components/workspace/todo-list";
import { TokenUsageIndicator } from "@/components/workspace/token-usage-indicator";
import { Tooltip } from "@/components/workspace/tooltip";
import { useAgent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import { useModels } from "@/core/models/hooks";
import { useNotification } from "@/core/notification/hooks";
import { useLocalSettings, useThreadSettings } from "@/core/settings";
import { useThreadStream, useThreadTokenUsage } from "@/core/threads/hooks";
import { threadTokenUsageToTokenUsage } from "@/core/threads/token-usage";
import { textOfMessage } from "@/core/threads/utils";
import { env } from "@/env";
import { cn } from "@/lib/utils";

export default function AgentChatPage() {
  const { t } = useI18n();
  const router = useRouter();

  const { agent_name } = useParams<{
    agent_name: string;
  }>();
  const isEcomLaunch = agent_name === "ecom-launch";
  const isDataInspector = agent_name === "data-inspector";
  const isPrimaryAgent = isEcomLaunch || isDataInspector;

  const { agent } = useAgent(isPrimaryAgent ? null : agent_name);

  const { threadId, setThreadId, isNewThread, setIsNewThread, isMock } =
    useThreadChat();
  // `isNewThread` gates history/token-usage fetches until the backend creates
  // the thread. `isWelcomeMode` controls only the centered welcome layout, so
  // it can flip immediately on submit without triggering eager history loads.
  const [isWelcomeMode, setIsWelcomeMode] = useState(isNewThread);
  const [primaryAgentContextEdited, setPrimaryAgentContextEdited] =
    useState(false);
  const [settings, setSettings] = useThreadSettings(threadId);
  const [localSettings, setLocalSettings] = useLocalSettings();
  const { tokenUsageEnabled } = useModels();
  const threadTokenUsage = useThreadTokenUsage(
    isNewThread || isMock ? undefined : threadId,
    { enabled: tokenUsageEnabled && !isMock },
  );
  const backendTokenUsage = threadTokenUsageToTokenUsage(threadTokenUsage.data);

  const { showNotification } = useNotification();

  useEffect(() => {
    setIsWelcomeMode(isNewThread);
  }, [isNewThread]);

  useEffect(() => {
    if (isNewThread) {
      setPrimaryAgentContextEdited(false);
    }
  }, [agent_name, isNewThread, threadId]);

  const effectiveContext = useMemo(() => {
    if (!isPrimaryAgent || primaryAgentContextEdited) {
      return settings.context;
    }
    return {
      ...settings.context,
      mode: "flash" as const,
      reasoning_effort: "minimal" as const,
    };
  }, [isPrimaryAgent, primaryAgentContextEdited, settings.context]);

  const handleContextChange = useCallback(
    (context: InputBoxContext) => {
      if (!isPrimaryAgent) {
        setSettings("context", context);
        return;
      }

      const changedAwayFromDefault =
        context.mode !== "flash" ||
        (context.reasoning_effort !== undefined &&
          context.reasoning_effort !== "minimal");
      if (changedAwayFromDefault) {
        setPrimaryAgentContextEdited(true);
        // Ultra mode needs a thinking-capable model (deepseek-reasoner).
        // The default deepseek-chat does not support thinking, so the
        // InputBox would force Ultra back to Flash otherwise.
        const nextContext =
          context.mode === "ultra" && context.model_name === "deepseek-chat"
            ? { ...context, model_name: "deepseek-reasoner" }
            : context;
        setSettings("context", nextContext);
        return;
      }

      // The input box auto-selects the model on mount. Keep that preference
      // while primary-agent chats remain fast by default until the user
      // explicitly chooses a different reasoning mode.
      setSettings("context", { model_name: context.model_name });
    },
    [isPrimaryAgent, setSettings],
  );

  const {
    thread,
    pendingUsageMessages,
    sendMessage,
    isUploading,
    isHistoryLoading,
    hasMoreHistory,
    loadMoreHistory,
  } = useThreadStream({
    threadId: isNewThread ? undefined : threadId,
    context: { ...effectiveContext, agent_name: agent_name },
    runtimeContext: isEcomLaunch
      ? {
          is_plan_mode: false,
          subagent_enabled: effectiveContext.mode !== "flash",
          max_concurrent_subagents: 2,
        }
      : undefined,
    isMock,
    onSend: () => {
      setIsWelcomeMode(false);
    },
    onStart: (createdThreadId) => {
      setThreadId(createdThreadId);
      setIsNewThread(false);
      // ! Important: Never use next.js router for navigation in this case, otherwise it will cause the thread to re-mount and lose all states. Use native history API instead.
      history.replaceState(
        null,
        "",
        `/workspace/agents/${agent_name}/chats/${createdThreadId}`,
      );
    },
    onFinish: (state) => {
      if (document.hidden || !document.hasFocus()) {
        let body = "Conversation finished";
        const lastMessage = state.messages[state.messages.length - 1];
        if (lastMessage) {
          const textContent = textOfMessage(lastMessage);
          if (textContent) {
            body =
              textContent.length > 200
                ? textContent.substring(0, 200) + "..."
                : textContent;
          }
        }
        showNotification(state.title, { body });
      }
    },
  });

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const sendPromise = sendMessage(threadId, message, { agent_name });
      if (message.files.length > 0) {
        return sendPromise;
      }
      void sendPromise;
    },
    [sendMessage, threadId, agent_name],
  );

  const handleStop = useCallback(async () => {
    await thread.stop();
  }, [thread]);

  const tokenUsageInlineMode = tokenUsageEnabled
    ? localSettings.tokenUsage.inlineMode
    : "off";
  const hasTodos = (thread.values.todos?.length ?? 0) > 0;
  const AgentBadgeIcon = isEcomLaunch
    ? ShoppingBagIcon
    : isDataInspector
      ? DatabaseIcon
      : BotIcon;
  const agentDisplayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : isDataInspector
      ? t.agents.dataInspectorName
      : (agent?.name ?? agent_name);
  const welcomeSuggestions = isEcomLaunch
    ? t.agents.ecomLaunchSuggestions
    : isDataInspector
      ? t.agents.dataInspectorSuggestions
      : undefined;

  return (
    <ThreadContext.Provider value={{ thread }}>
      <ChatBox threadId={threadId}>
        <div className="relative flex size-full min-h-0 justify-between">
          <header
            className={cn(
              "absolute top-0 right-0 left-0 z-30 flex h-12 shrink-0 items-center gap-2 px-4",
              isWelcomeMode
                ? "bg-background/0 backdrop-blur-none"
                : "bg-background/80 shadow-xs backdrop-blur",
            )}
          >
            <SidebarTrigger className="-ml-2 md:hidden" />
            {/* Agent badge */}
            <div className="flex min-w-0 shrink items-center gap-1.5 rounded-md border px-2 py-1">
              <AgentBadgeIcon className="text-primary h-3.5 w-3.5" />
              <span className="truncate text-xs font-medium">
                {agentDisplayName}
              </span>
            </div>

            <div className="flex min-w-0 flex-1 items-center text-sm font-medium">
              <ThreadTitle threadId={threadId} thread={thread} />
            </div>
            <div className="flex shrink-0 items-center md:mr-4">
              <Tooltip content={t.agents.newChat}>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    router.push(`/workspace/agents/${agent_name}/chats/new`);
                  }}
                >
                  <PlusSquare />
                  <span className="hidden sm:inline">{t.agents.newChat}</span>
                </Button>
              </Tooltip>
              <TokenUsageIndicator
                threadId={isNewThread ? undefined : threadId}
                backendUsage={backendTokenUsage}
                enabled={tokenUsageEnabled}
                messages={thread.messages}
                pendingMessages={pendingUsageMessages}
                preferences={localSettings.tokenUsage}
                onPreferencesChange={(preferences) =>
                  setLocalSettings("tokenUsage", preferences)
                }
              />
              <ExportTrigger threadId={threadId} />
              <ArtifactTrigger />
            </div>
          </header>

          <main className="flex min-h-0 max-w-full grow flex-col">
            <div className="flex min-h-0 flex-1 justify-center">
              <MessageList
                className={cn("size-full", !isWelcomeMode && "pt-10")}
                threadId={threadId}
                thread={thread}
                paddingBottom={MESSAGE_LIST_DEFAULT_PADDING_BOTTOM}
                hasMoreHistory={hasMoreHistory}
                loadMoreHistory={loadMoreHistory}
                isHistoryLoading={isHistoryLoading}
                tokenUsageInlineMode={tokenUsageInlineMode}
              />
            </div>

            <div
              className={cn(
                "right-0 bottom-0 left-0 z-30 flex justify-center px-4",
                isWelcomeMode ? "absolute" : "relative shrink-0 pb-4",
              )}
            >
              <div
                className={cn(
                  "relative w-full",
                  isWelcomeMode && "-translate-y-[calc(50vh-96px)]",
                  isWelcomeMode
                    ? "max-w-(--container-width-sm)"
                    : "max-w-(--container-width-md)",
                )}
              >
                {hasTodos && (
                  <div
                    className={cn(
                      "right-0 left-0 z-0",
                      isWelcomeMode ? "absolute -top-4" : "relative",
                    )}
                  >
                    <div
                      className={cn(
                        "right-0 bottom-0 left-0",
                        isWelcomeMode ? "absolute" : "relative",
                      )}
                    >
                      <TodoList
                        className="bg-background/5"
                        todos={thread.values.todos ?? []}
                        hidden={false}
                      />
                    </div>
                  </div>
                )}

                <InputBox
                  className={cn(
                    "bg-background/5 w-full",
                    isWelcomeMode && "-translate-y-4",
                  )}
                  isWelcomeMode={isWelcomeMode}
                  threadId={threadId}
                  autoFocus={isWelcomeMode}
                  status={
                    thread.error
                      ? "error"
                      : thread.isLoading
                        ? "streaming"
                        : "ready"
                  }
                  context={effectiveContext}
                  availableModes={isEcomLaunch ? ["flash", "ultra"] : undefined}
                  expandedWelcomeHeader={isDataInspector}
                  extraHeader={
                    isWelcomeMode && (
                      <AgentWelcome agent={agent} agentName={agent_name} />
                    )
                  }
                  welcomeSuggestions={welcomeSuggestions}
                  disabled={
                    env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ||
                    isUploading
                  }
                  onContextChange={handleContextChange}
                  onSubmit={handleSubmit}
                  onStop={handleStop}
                />
                {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" && (
                  <div className="text-muted-foreground/67 w-full translate-y-12 text-center text-xs">
                    {t.common.notAvailableInDemoMode}
                  </div>
                )}
              </div>
            </div>
          </main>
          {isEcomLaunch && (
            <LaunchCrewPanel
              threadValues={thread.values}
              messages={thread.messages}
              isStreaming={thread.isLoading}
            />
          )}
        </div>
      </ChatBox>
    </ThreadContext.Provider>
  );
}
