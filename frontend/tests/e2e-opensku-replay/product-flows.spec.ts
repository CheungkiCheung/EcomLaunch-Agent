import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const APP = process.env.OPENSKU_REPLAY_FRONTEND_URL ?? "http://localhost:3112";
const fixture = JSON.parse(
  readFileSync(
    join(
      here,
      "../../../backend/tests/fixtures/replay/opensku_product_flows.json",
    ),
    "utf-8",
  ),
) as {
  scenarios: Record<
    "launch" | "growth",
    { assistant_id: string; prompt: string; context: { mode: string } }
  >;
};

const PACK_FILES = [
  "launch-war-room.html",
  "evidence-ledger.json",
  "competitor-table.csv",
  "positioning-brief.md",
  "listing-pack.md",
  "content-pack.md",
  "launch-calendar.csv",
];

async function register(context: BrowserContext) {
  const unique = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  const response = await context.request.post(`${APP}/api/v1/auth/register`, {
    data: {
      email: `opensku-browser-${unique}@example.com`,
      password: ["very-strong", "password", "123"].join("-"),
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  await context.addCookies([{ name: "locale", value: "en-US", url: APP }]);
}

async function preparePage(page: Page) {
  await page.route("**/api/threads/*/suggestions", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ suggestions: [] }),
    }),
  );
}

async function expandAllSteps(page: Page) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const collapsed = page.getByRole("button", { name: /more steps?/i });
    const count = await collapsed.count();
    if (count === 0) {
      return;
    }
    await collapsed.last().click();
  }
  throw new Error("Step groups remained collapsed after 10 expansion attempts");
}

async function getThreadState(context: BrowserContext, threadId: string) {
  const response = await context.request.get(
    `${APP}/api/langgraph/threads/${threadId}/state`,
  );
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as {
    values?: {
      messages?: Array<{
        type?: string;
        content?: unknown;
        tool_calls?: Array<{ name?: string }>;
      }>;
    };
  };
}

function toolNamesFromState(state: Awaited<ReturnType<typeof getThreadState>>) {
  return (state.values?.messages ?? []).flatMap((message) =>
    (message.tool_calls ?? [])
      .map((toolCall) => toolCall.name)
      .filter((name): name is string => typeof name === "string"),
  );
}

function growthUploads() {
  const customers = ["user_id,segment"];
  const assignments = ["user_id,variant"];
  const outcomes = ["user_id,converted"];
  for (let userId = 1; userId <= 200; userId += 1) {
    const variant = userId <= 100 ? "control" : "variant";
    const converted = userId <= 10 || (userId >= 101 && userId <= 120) ? 1 : 0;
    customers.push(`${userId},new`);
    assignments.push(`${userId},${variant}`);
    outcomes.push(`${userId},${converted}`);
  }
  return [
    {
      name: "customers.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(`${customers.join("\n")}\n`),
    },
    {
      name: "assignments.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(`${assignments.join("\n")}\n`),
    },
    {
      name: "outcomes.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(`${outcomes.join("\n")}\n`),
    },
  ];
}

test.describe("OpenSKU product flows (real full stack, replay LLM)", () => {
  test.beforeEach(async ({ context }) => {
    await register(context);
  });

  test("Launch Ultra runs specialists, repairs preflight, delivers 7/7, and syncs War Room", async ({
    page,
    context,
  }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/workspace/agents/ecom-launch/chats/new");

    const flashMode = page
      .getByRole("button")
      .filter({ hasText: /^Flash$/ })
      .first();
    await expect(flashMode).toBeVisible({ timeout: 30_000 });
    await flashMode.click();
    const modeMenu = page.locator("[role='menu']");
    await expect(modeMenu).toBeVisible();
    await modeMenu.getByText("Ultra", { exact: true }).click();
    await expect(
      page
        .getByRole("button")
        .filter({ hasText: /^Ultra$/ })
        .first(),
    ).toBeVisible();
    const textarea = page.getByPlaceholder(/how can i assist|what can i help/i);
    await expect(textarea).toBeVisible();
    await textarea.fill(fixture.scenarios.launch.prompt);
    await textarea.press("Enter");
    await expect(page.getByTestId("streaming-status")).toBeVisible({
      timeout: 30_000,
    });

    await expect(
      page.getByRole("heading", {
        name: "Market Researcher",
        exact: true,
      }),
    ).toBeVisible({
      timeout: 90_000,
    });
    await expect(
      page.getByRole("heading", { name: "Offer Architect", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Asset Studio", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("7/7 core files ready", { exact: true }),
    ).toBeVisible({
      timeout: 90_000,
    });

    await expandAllSteps(page);
    await expect(
      page.getByText(
        "Repair invalid evidence JSON from preflight observation",
        {
          exact: true,
        },
      ),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Add the missing validation action row named by preflight",
        {
          exact: true,
        },
      ),
    ).toBeVisible();

    // Ultra can emit an initial pack and a final pack after the deterministic
    // repair loop. Assert against the final delivery card.
    const deliveryPack = page.getByTestId("artifact-delivery").last();
    await deliveryPack.scrollIntoViewIfNeeded();
    await expect(deliveryPack).toBeVisible();
    for (const name of PACK_FILES) {
      // The artifact preview drawer may also render the selected filename in
      // a hidden combobox/list. Scope this assertion to the visible delivery
      // card so we verify the user-facing Launch Validation Pack itself.
      const deliveredFile = deliveryPack.getByText(name, { exact: true });
      await deliveredFile.scrollIntoViewIfNeeded();
      await expect(deliveredFile).toBeVisible();
    }

    const threadId = new URL(page.url()).pathname.split("/").at(-1);
    expect(threadId).toBeTruthy();
    expect(threadId).not.toBe("new");
    const state = await getThreadState(context, threadId!);
    const toolNames = toolNamesFromState(state);
    expect(toolNames.slice(0, 3)).toEqual(["task", "task", "task"]);
    expect(toolNames.filter((name) => name === "write_file")).toHaveLength(7);
    expect(toolNames.filter((name) => name === "str_replace")).toHaveLength(2);
    expect(toolNames.filter((name) => name === "present_files")).toHaveLength(
      2,
    );
    expect(JSON.stringify(state)).toContain(
      "evidence-ledger.json is not valid readable JSON",
    );
    expect(JSON.stringify(state)).toContain(
      "launch-calendar.csv must contain a header and at least one non-empty data row",
    );
    const artifact = await context.request.get(
      `${APP}/api/threads/${threadId}/artifacts/mnt/user-data/outputs/evidence-ledger.json`,
    );
    expect(artifact.status(), await artifact.text()).toBe(200);
    expect((await artifact.json()).entries[0].label).toBe("observed_public");

    const warRoom = await context.newPage();
    await warRoom.setViewportSize({ width: 1440, height: 900 });
    await warRoom.goto("/workspace/war-room");
    await expect(
      warRoom.getByRole("heading", { name: "OpenSKU War Room" }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      warRoom.getByTestId("war-room-artifact-count").getByText("7", {
        exact: true,
      }),
    ).toBeVisible({ timeout: 30_000 });
    await expect(warRoom.locator("canvas")).toBeVisible();
    await warRoom.close();
  });

  test("Growth Analyst uploads three CSVs, joins them, and returns the A/B ship decision", async ({
    page,
    context,
  }) => {
    await preparePage(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/workspace/agents/data-inspector/chats/new");

    const textarea = page.getByPlaceholder(/how can i assist|what can i help/i);
    await expect(textarea).toBeVisible({ timeout: 30_000 });
    await page.getByLabel("Upload files").setInputFiles(growthUploads());
    for (const name of ["customers.csv", "assignments.csv", "outcomes.csv"]) {
      await expect(page.getByText(name, { exact: true })).toBeVisible();
    }

    await textarea.fill(fixture.scenarios.growth.prompt);
    await textarea.press("Enter");
    await expect(
      page.getByText("SHIP WITH MONITORING", { exact: false }),
    ).toBeVisible({
      timeout: 90_000,
    });
    await expect(page.getByText("p = 0.0477", { exact: false })).toBeVisible();
    await expect(page.getByText("+10.00 pp", { exact: false })).toBeVisible();
    await expect(
      page.getByText("+0.20 to +19.80 pp", { exact: false }),
    ).toBeVisible();
    await expect(
      page.getByText("SRM is not detected", { exact: false }),
    ).toBeVisible();

    await expandAllSteps(page);
    await expect(
      page.getByText('Use "inspect_data" tool', { exact: true }).first(),
    ).toBeVisible();
    await expect(
      page.getByText('Use "query_data" tool', { exact: true }).first(),
    ).toBeVisible();

    const threadId = new URL(page.url()).pathname.split("/").at(-1);
    expect(threadId).toBeTruthy();
    expect(threadId).not.toBe("new");
    const state = await getThreadState(context, threadId!);
    expect(toolNamesFromState(state)).toEqual([
      "inspect_data",
      "query_data",
      "analyze_ab_test",
    ]);
  });
});
