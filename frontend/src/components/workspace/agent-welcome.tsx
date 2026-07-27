"use client";

import { BotIcon, BriefcaseBusinessIcon, ShoppingBagIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { type Agent } from "@/core/agents";
import { isCommerceAgentName } from "@/core/commerce/agent-ui";
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
  const isCommerceAgent = isCommerceAgentName(agentName);
  const displayName = isEcomLaunch
    ? t.agents.ecomLaunchName
    : isCommerceAgent
      ? t.agents.commerceAgentName
      : (agent?.name ?? agentName);
  const description = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeDescription
    : isCommerceAgent
      ? t.agents.commerceWelcomeDescription
      : agent?.description;
  const Icon = isEcomLaunch
    ? ShoppingBagIcon
    : isCommerceAgent
      ? BriefcaseBusinessIcon
      : BotIcon;
  const badges = isEcomLaunch
    ? t.agents.ecomLaunchWelcomeBadges
    : isCommerceAgent
      ? t.agents.commerceWelcomeBadges
      : [];

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
      <h1 className="text-2xl font-bold">{displayName}</h1>
      {description && (
        <p className="text-muted-foreground max-w-sm text-sm">{description}</p>
      )}
      {badges.length > 0 && (
        <div className="mt-1 flex max-w-md flex-wrap justify-center gap-1.5">
          {badges.map((badge) => (
            <Badge key={badge} variant="secondary" className="font-normal">
              {badge}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
