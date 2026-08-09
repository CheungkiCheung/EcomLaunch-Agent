import type { Message } from "@langchain/langgraph-sdk";

import { enUS } from "@/core/i18n/locales/en-US";
import type { Translations } from "@/core/i18n/locales/types";
import {
  extractPresentFilesFromMessage,
  extractTextFromMessage,
  hasPresentFiles,
} from "@/core/messages/utils";
import { parseSubtaskResult } from "@/core/tasks/subtask-result";
import type { Subtask } from "@/core/tasks/types";
import { pathOfThread, textOfMessage } from "@/core/threads/utils";

import { localizeWarRoomActors } from "./config";
import type {
  WarRoomActivity,
  WarRoomActorConfig,
  WarRoomActorId,
  WarRoomActorSnapshot,
  WarRoomMetrics,
  WarRoomRunStatus,
  WarRoomSnapshot,
  WarRoomSource,
  WarRoomStage,
  WarRoomStatus,
  WarRoomTeam,
} from "./types";

const SUBAGENT_IDS = new Set<WarRoomActorId>([
  "market-voc-researcher",
  "offer-architect",
  "asset-studio",
  "evidence-checker",
]);

export function hydrateWarRoomThread(
  thread: WarRoomSource["ecomThread"],
  state:
    | { values?: NonNullable<WarRoomSource["ecomThread"]>["values"] }
    | null
    | undefined,
) {
  if (!thread || !state?.values) {
    return thread;
  }
  return {
    ...thread,
    values: {
      ...(thread.values ?? {}),
      ...state.values,
    },
  };
}

type TaskRecord = Subtask & {
  sequence: number;
  output?: string;
};

function messagesOf(source: WarRoomSource["ecomThread"]) {
  return source?.values?.messages ?? [];
}

function artifactsOf(source: WarRoomSource["ecomThread"]) {
  const files = [...(source?.values?.artifacts ?? [])];
  for (const message of messagesOf(source)) {
    if (hasPresentFiles(message)) {
      files.push(...extractPresentFilesFromMessage(message));
    }
  }
  return [...new Set(files)];
}

function tasksFromMessages(messages: Message[]) {
  const tasks = new Map<string, TaskRecord>();
  let sequence = 0;

  for (const message of messages) {
    if (message.type === "ai") {
      for (const toolCall of message.tool_calls ?? []) {
        if (toolCall.name !== "task" || !toolCall.id) continue;
        const args = toolCall.args as {
          subagent_type?: string;
          description?: string;
          prompt?: string;
        };
        if (!SUBAGENT_IDS.has(args.subagent_type as WarRoomActorId)) continue;
        tasks.set(toolCall.id, {
          id: toolCall.id,
          status: "in_progress",
          subagent_type: args.subagent_type!,
          description: args.description ?? args.subagent_type!,
          prompt: args.prompt ?? "",
          latestMessage: message,
          sequence: sequence++,
        });
      }
      continue;
    }

    if (message.type !== "tool" || !message.tool_call_id) continue;
    const task = tasks.get(message.tool_call_id);
    if (!task) continue;
    const result = parseSubtaskResult(
      extractTextFromMessage(message),
      message.additional_kwargs,
    );
    tasks.set(message.tool_call_id, {
      ...task,
      ...result,
      output: extractTextFromMessage(message),
    });
  }

  return [...tasks.values()];
}

function latestTaskForRole(tasks: TaskRecord[], id: WarRoomActorId) {
  return tasks
    .filter((task) => task.subagent_type === id)
    .sort((a, b) => b.sequence - a.sequence)[0];
}

function latestHumanRequest(messages: Message[]) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.type !== "human") continue;
    const text = textOfMessage(message)?.trim();
    if (text) return text;
  }
  return undefined;
}

function latestTool(messages: Message[], includeTask = false) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.type !== "ai") continue;
    const toolCall = [...(message.tool_calls ?? [])]
      .reverse()
      .find((tool) => includeTask || tool.name !== "task");
    if (toolCall) return toolCall.name;
  }
  return undefined;
}

function statusFromRun(runStatus: WarRoomRunStatus | undefined): WarRoomStatus {
  if (runStatus === "pending") return "queued";
  if (runStatus === "running") return "working";
  if (
    runStatus === "error" ||
    runStatus === "timeout" ||
    runStatus === "interrupted"
  ) {
    return "failed";
  }
  if (runStatus === "success") return "done";
  return "idle";
}

function statusFromTask(task: TaskRecord | undefined): WarRoomStatus {
  if (!task) return "idle";
  if (task.status === "failed") return "failed";
  if (task.status === "completed") return "done";
  return "working";
}

function activityFromTool(
  tool: string | undefined,
  fallback: WarRoomActivity,
): WarRoomActivity {
  if (!tool) return fallback;
  if (tool === "web_search" || tool === "image_search") return "searching";
  if (tool === "read_file" || tool === "web_fetch" || tool === "inspect_data") {
    return "reading";
  }
  if (
    tool === "query_data" ||
    tool === "analyze_ab_test" ||
    tool.includes("python") ||
    tool.includes("sql")
  ) {
    return "analyzing";
  }
  if (tool === "write_file") return "writing";
  if (tool === "present_files" || tool === "render_launch_pack")
    return "delivering";
  return fallback;
}

function activityFromTask(task: TaskRecord | undefined): WarRoomActivity {
  if (!task) return "waiting";
  if (task.status === "completed") return "delivering";
  if (task.status === "failed") return "reviewing";
  const text = `${task.description} ${task.prompt}`.toLowerCase();
  if (/search|research|market|voc|竞品|市场|用户|评价/.test(text)) {
    return "searching";
  }
  if (/evidence|verify|audit|review|证据|审核|检查/.test(text)) {
    return "reviewing";
  }
  if (/asset|content|copy|listing|素材|内容|文案/.test(text)) {
    return "writing";
  }
  return "analyzing";
}

function summaryFor(
  status: WarRoomStatus,
  activity: WarRoomActivity,
  copy: Translations["warRoom"],
  task?: string,
) {
  if (status === "failed") return copy.summaries.failed;
  if (status === "done") return copy.summaries.done;
  if (status === "queued") return copy.summaries.queued;
  if (status === "idle") return copy.summaries.idle;
  const label = copy.summaries[activity];
  return task ? `${label} ${task}` : label;
}

function hrefFor(source: WarRoomSource["ecomThread"]) {
  return source ? pathOfThread(source) : undefined;
}

function buildLeadActor(
  source: WarRoomSource,
  actors: WarRoomActorConfig[],
  copy: Translations["warRoom"],
): WarRoomActorSnapshot {
  const config = actors.find((actor) => actor.id === "ecom-launch")!;
  const messages = messagesOf(source.ecomThread);
  const tool = latestTool(messages, true);
  const status = statusFromRun(source.ecomRunStatus);
  const activity = activityFromTool(tool, "orchestrating");
  const task = latestHumanRequest(messages);
  return {
    ...config,
    status,
    activity: status === "idle" ? "waiting" : activity,
    summary: summaryFor(status, activity, copy, task),
    task,
    tool,
    artifacts: artifactsOf(source.ecomThread),
    threadId: source.ecomThread?.thread_id,
    href: hrefFor(source.ecomThread),
  };
}

function buildSubagentActor(
  id: WarRoomActorId,
  source: WarRoomSource,
  tasks: TaskRecord[],
  actors: WarRoomActorConfig[],
  copy: Translations["warRoom"],
): WarRoomActorSnapshot {
  const config = actors.find((actor) => actor.id === id)!;
  const task = latestTaskForRole(tasks, id);
  const status = statusFromTask(task);
  const activity = activityFromTask(task);
  return {
    ...config,
    status,
    activity,
    summary: summaryFor(status, activity, copy, task?.description),
    task: task?.description,
    tool: task?.latestMessage?.tool_calls?.at(-1)?.name,
    artifacts: [],
    threadId: source.ecomThread?.thread_id,
    href: hrefFor(source.ecomThread),
    taskDetail: task
      ? {
          id: task.id,
          description: task.description,
          status: task.status,
          output: task.output,
          error: task.error,
        }
      : undefined,
  };
}

function buildDataActor(
  source: WarRoomSource,
  actors: WarRoomActorConfig[],
  copy: Translations["warRoom"],
): WarRoomActorSnapshot {
  const config = actors.find((actor) => actor.id === "data-inspector")!;
  const messages = messagesOf(source.dataThread);
  const tool = latestTool(messages);
  const status = statusFromRun(source.dataRunStatus);
  const activity = activityFromTool(tool, "analyzing");
  const task = latestHumanRequest(messages);
  return {
    ...config,
    status,
    activity: status === "idle" ? "waiting" : activity,
    summary: summaryFor(status, activity, copy, task),
    task,
    tool,
    artifacts: artifactsOf(source.dataThread),
    threadId: source.dataThread?.thread_id,
    href: hrefFor(source.dataThread),
  };
}

function buildStages(
  source: WarRoomSource,
  tasks: TaskRecord[],
  copy: Translations["warRoom"],
): WarRoomStage[] {
  const definitions = [
    { id: "init", label: copy.stages.init },
    { id: "market-voc-researcher", label: copy.stages.research },
    { id: "offer-architect", label: copy.stages.offer },
    { id: "asset-studio", label: copy.stages.content },
    { id: "pack", label: copy.stages.pack },
    { id: "preflight", label: copy.stages.preflight },
    { id: "done", label: copy.stages.done },
  ] as const;

  const taskStatus = (id: string) => {
    const task = latestTaskForRole(tasks, id as WarRoomActorId);
    return task?.status;
  };
  const launchMessages = messagesOf(source.ecomThread);
  const rendererCallIds = new Set(
    launchMessages.flatMap((message) =>
      message.type === "ai"
        ? (message.tool_calls ?? [])
            .filter((call) => call.name === "render_launch_pack" && call.id)
            .map((call) => call.id!)
        : [],
    ),
  );
  const rendererCall = rendererCallIds.size > 0;
  const rendererSucceeded = launchMessages.some(
    (message) =>
      message.type === "tool" &&
      typeof message.tool_call_id === "string" &&
      rendererCallIds.has(message.tool_call_id) &&
      extractTextFromMessage(message).includes("Successfully presented files"),
  );

  let currentIndex = 0;
  if (source.ecomRunStatus === "success") {
    currentIndex = definitions.length - 1;
  } else if (taskStatus("market-voc-researcher") === "in_progress") {
    currentIndex = 1;
  } else if (taskStatus("market-voc-researcher") === "completed") {
    currentIndex = taskStatus("offer-architect") === "in_progress" ? 2 : 3;
  } else if (taskStatus("offer-architect") === "completed") {
    currentIndex = taskStatus("asset-studio") === "in_progress" ? 3 : 4;
  } else if (taskStatus("asset-studio") === "completed") {
    currentIndex = 4;
  }
  if (rendererCall) {
    currentIndex =
      rendererSucceeded && source.ecomRunStatus === "success" ? 6 : 5;
  }

  return definitions.map((stage, index) => ({
    id: stage.id,
    label: stage.label,
    done: index < currentIndex,
    current: index === currentIndex,
  }));
}

function toolProgress(
  messages: Message[],
  names: Set<string>,
): { called: boolean; completed: boolean } {
  const callIds = new Set<string>();
  let called = false;
  for (const message of messages) {
    if (message.type !== "ai") continue;
    for (const call of message.tool_calls ?? []) {
      if (!names.has(call.name)) continue;
      called = true;
      if (call.id) callIds.add(call.id);
    }
  }
  if (!called) return { called: false, completed: false };
  if (callIds.size === 0) return { called: true, completed: false };
  return {
    called: true,
    completed: messages.some(
      (message) =>
        message.type === "tool" &&
        typeof message.tool_call_id === "string" &&
        callIds.has(message.tool_call_id),
    ),
  };
}

function buildGrowthStages(
  source: WarRoomSource,
  copy: Translations["warRoom"],
): WarRoomStage[] {
  const definitions = [
    { id: "data-intake", label: copy.stages.dataIntake },
    { id: "data-inspect", label: copy.stages.dataInspect },
    { id: "data-join", label: copy.stages.dataJoin },
    { id: "data-experiment", label: copy.stages.dataExperiment },
    { id: "data-decision", label: copy.stages.dataDecision },
  ] as const;
  const messages = messagesOf(source.dataThread);
  const hasRequest = Boolean(latestHumanRequest(messages));
  const inspect = toolProgress(
    messages,
    new Set(["inspect_data", "list_tables"]),
  );
  const join = toolProgress(
    messages,
    new Set(["query_data", "join_files", "join_data"]),
  );
  const experiment = toolProgress(
    messages,
    new Set(["analyze_ab_test", "analyze_cohort", "calculate_statistics"]),
  );

  let currentIndex = 0;
  if (source.dataRunStatus === "success") {
    currentIndex = definitions.length - 1;
  } else if (!hasRequest) {
    currentIndex = 0;
  } else if (!inspect.called || !inspect.completed) {
    currentIndex = 1;
  } else if (!join.called || !join.completed) {
    currentIndex = 2;
  } else if (!experiment.called || !experiment.completed) {
    currentIndex = 3;
  } else {
    currentIndex = 4;
  }

  return definitions.map((stage, index) => ({
    id: stage.id,
    label: stage.label,
    done: index < currentIndex,
    current: index === currentIndex,
  }));
}

function buildMetrics(
  source: WarRoomSource,
  focusTeam: WarRoomTeam,
): WarRoomMetrics {
  const runs =
    focusTeam === "data-inspector"
      ? (source.dataRuns ?? [])
      : (source.ecomRuns ?? []);
  const latest = runs[0];
  const messages =
    focusTeam === "data-inspector"
      ? messagesOf(source.dataThread)
      : messagesOf(source.ecomThread);
  let webSearches = 0;
  let webFetches = 0;
  let writeFiles = 0;
  let presentCalls = 0;
  let dataQueries = 0;
  let experiments = 0;
  for (const message of messages) {
    if (message.type !== "ai") continue;
    for (const call of message.tool_calls ?? []) {
      if (call.name === "web_search") webSearches += 1;
      if (call.name === "web_fetch") webFetches += 1;
      if (call.name === "write_file") writeFiles += 1;
      if (call.name === "present_files" || call.name === "render_launch_pack") {
        presentCalls += 1;
      }
      if (
        call.name === "inspect_data" ||
        call.name === "query_data" ||
        call.name === "join_files" ||
        call.name === "join_data" ||
        call.name === "list_tables"
      ) {
        dataQueries += 1;
      }
      if (
        call.name === "analyze_ab_test" ||
        call.name === "analyze_cohort" ||
        call.name === "calculate_statistics"
      ) {
        experiments += 1;
      }
    }
  }
  let durationSeconds: number | undefined;
  if (latest?.created_at && latest?.updated_at) {
    durationSeconds = Math.max(
      0,
      Math.round(
        (new Date(latest.updated_at).getTime() -
          new Date(latest.created_at).getTime()) /
          1000,
      ),
    );
  }
  return {
    llmCalls: latest?.llm_call_count ?? 0,
    totalTokens: latest?.total_tokens ?? 0,
    durationSeconds,
    webSearches,
    webFetches,
    writeFiles,
    presentCalls,
    dataQueries,
    experiments,
  };
}

export function buildWarRoomSnapshot(
  source: WarRoomSource,
  copy: Translations["warRoom"] = enUS.warRoom,
  focusTeam: WarRoomTeam = "ecom-launch",
): WarRoomSnapshot {
  const tasks = tasksFromMessages(messagesOf(source.ecomThread));
  const actorConfigs = localizeWarRoomActors(copy.actors);
  const actors = actorConfigs.map((actor) => {
    if (actor.id === "ecom-launch") {
      return buildLeadActor(source, actorConfigs, copy);
    }
    if (actor.id === "data-inspector") {
      return buildDataActor(source, actorConfigs, copy);
    }
    return buildSubagentActor(actor.id, source, tasks, actorConfigs, copy);
  });
  return {
    focusTeam,
    actors,
    activeCount: actors.filter(
      (actor) => actor.status === "queued" || actor.status === "working",
    ).length,
    completedCount: actors.filter((actor) => actor.status === "done").length,
    failedCount: actors.filter((actor) => actor.status === "failed").length,
    artifactCount: new Set(actors.flatMap((actor) => actor.artifacts)).size,
    updatedAt: new Date().toISOString(),
    stages:
      focusTeam === "data-inspector"
        ? buildGrowthStages(source, copy)
        : buildStages(source, tasks, copy),
    metrics: buildMetrics(source, focusTeam),
    runStatus:
      focusTeam === "data-inspector"
        ? source.dataRunStatus
        : source.ecomRunStatus,
    runTitle:
      focusTeam === "data-inspector"
        ? (source.dataThread?.values?.title ?? undefined)
        : (source.ecomThread?.values?.title ?? undefined),
  };
}
