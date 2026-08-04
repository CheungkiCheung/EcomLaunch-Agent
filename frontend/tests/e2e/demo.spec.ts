import { expect, test } from "@playwright/test";

test.describe("Credential-free English demo", () => {
  test("shows the recorded War Room, agent states, and deliverables without API calls", async ({
    page,
  }) => {
    const applicationApiRequests: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (
        url.pathname.startsWith("/api/") ||
        url.pathname.startsWith("/mock/api/")
      ) {
        applicationApiRequests.push(url.pathname);
      }
    });

    await page.goto("/demo");

    await expect(page.getByTestId("recorded-demo-notice")).toContainText(
      "no live agents are running",
    );
    await expect(page.getByTestId("demo-war-room")).toBeVisible();
    await expect(
      page.getByTestId("demo-agent-status").locator("[data-agent-id]"),
    ).toHaveCount(6);
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "Launch Director",
    );
    await expect(page.getByTestId("demo-agent-status")).toContainText(
      "Growth Analyst",
    );
    await expect(
      page.getByTestId("demo-deliverables").getByRole("link"),
    ).toHaveCount(4);

    expect(applicationApiRequests).toEqual([]);
  });

  test("exposes the sample launch decision as a real file", async ({
    request,
  }) => {
    const response = await request.get(
      "/demo/opensku-coffee-mug/launch-decision.md",
    );

    expect(response.ok()).toBeTruthy();
    const content = await response.text();
    expect(content).toContain("VALIDATE BEFORE COMMITTING");
    expect(content).toContain("Recorded OpenSKU demo fixture");
  });
});
