import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { expect, test, type APIRequestContext } from "@playwright/test";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const APP = "http://localhost:3000";
const NATURAL_QUERY_GATE =
  process.env.DEERFLOW_COMMERCE_NATURAL_QUERY_GATE === "1";
const NATURAL_QUERY_OUTPUT_DIR =
  process.env.DEERFLOW_COMMERCE_NATURAL_QUERY_GATE_OUTPUT_DIR?.trim() ??
  "docs/progress/runs/2026-07-27-commerce-chat-natural-query-gate-v1";
const OUTPUT_DIR = path.join(
  REPO_ROOT,
  NATURAL_QUERY_GATE
    ? NATURAL_QUERY_OUTPUT_DIR
    : "docs/progress/runs/2026-07-27-commerce-chat-browser-gate-v7",
);
const INPUT_DIR = path.join(
  REPO_ROOT,
  "evals/commerce/cases/GC-FULFILLMENT-001/input",
);
const FILE_NAMES = [
  "orders.csv",
  "order_items.csv",
  "order_reviews.csv",
  "customers.csv",
  "products.csv",
  "sellers.csv",
] as const;
const FILE_PATHS = FILE_NAMES.map((name) => path.join(INPUT_DIR, name));
const NATURAL_PROMPT = "请分析这个店铺最近的履约异常";
const FROZEN_AUDIT_PROMPT = `请分析这个店铺最近的履约异常。先识别当前上传数据能回答什么，并用全量关联确认卖家 4869f7a5dfa277a7dca6462dcf3b52b2 的精确可用时间范围，不要从抽样记录推断最早或最晚日期；再用可复算指标比较基准窗口 2017-12-02 至 2018-01-31 与当前窗口 2018-01-31 至 2018-04-01。

请区分卖家处理与承运运输阶段，给出支持证据、反证或替代解释、未知项、数据限制和下一步，并让独立核验任务重新计算核心指标后再回答。所有数值必须来自确定性工具。

本次数据没有曝光、点击、加购、广告消耗、库存、利润或 GMV，不要推断这些指标；不要把相关性写成因果。最终请用简洁自然的中文回答，不使用 Markdown 表格和装饰性 Emoji。`;
const PROMPT = NATURAL_QUERY_GATE ? NATURAL_PROMPT : FROZEN_AUDIT_PROMPT;
const EXISTING_THREAD_ID =
  process.env.DEERFLOW_COMMERCE_EXISTING_THREAD_ID?.trim();
const EXISTING_RUN_ID = process.env.DEERFLOW_COMMERCE_EXISTING_RUN_ID?.trim();
const EXISTING_ACCOUNT_EMAIL =
  process.env.DEERFLOW_COMMERCE_EXISTING_ACCOUNT_EMAIL?.trim();
const TEST_ACCOUNT_PASSWORD = "very-strong-commerce-gate-password-123";

type JsonRecord = Record<string, unknown>;

test.skip(
  process.env.DEERFLOW_COMMERCE_REAL_MODEL_GATE !== "1",
  "Set DEERFLOW_COMMERCE_REAL_MODEL_GATE=1 to spend fresh DeepSeek V4 tokens.",
);

test(`uploads six public CSV files and completes a ${NATURAL_QUERY_GATE ? "natural-query " : ""}persistent DeepSeek V4 Commerce run`, async ({
  page,
}) => {
  await mkdir(OUTPUT_DIR, { recursive: true });
  const audit: JsonRecord = {
    schema_version: "1.0",
    gate: NATURAL_QUERY_GATE
      ? "commerce-natural-query-chat-browser"
      : "commerce-persistent-chat-browser",
    natural_query: NATURAL_QUERY_GATE,
    output_directory: path.relative(REPO_ROOT, OUTPUT_DIR),
    configured_alias: "deepseek-reasoner",
    expected_actual_model_identity: "deepseek-v4-flash",
    retry_policy: 0,
    prompt_sha256: sha256(PROMPT),
    input_files: [...FILE_NAMES],
    started_at: new Date().toISOString(),
    passed: false,
  };
  const network: Array<{ method: string; path: string; status: number }> = [];
  const consoleErrors: string[] = [];

  page.on("response", (response) => {
    const url = new URL(response.url());
    if (
      url.pathname.includes("/uploads") ||
      url.pathname.endsWith("/runs/stream")
    ) {
      network.push({
        method: response.request().method(),
        path: url.pathname,
        status: response.status(),
      });
    }
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  try {
    const context = page.context();
    const existingValues = [
      EXISTING_THREAD_ID,
      EXISTING_RUN_ID,
      EXISTING_ACCOUNT_EMAIL,
    ];
    if (NATURAL_QUERY_GATE && existingValues.some(Boolean)) {
      throw new Error(
        "Natural-query gate must create a fresh thread and run; unset all existing-run audit variables",
      );
    }
    const resumeExistingRun =
      !NATURAL_QUERY_GATE && existingValues.every(Boolean);
    if (!resumeExistingRun && existingValues.some(Boolean)) {
      throw new Error(
        "Existing-run audit requires thread ID, run ID, and account email together",
      );
    }
    const accountNonce = resumeExistingRun
      ? `resume-${EXISTING_THREAD_ID}`
      : `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const email = resumeExistingRun
      ? EXISTING_ACCOUNT_EMAIL!
      : `commerce-browser-${accountNonce}@example.com`;
    const commerceWorkspaceId = `wsp_${sha256(accountNonce).slice(0, 32)}`;
    if (resumeExistingRun) {
      const login = await context.request.post(
        `${APP}/api/v1/auth/login/local`,
        {
          form: {
            username: email,
            password: TEST_ACCOUNT_PASSWORD,
          },
        },
      );
      expect(
        login.status(),
        `existing account login failed: ${await login.text()}`,
      ).toBe(200);
    } else {
      const registration = await context.request.post(
        `${APP}/api/v1/auth/register`,
        {
          data: {
            email,
            password: TEST_ACCOUNT_PASSWORD,
          },
        },
      );
      expect(
        registration.status(),
        `throwaway account registration failed: ${await registration.text()}`,
      ).toBe(201);
    }

    const cookies = await context.cookies(APP);
    const accessToken = cookies.find(
      (cookie) => cookie.name === "access_token",
    )?.value;
    const csrfToken = cookies.find(
      (cookie) => cookie.name === "csrf_token",
    )?.value;
    expect(accessToken, "register must set access_token cookie").toBeTruthy();
    expect(csrfToken, "register must set csrf_token cookie").toBeTruthy();

    const authMe = await context.request.get(`${APP}/api/v1/auth/me`);
    expect(
      authMe.status(),
      `/api/v1/auth/me preflight failed: ${await authMe.text()}`,
    ).toBe(200);
    const models = await context.request.get(`${APP}/api/models`);
    expect(
      models.status(),
      `/api/models preflight failed: ${await models.text()}`,
    ).toBe(200);
    const commerceCases = await context.request.get(
      `${APP}/api/commerce/cases?limit=1`,
      {
        headers: {
          "X-Commerce-Workspace-Id": commerceWorkspaceId,
        },
      },
    );
    expect(
      commerceCases.status(),
      `/api/commerce/cases preflight failed: ${await commerceCases.text()}`,
    ).toBe(200);
    audit.auth = {
      account_sha256: sha256(email),
      access_token_cookie_present: true,
      csrf_token_cookie_present: true,
      auth_me_status: authMe.status(),
      models_status: models.status(),
      commerce_cases_status: commerceCases.status(),
      commerce_workspace_id: commerceWorkspaceId,
      resumed_existing_run: resumeExistingRun,
    };

    await context.addCookies([
      {
        name: "locale",
        value: "zh-CN",
        url: APP,
      },
    ]);
    let threadId = EXISTING_THREAD_ID ?? "";
    let runId = EXISTING_RUN_ID ?? "";
    if (resumeExistingRun) {
      await page.goto(
        `/workspace/agents/commerce-agent/chats/${EXISTING_THREAD_ID}`,
      );
      await expect(page).toHaveURL(
        `/workspace/agents/commerce-agent/chats/${EXISTING_THREAD_ID}`,
      );
    } else {
      await page.goto("/workspace/agents/commerce-agent/chats/new");
      await expect(
        page.getByRole("heading", { name: "电商经营诊断", exact: true }),
      ).toBeVisible();

      const fileInput = page.getByLabel("Upload files");
      await expect(fileInput).toHaveCount(1);
      await fileInput.setInputFiles(FILE_PATHS);
      for (const fileName of FILE_NAMES) {
        await expect(page.getByText(fileName, { exact: true })).toBeVisible();
      }
      await page.screenshot({
        path: path.join(OUTPUT_DIR, "01-files-selected-desktop.png"),
        fullPage: true,
      });

      const input = page.getByPlaceholder("今天我能为你做些什么？", {
        exact: true,
      });
      await input.fill(PROMPT);
      const submit = page.getByRole("button", { name: "发送", exact: true });
      await expect(submit).toBeEnabled();
      await submit.click();

      await expect(page).toHaveURL(
        /\/workspace\/agents\/commerce-agent\/chats\/[0-9a-f-]{36}$/u,
        { timeout: 120_000 },
      );
      threadId = new URL(page.url()).pathname.split("/").at(-1) ?? "";
    }
    expect(threadId).toMatch(/^[0-9a-f-]{36}$/u);
    audit.thread_id = threadId;

    const collaborationLink = page.getByRole("link", {
      name: "协作空间",
      exact: true,
    });
    await expect(collaborationLink).toBeVisible({ timeout: 120_000 });
    const collaborationHref = await collaborationLink.getAttribute("href");
    expect(collaborationHref).toBeTruthy();
    const linkedRunId = new URL(
      collaborationHref!,
      page.url(),
    ).searchParams.get("runId");
    if (resumeExistingRun) {
      expect(linkedRunId).toBe(runId);
    } else {
      runId = linkedRunId ?? "";
    }
    expect(runId).toMatch(/^[0-9a-f-]{36}$/u);
    audit.run_id = runId;

    const run = await waitForSuccessfulRun(
      page.request,
      `/api/threads/${threadId}/runs/${runId}`,
      8 * 60_000,
    );
    const runMessages = await getJson(
      page.request,
      `/api/threads/${threadId}/runs/${runId}/messages?limit=200`,
    );
    const runEvents = await getJsonValue(
      page.request,
      `/api/threads/${threadId}/runs/${runId}/events?limit=2000`,
    );
    const tokenUsage = await getJson(
      page.request,
      `/api/threads/${threadId}/token-usage`,
    );
    const taskEnvelope = await getJson(
      page.request,
      `/api/runs/${runId}/subagent-tasks`,
    );
    const tasks = Array.isArray(taskEnvelope)
      ? taskEnvelope
      : Array.isArray(taskEnvelope.data)
        ? taskEnvelope.data
        : [];
    const finalAnswer = extractFinalAiAnswer(runMessages);
    const identities = uniqueStringsByKey(
      [run, runMessages, runEvents, taskEnvelope],
      "actual_model_identity",
    );
    const actualModelIdentities = [...new Set(identities)];
    const configuredModelAliases = Object.keys(asRecord(tokenUsage.by_model));
    const providerRequestIds = uniqueStringsByKey(
      [run, runMessages, runEvents, taskEnvelope],
      "provider_request_id",
    );
    const retryCounts = numericValuesByKey(
      [run, runMessages, runEvents, taskEnvelope],
      "retry_count",
    );

    expect(run.status).toBe("success");
    expect(Number(run.total_tokens)).toBeGreaterThan(0);
    expect(Number(run.llm_call_count)).toBeGreaterThan(0);
    expect(Number(tokenUsage.total_tokens)).toBeGreaterThan(0);
    expect(configuredModelAliases).toContain("deepseek-reasoner");
    expect(actualModelIdentities).toContain("deepseek-v4-flash");
    expect(
      actualModelIdentities.every((identity) =>
        identity.toLowerCase().startsWith("deepseek-v4"),
      ),
    ).toBe(true);
    expect(providerRequestIds.length).toBeGreaterThan(0);
    expect(new Set(providerRequestIds).size).toBe(providerRequestIds.length);
    expect(retryCounts.length).toBeGreaterThan(0);
    expect(retryCounts.every((count) => count === 0)).toBe(true);

    expect(tasks.length).toBeGreaterThanOrEqual(NATURAL_QUERY_GATE ? 2 : 3);
    const taskProfiles = tasks.map((task) => {
      const value = asRecord(task);
      return String(value.profile ?? value.subagent_type);
    });
    expect(taskProfiles).toEqual(
      expect.arrayContaining(
        NATURAL_QUERY_GATE
          ? ["analyst", "verifier"]
          : ["explore", "analyst", "verifier"],
      ),
    );
    expect(
      tasks.every((task) => String(asRecord(task).status) === "completed"),
    ).toBe(true);

    const verifierTasks = tasks.filter((task) => {
      const value = asRecord(task);
      return String(value.profile ?? value.subagent_type) === "verifier";
    });
    expect(verifierTasks.length).toBeGreaterThan(0);
    const completedTaskIds = new Set(
      tasks.map((task) => String(asRecord(task).task_id)),
    );
    expect(
      verifierTasks.every((task) => {
        const sourceRefs = taskSourceRefs(task);
        return sourceRefs.some((sourceRef) => {
          if (!sourceRef.startsWith("task:")) {
            return false;
          }
          return completedTaskIds.has(sourceRef.slice("task:".length));
        });
      }),
    ).toBe(true);

    const requiredTexts = NATURAL_QUERY_GATE
      ? ["卖家", "运输", "处理", "限制"]
      : ["141", "202", "3.55%", "35.15%", "卖家", "运输", "反证", "限制"];
    for (const requiredText of requiredTexts) {
      expect(finalAnswer).toContain(requiredText);
    }
    expect(finalAnswer).toMatch(/[\u4e00-\u9fff]/u);
    expect(finalAnswer).toMatch(/反证|替代解释/u);
    expect(finalAnswer).toMatch(/下一步|建议/u);
    expect(finalAnswer).not.toContain("本次复杂执行已被 Harness 阻止交付");
    expect(finalAnswer).not.toContain("未通过独立子智能体核验");
    expect(finalAnswer).not.toContain("检查持久化任务服务");
    if (NATURAL_QUERY_GATE) {
      expect(finalAnswer).toMatch(
        /默认.{0,16}(近期|窗口)|近期.{0,16}默认|自动选择.{0,16}窗口/su,
      );
      for (const expectedBoundary of [
        "2018-02-01",
        "2018-04-02",
        "2018-06-01",
      ]) {
        expect(finalAnswer).toContain(expectedBoundary);
      }
    } else {
      expect(finalAnswer).not.toContain("春节");
    }
    expect(finalAnswer).not.toMatch(/^\s*\|/mu);

    await page.screenshot({
      path: path.join(OUTPUT_DIR, "02-final-chat-desktop.png"),
      fullPage: true,
    });

    await collaborationLink.click();
    await expect(page).toHaveURL(/commerce-agent\/war-room/u);
    const actors = page.locator("[data-commerce-actor]");
    await expect(actors).toHaveCount(tasks.length);
    await expect(page.locator("[data-commerce-actor-sprite]")).toHaveCount(
      tasks.length,
    );
    await expect(page.locator("[data-commerce-station-sprite]")).toHaveCount(
      tasks.length,
    );
    await actors.nth(0).click();
    await expect(page.locator("[data-commerce-actor-drawer]")).toBeVisible();
    await page.screenshot({
      path: path.join(OUTPUT_DIR, "03-collaboration-desktop.png"),
      fullPage: true,
    });

    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator("[data-commerce-actor]")).toHaveCount(
      tasks.length,
    );
    const viewport = await page.evaluate(() => ({
      contentWidth: document.documentElement.scrollWidth,
      prefersReducedMotion: matchMedia("(prefers-reduced-motion: reduce)")
        .matches,
      viewportWidth: document.documentElement.clientWidth,
    }));
    expect(viewport.contentWidth).toBeLessThanOrEqual(viewport.viewportWidth);
    expect(viewport.prefersReducedMotion).toBe(true);
    await page.screenshot({
      path: path.join(OUTPUT_DIR, "04-collaboration-mobile-reduced-motion.png"),
      fullPage: true,
    });

    if (!resumeExistingRun) {
      expect(
        network.some(
          (item) => item.path.endsWith("/uploads") && item.status === 200,
        ),
      ).toBe(true);
      expect(
        network.some(
          (item) => item.path.endsWith("/runs/stream") && item.status === 200,
        ),
      ).toBe(true);
    }
    expect(consoleErrors).toEqual([]);

    Object.assign(audit, {
      completed_at: new Date().toISOString(),
      passed: true,
      run: {
        status: run.status,
        llm_call_count: run.llm_call_count,
        total_input_tokens: run.total_input_tokens,
        total_output_tokens: run.total_output_tokens,
        total_tokens: run.total_tokens,
        lead_agent_tokens: run.lead_agent_tokens,
        subagent_tokens: run.subagent_tokens,
        middleware_tokens: run.middleware_tokens,
      },
      actual_model_identities: actualModelIdentities,
      configured_model_aliases: configuredModelAliases,
      provider_request_ids: providerRequestIds,
      retry_counts: retryCounts,
      tasks: tasks.map((task) => {
        const value = asRecord(task);
        return {
          task_id: value.task_id,
          profile: value.profile ?? value.subagent_type,
          status: value.status,
          station: value.station,
          source_refs: taskSourceRefs(value),
          created_at: value.created_at,
          started_at: value.started_at,
          completed_at: value.completed_at,
        };
      }),
      final_answer: finalAnswer,
      network,
      console_errors: consoleErrors,
      viewport,
      screenshots: [
        "01-files-selected-desktop.png",
        "02-final-chat-desktop.png",
        "03-collaboration-desktop.png",
        "04-collaboration-mobile-reduced-motion.png",
      ],
    });
    await writeAudit("passed-browser-audit.json", audit);
  } catch (error) {
    Object.assign(audit, {
      completed_at: new Date().toISOString(),
      passed: false,
      error: error instanceof Error ? error.message : String(error),
      network,
      console_errors: consoleErrors,
    });
    await page
      .screenshot({
        path: path.join(OUTPUT_DIR, "failed-browser-state.png"),
        fullPage: true,
      })
      .catch(() => undefined);
    await writeAudit("failed-browser-audit.json", audit);
    throw error;
  }
});

async function getJson(
  request: APIRequestContext,
  url: string,
): Promise<JsonRecord> {
  const value = await getJsonValue(request, url);
  expect(
    value && typeof value === "object" && !Array.isArray(value),
    `${url} must return a JSON object`,
  ).toBe(true);
  return value as JsonRecord;
}

async function getJsonValue(
  request: APIRequestContext,
  url: string,
): Promise<unknown> {
  const response = await request.get(url);
  expect(response.ok(), `${url} returned ${response.status()}`).toBe(true);
  return response.json();
}

async function waitForSuccessfulRun(
  request: APIRequestContext,
  url: string,
  timeoutMs: number,
): Promise<JsonRecord> {
  const deadline = Date.now() + timeoutMs;
  const failedStatuses = new Set([
    "error",
    "failed",
    "interrupted",
    "cancelled",
    "timed_out",
  ]);
  while (Date.now() < deadline) {
    const run = await getJson(request, url);
    const status = typeof run.status === "string" ? run.status : "missing";
    if (status === "success") return run;
    if (failedStatuses.has(status)) {
      throw new Error(`Run entered terminal failure status: ${status}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 1_000));
  }
  throw new Error(`Run did not complete within ${timeoutMs}ms`);
}

function extractFinalAiAnswer(envelope: JsonRecord): string {
  const rows = Array.isArray(envelope.data) ? envelope.data : [];
  const aiRows = rows.filter((row) => {
    const value = asRecord(row);
    return ["llm.ai.response", "ai_message"].includes(String(value.event_type));
  });
  const last = asRecord(aiRows.at(-1));
  const content = asRecord(last.content).content ?? last.content;
  const text = extractText(content).trim();
  expect(text, "final AI answer must be persisted").not.toBe("");
  return text;
}

function extractText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(extractText).join("");
  if (!value || typeof value !== "object") return "";
  const record = asRecord(value);
  if (typeof record.text === "string") return record.text;
  if (record.content !== undefined) return extractText(record.content);
  return "";
}

function uniqueStringsByKey(values: unknown[], key: string): string[] {
  const found: string[] = [];
  walk(values, (record) => {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      found.push(collapseRepeatedString(value.trim()));
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        if (typeof item === "string" && item.trim()) {
          found.push(collapseRepeatedString(item.trim()));
        }
      }
    }
  });
  return [...new Set(found)];
}

function collapseRepeatedString(value: string): string {
  if (value.length < 2) return value;
  const prefixLengths = new Uint32Array(value.length);
  for (let index = 1; index < value.length; index += 1) {
    let candidate = prefixLengths[index - 1] ?? 0;
    while (candidate > 0 && value[index] !== value[candidate]) {
      candidate = prefixLengths[candidate - 1] ?? 0;
    }
    if (value[index] === value[candidate]) candidate += 1;
    prefixLengths[index] = candidate;
  }
  const unitLength = value.length - (prefixLengths[value.length - 1] ?? 0);
  return unitLength < value.length && value.length % unitLength === 0
    ? value.slice(0, unitLength)
    : value;
}

function numericValuesByKey(values: unknown[], key: string): number[] {
  const found: number[] = [];
  walk(values, (record) => {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) found.push(value);
  });
  return found;
}

function walk(value: unknown, visit: (record: JsonRecord) => void): void {
  if (Array.isArray(value)) {
    for (const item of value) walk(item, visit);
    return;
  }
  if (!value || typeof value !== "object") return;
  const record = asRecord(value);
  visit(record);
  for (const item of Object.values(record)) walk(item, visit);
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : {};
}

function taskSourceRefs(task: unknown): string[] {
  const value = asRecord(task);
  const contextPacket = asRecord(value.context_packet);
  const sourceRefs = Array.isArray(contextPacket.source_refs)
    ? contextPacket.source_refs
    : Array.isArray(value.source_refs)
      ? value.source_refs
      : [];
  return sourceRefs.filter(
    (sourceRef): sourceRef is string => typeof sourceRef === "string",
  );
}

function sha256(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

async function writeAudit(name: string, audit: JsonRecord): Promise<void> {
  await writeFile(
    path.join(OUTPUT_DIR, name),
    `${JSON.stringify(audit, null, 2)}\n`,
    "utf8",
  );
}
