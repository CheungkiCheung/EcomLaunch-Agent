import { afterEach, describe, expect, test, vi } from "vitest";

import {
  ArtifactLoadError,
  loadArtifactContent,
} from "@/core/artifacts/loader";

describe("loadArtifactContent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test("rejects a missing artifact instead of rendering the 404 JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"detail":"Artifact not found"}', {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      loadArtifactContent({
        filepath: "/mnt/user-data/outputs/launch-war-room.html",
        threadId: "thread-1",
      }),
    ).rejects.toEqual(
      new ArtifactLoadError(404, "/mnt/user-data/outputs/launch-war-room.html"),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(
        "/artifacts/mnt/user-data/outputs/launch-war-room.html",
      ),
      expect.objectContaining({ cache: "no-store", credentials: "include" }),
    );
  });

  test("returns the content of an available artifact", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!doctype html><h1>Launch War Room</h1>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );

    await expect(
      loadArtifactContent({
        filepath: "/mnt/user-data/outputs/launch-war-room.html",
        threadId: "thread-1",
      }),
    ).resolves.toMatchObject({
      content: "<!doctype html><h1>Launch War Room</h1>",
    });
  });
});
