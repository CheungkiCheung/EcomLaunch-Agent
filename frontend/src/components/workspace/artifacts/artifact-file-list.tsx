import {
  DownloadIcon,
  EyeIcon,
  LoaderIcon,
  PackageCheckIcon,
  PackageIcon,
} from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { isCompleteLaunchPack } from "@/core/artifacts/launch-pack";
import { urlOfArtifact } from "@/core/artifacts/utils";
import { useI18n } from "@/core/i18n/hooks";
import { installSkill } from "@/core/skills/api";
import {
  getFileExtensionDisplayName,
  getFileIcon,
  getFileName,
} from "@/core/utils/files";
import { cn } from "@/lib/utils";

import { useArtifacts } from "./context";

export function ArtifactFileList({
  className,
  files,
  threadId,
  variant = "list",
}: {
  className?: string;
  files: string[];
  threadId: string;
  variant?: "list" | "delivery";
}) {
  const { t } = useI18n();
  const { select: selectArtifact, setOpen } = useArtifacts();
  const [installingFile, setInstallingFile] = useState<string | null>(null);

  const handleClick = useCallback(
    (filepath: string) => {
      selectArtifact(filepath);
      setOpen(true);
    },
    [selectArtifact, setOpen],
  );

  const handleInstallSkill = useCallback(
    async (e: React.MouseEvent, filepath: string) => {
      e.stopPropagation();
      e.preventDefault();

      if (installingFile) return;

      setInstallingFile(filepath);
      try {
        const result = await installSkill({
          thread_id: threadId,
          path: filepath,
        });
        if (result.success) {
          toast.success(result.message);
        } else {
          toast.error(result.message || "Failed to install skill");
        }
      } catch (error) {
        console.error("Failed to install skill:", error);
        toast.error("Failed to install skill");
      } finally {
        setInstallingFile(null);
      }
    },
    [threadId, installingFile],
  );

  const uniqueFiles = [...new Set(files)];
  const completeLaunchPack = isCompleteLaunchPack(uniqueFiles);
  const primaryFile =
    uniqueFiles.find((file) => file.endsWith("/launch-war-room.html")) ??
    uniqueFiles[0];

  const fileList = (
    <ul
      className={cn(
        "flex w-full flex-col gap-4",
        variant === "delivery" &&
          "grid grid-cols-[repeat(auto-fit,minmax(min(100%,18rem),1fr))] gap-2",
        className,
      )}
    >
      {uniqueFiles.map((file) => (
        <Card
          key={file}
          className={cn(
            "hover:bg-muted/40 relative cursor-pointer p-3 transition-colors",
            variant === "delivery" && "py-2",
          )}
          onClick={() => handleClick(file)}
        >
          <CardHeader className="grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 pr-2 pl-1">
            <CardTitle className="relative min-w-0 pl-8 leading-tight [overflow-wrap:anywhere] break-words">
              <div className="min-w-0">{getFileName(file)}</div>
              <div className="absolute top-2 -left-0.5">
                {getFileIcon(file, "size-6")}
              </div>
            </CardTitle>
            <CardDescription className="min-w-0 pl-8 text-xs">
              {getFileExtensionDisplayName(file)}
            </CardDescription>
            <CardAction className="row-span-1 self-center">
              {file.endsWith(".skill") && (
                <Button
                  variant="ghost"
                  disabled={installingFile === file}
                  onClick={(e) => handleInstallSkill(e, file)}
                >
                  {installingFile === file ? (
                    <LoaderIcon className="size-4 animate-spin" />
                  ) : (
                    <PackageIcon className="size-4" />
                  )}
                  {t.common.install}
                </Button>
              )}
              <Button variant="ghost" asChild>
                <a
                  href={urlOfArtifact({
                    filepath: file,
                    threadId: threadId,
                    download: true,
                  })}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  <DownloadIcon className="size-4" />
                  {t.common.download}
                </a>
              </Button>
            </CardAction>
          </CardHeader>
        </Card>
      ))}
    </ul>
  );

  if (variant !== "delivery") {
    return fileList;
  }

  return (
    <section
      data-testid="artifact-delivery"
      className="border-border/80 bg-card overflow-hidden rounded-xl border shadow-sm"
    >
      <header className="border-border/70 bg-muted/25 flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="bg-primary/10 text-primary flex size-9 shrink-0 items-center justify-center rounded-lg">
            <PackageCheckIcon className="size-5" />
          </div>
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold">
              {completeLaunchPack
                ? "Launch Validation Pack"
                : t.common.artifacts}
            </h3>
            <p className="text-muted-foreground text-xs">
              {t.warRoom.artifactFiles(uniqueFiles.length)}
            </p>
          </div>
        </div>
        {primaryFile && (
          <Button
            type="button"
            variant="default"
            size="sm"
            onClick={() => handleClick(primaryFile)}
          >
            <EyeIcon className="size-4" />
            {t.common.preview}
            {completeLaunchPack ? " War Room" : ""}
          </Button>
        )}
      </header>
      <div className="p-3">{fileList}</div>
    </section>
  );
}
