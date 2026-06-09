"use client";

import { BotIcon, ShoppingBagIcon } from "lucide-react";

import { type Agent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function AgentWelcome({
  className,
  agent,
  agentName,
}: {
  className?: string;
  agent: Agent | null | undefined;
  agentName: string;
}) {
  const { t } = useI18n();
  const isEcomLaunch = agentName === "ecom-launch";
  const displayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : (agent?.name ?? agentName);
  const description = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeDescription
    : agent?.description;
  const Icon = isEcomLaunch ? ShoppingBagIcon : BotIcon;

  return (
    <div
      className={cn(
        "mx-auto flex w-full flex-col items-center justify-center gap-2 px-8 py-4 text-center",
        className,
      )}
    >
      <div className="bg-primary/10 flex h-12 w-12 items-center justify-center rounded-full">
        <Icon className="text-primary h-6 w-6" />
      </div>
      <div className="text-2xl font-bold">{displayName}</div>
      {description && (
        <p className="text-muted-foreground max-w-sm text-sm">{description}</p>
      )}
    </div>
  );
}
