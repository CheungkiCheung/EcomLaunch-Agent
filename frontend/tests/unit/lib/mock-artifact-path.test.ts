import path from "node:path";

import { describe, expect, it } from "vitest";

import { resolveMockArtifactPath } from "@/lib/mock-artifact-path";

const PROJECT_ROOT = path.resolve("/tmp/opensku-test-project");

describe("resolveMockArtifactPath", () => {
  it("resolves an artifact below the selected demo thread", () => {
    expect(
      resolveMockArtifactPath({
        projectRoot: PROJECT_ROOT,
        threadId: "opensku-coffee-mug",
        artifactSegments: ["mnt", "user-data", "outputs", "report.html"],
      }),
    ).toBe(
      path.join(
        PROJECT_ROOT,
        "public/demo/threads/opensku-coffee-mug/user-data/outputs/report.html",
      ),
    );
  });

  it.each([
    ["parent traversal", ["mnt", "..", "secret.txt"]],
    ["nested parent traversal", ["mnt", "user-data", "..", "secret.txt"]],
    ["embedded slash", ["mnt", "user-data/../../secret.txt"]],
    ["embedded backslash", ["mnt", "user-data\\..\\secret.txt"]],
    ["null byte", ["mnt", "report.html\0.txt"]],
    ["missing mnt prefix", ["user-data", "outputs", "report.html"]],
  ])("rejects %s", (_label, artifactSegments) => {
    expect(
      resolveMockArtifactPath({
        projectRoot: PROJECT_ROOT,
        threadId: "opensku-coffee-mug",
        artifactSegments,
      }),
    ).toBeNull();
  });

  it.each(["../other-thread", "..", ".", "/absolute", "nested/thread"])(
    "rejects unsafe thread id %s",
    (threadId) => {
      expect(
        resolveMockArtifactPath({
          projectRoot: PROJECT_ROOT,
          threadId,
          artifactSegments: ["mnt", "user-data", "outputs", "report.html"],
        }),
      ).toBeNull();
    },
  );

  it("rejects the thread directory itself", () => {
    expect(
      resolveMockArtifactPath({
        projectRoot: PROJECT_ROOT,
        threadId: "opensku-coffee-mug",
        artifactSegments: ["mnt"],
      }),
    ).toBeNull();
  });
});
