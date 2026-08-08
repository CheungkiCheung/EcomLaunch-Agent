import path from "node:path";

const SAFE_THREAD_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

export function resolveMockArtifactPath({
  projectRoot,
  threadId,
  artifactSegments,
}: {
  projectRoot: string;
  threadId: string;
  artifactSegments: string[];
}): string | null {
  if (
    !SAFE_THREAD_ID.test(threadId) ||
    threadId === "." ||
    threadId === ".." ||
    artifactSegments.length < 2 ||
    artifactSegments[0] !== "mnt" ||
    artifactSegments.some(
      (segment) =>
        segment.length === 0 ||
        segment === "." ||
        segment === ".." ||
        segment.includes("\0") ||
        segment.includes("/") ||
        segment.includes("\\"),
    )
  ) {
    return null;
  }

  const threadRoot = path.resolve(
    projectRoot,
    "public",
    "demo",
    "threads",
    threadId,
  );
  const candidate = path.resolve(threadRoot, ...artifactSegments.slice(1));
  const relative = path.relative(threadRoot, candidate);

  if (
    relative.length === 0 ||
    relative.startsWith(`..${path.sep}`) ||
    relative === ".." ||
    path.isAbsolute(relative)
  ) {
    return null;
  }

  return candidate;
}
