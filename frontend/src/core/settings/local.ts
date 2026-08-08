import type { TokenUsageInlineMode } from "../messages/usage-model";
import type { AgentThreadContext } from "../threads";

export const DEFAULT_LOCAL_SETTINGS: LocalSettings = {
  notification: {
    enabled: true,
  },
  tokenUsage: {
    headerTotal: true,
    inlineMode: "per_turn",
  },
  context: {
    model_name: undefined,
    mode: undefined,
    reasoning_effort: undefined,
  },
};

export const LOCAL_SETTINGS_KEY = "opensku.local-settings";
export const THREAD_MODEL_KEY_PREFIX = "opensku.thread-model.";
export const LEGACY_LOCAL_SETTINGS_KEY = "deerflow.local-settings";
export const LEGACY_THREAD_MODEL_KEY_PREFIX = "deerflow.thread-model.";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export interface LocalSettings {
  notification: {
    enabled: boolean;
  };
  tokenUsage: {
    headerTotal: boolean;
    inlineMode: TokenUsageInlineMode;
  };
  context: Omit<
    AgentThreadContext,
    | "thread_id"
    | "is_plan_mode"
    | "thinking_enabled"
    | "subagent_enabled"
    | "model_name"
    | "reasoning_effort"
  > & {
    model_name?: string | undefined;
    mode: "flash" | "thinking" | "pro" | "ultra" | undefined;
    reasoning_effort?: "minimal" | "low" | "medium" | "high";
  };
}

function mergeLocalSettings(settings?: Partial<LocalSettings>): LocalSettings {
  return {
    ...DEFAULT_LOCAL_SETTINGS,
    context: {
      ...DEFAULT_LOCAL_SETTINGS.context,
      ...settings?.context,
    },
    tokenUsage: {
      ...DEFAULT_LOCAL_SETTINGS.tokenUsage,
      ...settings?.tokenUsage,
    },
    notification: {
      ...DEFAULT_LOCAL_SETTINGS.notification,
      ...settings?.notification,
    },
  };
}

function getThreadModelStorageKey(threadId: string): string {
  return `${THREAD_MODEL_KEY_PREFIX}${threadId}`;
}

function getLegacyThreadModelStorageKey(threadId: string): string {
  return `${LEGACY_THREAD_MODEL_KEY_PREFIX}${threadId}`;
}

export function getThreadModelName(threadId: string): string | undefined {
  if (!isBrowser()) {
    return undefined;
  }
  const current = localStorage.getItem(getThreadModelStorageKey(threadId));
  if (current !== null) {
    return current;
  }
  const legacyKey = getLegacyThreadModelStorageKey(threadId);
  const legacy = localStorage.getItem(legacyKey);
  if (legacy !== null) {
    localStorage.setItem(getThreadModelStorageKey(threadId), legacy);
    localStorage.removeItem(legacyKey);
    return legacy;
  }
  return undefined;
}

export function saveThreadModelName(
  threadId: string,
  modelName: string | undefined,
) {
  if (!isBrowser()) {
    return;
  }
  const key = getThreadModelStorageKey(threadId);
  if (!modelName) {
    localStorage.removeItem(key);
    localStorage.removeItem(getLegacyThreadModelStorageKey(threadId));
    return;
  }
  localStorage.setItem(key, modelName);
  localStorage.removeItem(getLegacyThreadModelStorageKey(threadId));
}

export function applyThreadModelOverride(
  settings: LocalSettings,
  threadModelName: string | undefined,
): LocalSettings {
  if (!threadModelName) {
    return settings;
  }
  return {
    ...settings,
    context: {
      ...settings.context,
      model_name: threadModelName,
    },
  };
}

export function getLocalSettings(): LocalSettings {
  if (!isBrowser()) {
    return DEFAULT_LOCAL_SETTINGS;
  }
  const current = localStorage.getItem(LOCAL_SETTINGS_KEY);
  const legacy =
    current === null ? localStorage.getItem(LEGACY_LOCAL_SETTINGS_KEY) : null;
  const json = current ?? legacy;
  try {
    if (json) {
      const settings = JSON.parse(json) as Partial<LocalSettings>;
      const merged = mergeLocalSettings(settings);
      if (legacy !== null) {
        localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(merged));
        localStorage.removeItem(LEGACY_LOCAL_SETTINGS_KEY);
      }
      return merged;
    }
  } catch {}
  return DEFAULT_LOCAL_SETTINGS;
}

export function saveLocalSettings(settings: LocalSettings) {
  if (!isBrowser()) {
    return;
  }
  localStorage.setItem(LOCAL_SETTINGS_KEY, JSON.stringify(settings));
  localStorage.removeItem(LEGACY_LOCAL_SETTINGS_KEY);
}
