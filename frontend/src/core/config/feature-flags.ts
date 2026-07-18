import { env } from "@/env";

export function parseBooleanFeatureFlag(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

export const featureFlags = Object.freeze({
  commerceCaseAgent: parseBooleanFeatureFlag(
    env.NEXT_PUBLIC_COMMERCE_CASE_AGENT_ENABLED,
  ),
});
