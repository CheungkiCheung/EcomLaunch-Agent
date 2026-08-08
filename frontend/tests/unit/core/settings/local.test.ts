import { afterEach, expect, test, vi } from "vitest";

import {
  DEFAULT_LOCAL_SETTINGS,
  LEGACY_LOCAL_SETTINGS_KEY,
  LEGACY_THREAD_MODEL_KEY_PREFIX,
  LOCAL_SETTINGS_KEY,
  THREAD_MODEL_KEY_PREFIX,
  getLocalSettings,
  getThreadModelName,
} from "@/core/settings/local";

function installStorage(entries: Record<string, string>) {
  const values = new Map(Object.entries(entries));
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  };
  vi.stubGlobal("window", {});
  vi.stubGlobal("localStorage", storage);
  return values;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

test("defaults token usage to header total plus per-turn breakdown", () => {
  expect(DEFAULT_LOCAL_SETTINGS.tokenUsage).toEqual({
    headerTotal: true,
    inlineMode: "per_turn",
  });
});

test("migrates legacy local settings to the OpenSKU storage key", () => {
  const values = installStorage({
    [LEGACY_LOCAL_SETTINGS_KEY]: JSON.stringify({
      context: { mode: "ultra" },
    }),
  });

  expect(getLocalSettings().context.mode).toBe("ultra");
  expect(values.has(LOCAL_SETTINGS_KEY)).toBe(true);
  expect(values.has(LEGACY_LOCAL_SETTINGS_KEY)).toBe(false);
});

test("migrates a legacy per-thread model override", () => {
  const threadId = "thread-1";
  const values = installStorage({
    [`${LEGACY_THREAD_MODEL_KEY_PREFIX}${threadId}`]: "legacy-model",
  });

  expect(getThreadModelName(threadId)).toBe("legacy-model");
  expect(values.get(`${THREAD_MODEL_KEY_PREFIX}${threadId}`)).toBe(
    "legacy-model",
  );
  expect(values.has(`${LEGACY_THREAD_MODEL_KEY_PREFIX}${threadId}`)).toBe(
    false,
  );
});
