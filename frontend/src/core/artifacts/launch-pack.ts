export const LAUNCH_PACK_FILENAMES = [
  "launch-war-room.html",
  "evidence-ledger.json",
  "competitor-table.csv",
  "positioning-brief.md",
  "listing-pack.md",
  "content-pack.md",
  "launch-calendar.csv",
] as const;

export const LAUNCH_PACK_OUTPUT_PREFIX = "/mnt/user-data/outputs/";

export const LAUNCH_PACK_FILEPATHS = LAUNCH_PACK_FILENAMES.map(
  (filename) => `${LAUNCH_PACK_OUTPUT_PREFIX}${filename}`,
);

export function isLaunchPackFile(filepath: string) {
  return LAUNCH_PACK_FILENAMES.includes(
    filepath.split("/").at(-1) as (typeof LAUNCH_PACK_FILENAMES)[number],
  );
}

export function isCompleteLaunchPack(files: string[]) {
  const names = new Set(files.map((filepath) => filepath.split("/").at(-1)));
  return LAUNCH_PACK_FILENAMES.every((filename) => names.has(filename));
}
