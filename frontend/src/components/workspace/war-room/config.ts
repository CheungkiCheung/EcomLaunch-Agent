import type { Translations } from "@/core/i18n/locales/types";

import type { WarRoomActorConfig } from "./types";

export const WAR_ROOM_ACTORS: WarRoomActorConfig[] = [
  {
    id: "ecom-launch",
    team: "ecom-launch",
    name: "OpenSKU Launch Team",
    shortName: "Director",
    role: "Launch Director",
    description:
      "Breaks down the brief, coordinates specialists, and assembles the final decision pack.",
    accent: "#f2b35f",
    glow: 0xf2b35f,
    position: { x: 47, y: 65, workX: 47, workY: 62 },
  },
  {
    id: "market-voc-researcher",
    team: "ecom-launch",
    name: "Market Researcher",
    shortName: "Market",
    role: "Market & VOC Researcher",
    description:
      "Studies competitors, market signals, and real customer language.",
    accent: "#e98b63",
    glow: 0xe98b63,
    position: { x: 33, y: 42, workX: 29, workY: 36 },
  },
  {
    id: "offer-architect",
    team: "ecom-launch",
    name: "Offer Architect",
    shortName: "Offer",
    role: "Offer Architect",
    description:
      "Shapes positioning, pricing hypotheses, validation tests, and launch strategy.",
    accent: "#d87855",
    glow: 0xd87855,
    position: { x: 21, y: 57, workX: 16, workY: 53 },
  },
  {
    id: "asset-studio",
    team: "ecom-launch",
    name: "Asset Studio",
    shortName: "Assets",
    role: "Asset Studio",
    description:
      "Creates listing copy, content angles, scripts, and launch assets.",
    accent: "#ca6d67",
    glow: 0xca6d67,
    position: { x: 43, y: 69, workX: 39, workY: 66 },
  },
  {
    id: "evidence-checker",
    team: "ecom-launch",
    name: "Evidence Checker",
    shortName: "Evidence",
    role: "Evidence Checker",
    description:
      "Checks sources, factual boundaries, conclusions, and delivery quality.",
    accent: "#b76555",
    glow: 0xb76555,
    position: { x: 62, y: 42, workX: 63, workY: 35 },
  },
  {
    id: "data-inspector",
    team: "data-inspector",
    name: "Growth Analyst",
    shortName: "Growth",
    role: "Data & Growth Analyst",
    description:
      "Explains uploaded business data, anomalies, and practical growth opportunities.",
    accent: "#78a99d",
    glow: 0x78a99d,
    position: { x: 80, y: 60, workX: 80, workY: 51 },
  },
];

export function localizeWarRoomActors(
  actors: Translations["warRoom"]["actors"],
): WarRoomActorConfig[] {
  return WAR_ROOM_ACTORS.map((actor) => ({
    ...actor,
    ...actors[actor.id],
  }));
}

export const WAR_ROOM_POLL_INTERVAL_MS = 2500;
