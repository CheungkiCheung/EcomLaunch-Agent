import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import type { NextRequest } from "next/server";

import { resolveMockArtifactPath } from "@/lib/mock-artifact-path";

export async function GET(
  request: NextRequest,
  {
    params,
  }: {
    params: Promise<{
      thread_id: string;
      artifact_path?: string[] | undefined;
    }>;
  },
) {
  const resolvedParams = await params;
  const artifactPath = resolveMockArtifactPath({
    projectRoot: process.cwd(),
    threadId: resolvedParams.thread_id,
    artifactSegments: resolvedParams.artifact_path ?? [],
  });

  if (!artifactPath) {
    return new Response("File not found", { status: 404 });
  }

  try {
    const fileStat = await stat(artifactPath);
    if (!fileStat.isFile()) {
      return new Response("File not found", { status: 404 });
    }

    const body = await readFile(artifactPath);
    if (request.nextUrl.searchParams.get("download") === "true") {
      const headers = new Headers();
      headers.set(
        "Content-Disposition",
        `attachment; filename="${path.basename(artifactPath)}"`,
      );
      return new Response(body, { status: 200, headers });
    }
    if (artifactPath.endsWith(".mp4")) {
      return new Response(body, {
        status: 200,
        headers: { "Content-Type": "video/mp4" },
      });
    }
    return new Response(body, { status: 200 });
  } catch (error) {
    if (
      error instanceof Error &&
      "code" in error &&
      (error.code === "ENOENT" || error.code === "ENOTDIR")
    ) {
      return new Response("File not found", { status: 404 });
    }
    throw error;
  }
}
