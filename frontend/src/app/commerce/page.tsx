import { CommerceMasterShell } from "@/components/commerce/master-shell";
import { env } from "@/env";

export default function CommerceWorkspacePage() {
  return (
    <CommerceMasterShell
      workspaceId={env.NEXT_PUBLIC_COMMERCE_WORKSPACE_ID ?? null}
      actorId={env.NEXT_PUBLIC_COMMERCE_ACTOR_ID ?? null}
    />
  );
}
