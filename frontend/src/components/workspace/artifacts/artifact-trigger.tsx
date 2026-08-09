import { FilesIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/workspace/tooltip";
import { useI18n } from "@/core/i18n/hooks";

import { useArtifacts } from "./context";

export const ArtifactTrigger = () => {
  const { t } = useI18n();
  const { artifacts, setOpen: setArtifactsOpen } = useArtifacts();

  if (!artifacts || artifacts.length === 0) {
    return null;
  }
  return (
    <Tooltip content={t.warRoom.artifactFiles(artifacts.length)}>
      <Button
        data-testid="artifact-trigger"
        className="text-muted-foreground hover:text-foreground"
        variant="ghost"
        onClick={() => {
          setArtifactsOpen(true);
        }}
      >
        <FilesIcon />
        {t.common.artifacts}
        <Badge variant="secondary" className="min-w-5 justify-center px-1.5">
          {artifacts.length}
        </Badge>
      </Button>
    </Tooltip>
  );
};
