"use client";

import {
  Application,
  Assets,
  Container,
  Graphics,
  Sprite,
  Text,
  Texture,
} from "pixi.js";
import { useEffect, useMemo, useRef } from "react";

import type {
  LaunchCrewAgent,
  LaunchCrewArtifact,
  LaunchCrewRole,
} from "./launch-crew-activity-model";
import { WAR_ROOM_PROPS, warRoomCharacterSprite } from "./war-room-assets";
import type { WarRoomAgentMotion } from "./war-room-motion";
import {
  AGENT_HOME_WAYPOINTS,
  WAR_ROOM_WAYPOINTS,
  type WarRoomPoint,
} from "./war-room-motion";

type WarRoomCanvasStageProps = {
  agents: LaunchCrewAgent[];
  artifacts: LaunchCrewArtifact[];
  motions: WarRoomAgentMotion[];
  selectedAgentId: LaunchCrewAgent["id"];
  onSelectAgent: (id: LaunchCrewAgent["id"]) => void;
};

type RenderedAgent = {
  agent: LaunchCrewAgent;
  motion: WarRoomAgentMotion;
  sprite: ReturnType<typeof warRoomCharacterSprite>;
};

type MovingAgentNode = {
  id: LaunchCrewRole;
  sprite: Sprite;
  label: Text;
  ring: Graphics;
  pathKey: string;
  path: Array<{ x: number; y: number }>;
  pathIndex: number;
  targetX: number;
  targetY: number;
  selected: boolean;
};

type ArtifactDropNode = {
  container: Container;
  baseY: number;
};

type CarriedPackageNode = {
  container: Container;
  agentId: LaunchCrewRole;
  artifactName: string;
};

type EffectNode = {
  graphic: Graphics;
  kind: "station-active" | "station-blocked" | "artifact-pulse";
  phase: number;
};

type PixiStageState = {
  app: Application;
  root: Container;
  lineLayer: Graphics;
  effectLayer: Container;
  propLayer: Container;
  artifactLayer: Container;
  agentLayer: Container;
  textureCache: Map<string, Texture>;
  agents: Map<LaunchCrewRole, MovingAgentNode>;
  artifacts: Map<string, ArtifactDropNode>;
  carriedPackages: Map<LaunchCrewRole, CarriedPackageNode>;
  effects: Map<string, EffectNode>;
  propsRendered: boolean;
  destroyed: boolean;
};

const STAGE_WIDTH = 1000;
const STAGE_HEIGHT = 700;

function stagePoint(point: WarRoomPoint) {
  return {
    x: (point.x / 100) * STAGE_WIDTH,
    y: (point.y / 100) * STAGE_HEIGHT,
  };
}

function fitRootToContainer(root: Container, container: HTMLElement) {
  const scale = Math.min(
    container.clientWidth / STAGE_WIDTH,
    container.clientHeight / STAGE_HEIGHT,
  );
  root.scale.set(scale);
  root.x = (container.clientWidth - STAGE_WIDTH * scale) / 2;
  root.y = (container.clientHeight - STAGE_HEIGHT * scale) / 2;
}

function drawRoomShell(root: Container) {
  const floor = new Graphics();
  floor.rect(0, 0, STAGE_WIDTH, STAGE_HEIGHT).fill(0x223038);
  floor.rect(0, 0, STAGE_WIDTH, 105).fill(0x3a464d);
  floor.rect(185, 24, 630, 58).stroke({ color: 0x151e20, width: 4 });
  floor.rect(190, 29, 620, 48).fill({ color: 0xa8bbc0, alpha: 0.14 });

  for (let x = 0; x <= STAGE_WIDTH; x += 32) {
    floor.moveTo(x, 0).lineTo(x, STAGE_HEIGHT).stroke({
      color: 0xffffff,
      alpha: 0.055,
      width: 1,
    });
  }
  for (let y = 0; y <= STAGE_HEIGHT; y += 32) {
    floor.moveTo(0, y).lineTo(STAGE_WIDTH, y).stroke({
      color: 0xffffff,
      alpha: 0.055,
      width: 1,
    });
  }

  const vignette = new Graphics();
  vignette.rect(0, 0, STAGE_WIDTH, STAGE_HEIGHT).stroke({
    color: 0x0f1715,
    width: 8,
    alpha: 0.76,
  });

  root.addChild(floor, vignette);
}

function drawSignalLines(lineLayer: Graphics, motions: WarRoomAgentMotion[]) {
  lineLayer.clear();
  for (const motion of motions) {
    if (motion.id === "launch-director") continue;
    const points = [motion.previousPosition, ...motion.path].map(stagePoint);
    for (let index = 0; index < points.length - 1; index += 1) {
      const start = points[index];
      const end = points[index + 1];
      if (!start || !end) continue;
      lineLayer
        .moveTo(start.x, start.y)
        .lineTo(end.x, end.y)
        .stroke({
          color: 0x78ffd4,
          width: motion.state === "roaming" ? 1 : 2,
          alpha: motion.state === "roaming" ? 0.18 : 0.62,
        });
    }
  }
}

function artifactDropPoint(index: number) {
  const base = stagePoint(WAR_ROOM_WAYPOINTS.artifactConveyor);
  return {
    x: base.x - 38 + index * 38,
    y: base.y + 20 + (index % 2) * 12,
  };
}

function createArtifactDrop(artifact: LaunchCrewArtifact, index: number) {
  const point = artifactDropPoint(index);
  const container = new Container();
  container.x = point.x;
  container.y = point.y - 18;
  container.alpha = 0.92;
  container.zIndex = Math.round(point.y) + 8;

  const packageBody = new Graphics();
  packageBody
    .roundRect(-16, -16, 32, 24, 4)
    .fill(artifact.required ? 0xd6b36c : 0x0f766e)
    .stroke({ color: 0x111827, width: 3 });
  packageBody.rect(-2, -16, 4, 24).fill({ color: 0x8a6d3b, alpha: 0.6 });
  packageBody.rect(-16, -4, 32, 4).fill({ color: 0x8a6d3b, alpha: 0.6 });

  const label = new Text({
    text: artifact.label,
    style: {
      fontFamily: "monospace",
      fontSize: 9,
      fontWeight: "900",
      fill: 0xf8fafc,
      stroke: { color: 0x101714, width: 3 },
    },
  });
  label.anchor.set(0.5, 0);
  label.y = 10;

  container.addChild(packageBody, label);
  return container;
}

function createCarriedPackage(artifact: LaunchCrewArtifact) {
  const container = new Container();
  container.alpha = 0.96;

  const packageBody = new Graphics();
  packageBody
    .roundRect(-12, -12, 24, 18, 4)
    .fill(artifact.required ? 0xe5c879 : 0x2dd4bf)
    .stroke({ color: 0x111827, width: 3 });
  packageBody.rect(-2, -12, 4, 18).fill({ color: 0x7c5f2d, alpha: 0.55 });
  packageBody.rect(-12, -3, 24, 4).fill({ color: 0x7c5f2d, alpha: 0.55 });

  const label = new Text({
    text: "pkg",
    style: {
      fontFamily: "monospace",
      fontSize: 8,
      fontWeight: "900",
      fill: 0x10201c,
    },
  });
  label.anchor.set(0.5, 0);
  label.y = 8;

  container.addChild(packageBody, label);
  return container;
}

function effectKey(kind: EffectNode["kind"], id: string) {
  return `${kind}:${id}`;
}

function drawStationEffect(
  graphic: Graphics,
  agent: LaunchCrewAgent,
  alpha = 0.44,
) {
  const point = stagePoint(WAR_ROOM_WAYPOINTS[AGENT_HOME_WAYPOINTS[agent.id]]);
  const isBlocked = agent.status === "error";
  graphic.clear();
  graphic.ellipse(point.x, point.y - 16, 70, 25).fill({
    color: isBlocked ? 0xef4444 : 0x67ffd6,
    alpha: isBlocked ? alpha * 0.72 : alpha * 0.38,
  });
  graphic.ellipse(point.x, point.y - 16, 78, 29).stroke({
    color: isBlocked ? 0xfca5a5 : 0x78ffd4,
    alpha,
    width: isBlocked ? 4 : 3,
  });
  graphic.zIndex = Math.round(point.y) - 35;
}

function drawArtifactPulse(graphic: Graphics, alpha = 0.5, scale = 1) {
  const point = stagePoint(WAR_ROOM_WAYPOINTS.artifactConveyor);
  graphic.clear();
  graphic
    .roundRect(
      point.x - 78 * scale,
      point.y - 28 * scale,
      156 * scale,
      46 * scale,
      8,
    )
    .stroke({
      color: 0xf8d36a,
      alpha,
      width: 3,
    });
  graphic
    .roundRect(
      point.x - 66 * scale,
      point.y - 20 * scale,
      132 * scale,
      30 * scale,
      6,
    )
    .fill({ color: 0xf8d36a, alpha: alpha * 0.12 });
  graphic.zIndex = Math.round(point.y) - 10;
}

async function loadTexture(cache: Map<string, Texture>, src: string) {
  const cached = cache.get(src);
  if (cached) return cached;

  const texture = await Assets.load<Texture>(src);
  cache.set(src, texture);
  return texture;
}

function fitSprite(
  sprite: Sprite,
  size: { width: number; height: number },
  point: WarRoomPoint,
  offsets = { x: 0, y: 0 },
) {
  const position = stagePoint(point);
  sprite.width = size.width;
  sprite.height = size.height;
  sprite.anchor.set(0.5, 1);
  sprite.x = position.x + offsets.x;
  sprite.y = position.y + offsets.y;
  sprite.zIndex = Math.round(sprite.y);
}

function pointWithOffset(point: WarRoomPoint, offsets = { x: 0, y: 0 }) {
  const position = stagePoint(point);
  return {
    x: position.x + offsets.x,
    y: position.y + offsets.y,
  };
}

function stagePath(points: WarRoomPoint[]) {
  return points.map(stagePoint);
}

function pathKey(points: WarRoomPoint[]) {
  return points.map((point) => `${point.x}:${point.y}`).join("|");
}

function createAgentLabel(label: string, selected: boolean) {
  const text = new Text({
    text: label,
    style: {
      fontFamily: "monospace",
      fontSize: selected ? 12 : 10,
      fontWeight: "900",
      fill: selected ? 0xeafffb : 0xcffcf1,
      stroke: { color: 0x101714, width: selected ? 4 : 3 },
    },
  });
  text.anchor.set(0.5, 0);
  return text;
}

function drawSelectionRing(ring: Graphics, x: number, y: number) {
  ring.clear();
  ring.ellipse(x, y - 2, 54, 18).stroke({
    color: 0x67ffd6,
    alpha: 0.88,
    width: 3,
  });
  ring.ellipse(x, y, 38, 10).fill({ color: 0x67ffd6, alpha: 0.1 });
  ring.zIndex = Math.round(y) - 1;
}

function updateAgentNodePosition(node: MovingAgentNode) {
  node.sprite.zIndex = Math.round(node.sprite.y) + 20;
  node.label.x = node.sprite.x;
  node.label.y = node.sprite.y + (node.selected ? 8 : 14);
  node.label.zIndex = node.sprite.zIndex + 2;
  node.label.visible = node.selected;
  node.ring.visible = node.selected;
  if (node.selected) {
    drawSelectionRing(node.ring, node.sprite.x, node.sprite.y);
  }
}

function updateCarriedPackagePosition(
  carriedPackage: CarriedPackageNode,
  agent: MovingAgentNode,
) {
  const conveyor = stagePoint(WAR_ROOM_WAYPOINTS.artifactConveyor);
  const distanceToConveyor = Math.hypot(
    agent.sprite.x - conveyor.x,
    agent.sprite.y - conveyor.y,
  );
  carriedPackage.container.x = agent.sprite.x + 22;
  carriedPackage.container.y = agent.sprite.y - 44;
  carriedPackage.container.alpha =
    distanceToConveyor < 44 ? 0.24 : 0.78 + Math.sin(agent.sprite.x / 18) * 0.1;
  carriedPackage.container.zIndex = agent.sprite.zIndex + 1;
}

function tickAgentNodes(state: PixiStageState) {
  const time = state.app.ticker.lastTime / 280;
  let artifactIndex = 0;
  for (const artifact of state.artifacts.values()) {
    artifact.container.y = artifact.baseY + Math.sin(time + artifactIndex) * 2;
    artifactIndex += 1;
  }

  for (const effect of state.effects.values()) {
    const wave = (Math.sin(time + effect.phase) + 1) / 2;
    if (effect.kind === "artifact-pulse") {
      drawArtifactPulse(effect.graphic, 0.22 + wave * 0.34, 1 + wave * 0.05);
    } else {
      effect.graphic.alpha = 0.58 + wave * 0.34;
    }
  }

  for (const node of state.agents.values()) {
    const waypoint = node.path[node.pathIndex] ?? {
      x: node.targetX,
      y: node.targetY,
    };
    node.targetX = waypoint.x;
    node.targetY = waypoint.y;
    node.sprite.x += (node.targetX - node.sprite.x) * 0.12;
    node.sprite.y += (node.targetY - node.sprite.y) * 0.12;
    if (Math.abs(node.targetX - node.sprite.x) < 0.25) {
      node.sprite.x = node.targetX;
    }
    if (Math.abs(node.targetY - node.sprite.y) < 0.25) {
      node.sprite.y = node.targetY;
    }
    if (
      node.sprite.x === node.targetX &&
      node.sprite.y === node.targetY &&
      node.pathIndex < node.path.length - 1
    ) {
      node.pathIndex += 1;
    }
    updateAgentNodePosition(node);
  }

  for (const carriedPackage of state.carriedPackages.values()) {
    const agent = state.agents.get(carriedPackage.agentId);
    if (!agent) continue;
    updateCarriedPackagePosition(carriedPackage, agent);
  }
  state.effectLayer.sortChildren();
  state.artifactLayer.sortChildren();
  state.agentLayer.sortChildren();
}

function useRenderedAgents(
  agents: LaunchCrewAgent[],
  motions: WarRoomAgentMotion[],
) {
  return useMemo(() => {
    const motionByAgent = new Map(motions.map((motion) => [motion.id, motion]));
    return agents.flatMap((agent) => {
      const motion = motionByAgent.get(agent.id);
      if (!motion) return [];
      return [
        {
          agent,
          motion,
          sprite: warRoomCharacterSprite(agent, motion),
        },
      ];
    });
  }, [agents, motions]);
}

async function renderStaticProps(state: PixiStageState) {
  if (state.propsRendered) return;
  for (const prop of WAR_ROOM_PROPS) {
    const texture = await loadTexture(state.textureCache, prop.src);
    if (state.destroyed) return;
    const sprite = new Sprite(texture);
    fitSprite(
      sprite,
      { width: prop.width, height: prop.height },
      WAR_ROOM_WAYPOINTS[prop.waypoint],
      { x: prop.offsetX, y: prop.offsetY },
    );
    sprite.zIndex -= 30;
    state.propLayer.addChild(sprite);
  }
  state.propLayer.sortChildren();
  state.propsRendered = true;
}

function syncArtifactDrops(
  state: PixiStageState,
  artifacts: LaunchCrewArtifact[],
) {
  const readyArtifacts = artifacts
    .filter((artifact) => artifact.status === "ready")
    .slice(0, 5);
  const liveIds = new Set(readyArtifacts.map((artifact) => artifact.filepath));

  for (const [id, drop] of state.artifacts) {
    if (liveIds.has(id)) continue;
    drop.container.destroy({ children: true });
    state.artifacts.delete(id);
  }

  readyArtifacts.forEach((artifact, index) => {
    let drop = state.artifacts.get(artifact.filepath);
    if (!drop) {
      const container = createArtifactDrop(artifact, index);
      drop = { container, baseY: container.y };
      state.artifacts.set(artifact.filepath, drop);
      state.artifactLayer.addChild(container);
    }
    const point = artifactDropPoint(index);
    drop.container.x = point.x;
    drop.baseY = point.y - 18;
    drop.container.zIndex = Math.round(point.y) + 8;
  });
  state.artifactLayer.sortChildren();
}

function readyArtifactsByRole(artifacts: LaunchCrewArtifact[]) {
  const result = new Map<LaunchCrewRole, LaunchCrewArtifact>();
  for (const artifact of artifacts) {
    if (artifact.status !== "ready") continue;
    if (result.has(artifact.role)) continue;
    result.set(artifact.role, artifact);
  }
  return result;
}

function syncCarriedPackages(
  state: PixiStageState,
  renderedAgents: RenderedAgent[],
  artifacts: LaunchCrewArtifact[],
) {
  const artifactsByRole = readyArtifactsByRole(artifacts);
  const carryingAgents = new Map(
    renderedAgents
      .filter(({ motion }) => motion.state === "reporting")
      .flatMap(({ agent }) => {
        const artifact = artifactsByRole.get(agent.id);
        return artifact ? [[agent.id, artifact] as const] : [];
      }),
  );

  for (const [agentId, node] of state.carriedPackages) {
    const nextArtifact = carryingAgents.get(agentId);
    if (nextArtifact?.name === node.artifactName) continue;
    node.container.destroy({ children: true });
    state.carriedPackages.delete(agentId);
  }

  for (const [agentId, artifact] of carryingAgents) {
    let node = state.carriedPackages.get(agentId);
    if (!node) {
      const container = createCarriedPackage(artifact);
      node = { container, agentId, artifactName: artifact.name };
      state.carriedPackages.set(agentId, node);
      state.artifactLayer.addChild(container);
    }
    const agent = state.agents.get(agentId);
    if (agent) {
      updateCarriedPackagePosition(node, agent);
    }
  }
  state.artifactLayer.sortChildren();
}

function syncStatusEffects(
  state: PixiStageState,
  agents: LaunchCrewAgent[],
  artifacts: LaunchCrewArtifact[],
) {
  const desired = new Set<string>();
  for (const agent of agents) {
    if (agent.id === "launch-director") continue;
    if (agent.status === "error") {
      desired.add(effectKey("station-blocked", agent.id));
      continue;
    }
    if (agent.active) {
      desired.add(effectKey("station-active", agent.id));
    }
  }
  if (artifacts.some((artifact) => artifact.status === "ready")) {
    desired.add(effectKey("artifact-pulse", "conveyor"));
  }

  for (const [key, effect] of state.effects) {
    if (desired.has(key)) continue;
    effect.graphic.destroy();
    state.effects.delete(key);
  }

  for (const agent of agents) {
    const kind =
      agent.status === "error"
        ? "station-blocked"
        : agent.id !== "launch-director" && agent.active
          ? "station-active"
          : null;
    if (!kind) continue;
    const key = effectKey(kind, agent.id);
    if (state.effects.has(key)) continue;
    const graphic = new Graphics();
    drawStationEffect(graphic, agent);
    state.effects.set(key, {
      graphic,
      kind,
      phase: state.effects.size * 0.7,
    });
    state.effectLayer.addChild(graphic);
  }

  const conveyorKey = effectKey("artifact-pulse", "conveyor");
  if (desired.has(conveyorKey) && !state.effects.has(conveyorKey)) {
    const graphic = new Graphics();
    drawArtifactPulse(graphic);
    state.effects.set(conveyorKey, {
      graphic,
      kind: "artifact-pulse",
      phase: state.effects.size * 0.7,
    });
    state.effectLayer.addChild(graphic);
  }
  state.effectLayer.sortChildren();
}

function removeMissingAgentNodes(
  state: PixiStageState,
  renderedAgents: RenderedAgent[],
) {
  const liveIds = new Set(renderedAgents.map(({ agent }) => agent.id));
  for (const [id, node] of state.agents) {
    if (liveIds.has(id)) continue;
    node.sprite.destroy();
    node.label.destroy();
    node.ring.destroy();
    state.agents.delete(id);
  }
}

async function syncPixiStage({
  state,
  renderedAgents,
  artifacts,
  motions,
  selectedAgentId,
  onSelectAgent,
}: {
  state: PixiStageState;
  renderedAgents: RenderedAgent[];
  artifacts: LaunchCrewArtifact[];
  motions: WarRoomAgentMotion[];
  selectedAgentId: LaunchCrewRole;
  onSelectAgent: (id: LaunchCrewRole) => void;
}) {
  await renderStaticProps(state);
  if (state.destroyed) return;

  drawSignalLines(state.lineLayer, motions);
  syncStatusEffects(
    state,
    renderedAgents.map(({ agent }) => agent),
    artifacts,
  );
  syncArtifactDrops(state, artifacts);
  removeMissingAgentNodes(state, renderedAgents);
  for (const renderedAgent of renderedAgents) {
    const texture = await loadTexture(
      state.textureCache,
      renderedAgent.sprite.src,
    );
    if (state.destroyed) return;
    const path = stagePath(renderedAgent.motion.path);
    const key = pathKey(renderedAgent.motion.path);
    const target = path[0] ?? stagePoint(renderedAgent.motion.position);
    let node = state.agents.get(renderedAgent.agent.id);
    if (!node) {
      const sprite = new Sprite(texture);
      sprite.width = renderedAgent.sprite.width;
      sprite.height = renderedAgent.sprite.height;
      sprite.anchor.set(0.5, 1);
      sprite.x = stagePoint(renderedAgent.motion.previousPosition).x;
      sprite.y = stagePoint(renderedAgent.motion.previousPosition).y;
      sprite.eventMode = "static";
      sprite.cursor = "pointer";
      sprite.on("pointertap", () => onSelectAgent(renderedAgent.agent.id));

      const label = createAgentLabel(
        renderedAgent.agent.shortName,
        renderedAgent.agent.id === selectedAgentId,
      );
      const ring = new Graphics();

      node = {
        id: renderedAgent.agent.id,
        sprite,
        label,
        ring,
        pathKey: key,
        path,
        pathIndex: 0,
        targetX: target.x,
        targetY: target.y,
        selected: renderedAgent.agent.id === selectedAgentId,
      };
      state.agents.set(renderedAgent.agent.id, node);
      state.agentLayer.addChild(ring, sprite, label);
    }

    node.sprite.texture = texture;
    node.sprite.width = renderedAgent.sprite.width;
    node.sprite.height = renderedAgent.sprite.height;
    if (node.pathKey !== key) {
      node.pathKey = key;
      node.path = path;
      node.pathIndex = 0;
      node.targetX = target.x;
      node.targetY = target.y;
    }
    node.selected = renderedAgent.agent.id === selectedAgentId;
    node.label.style.fill = node.selected ? 0xeafffb : 0xcffcf1;
    node.label.style.fontSize = node.selected ? 12 : 10;
    node.label.style.stroke = {
      color: 0x101714,
      width: node.selected ? 4 : 3,
    };
    updateAgentNodePosition(node);
  }
  syncCarriedPackages(state, renderedAgents, artifacts);
  state.agentLayer.sortChildren();
}

function CanvasHitTargets({
  renderedAgents,
  artifacts,
  selectedAgentId,
  onSelectAgent,
}: {
  renderedAgents: RenderedAgent[];
  artifacts: LaunchCrewArtifact[];
  selectedAgentId: LaunchCrewRole;
  onSelectAgent: (id: LaunchCrewRole) => void;
}) {
  return (
    <div className="absolute inset-0 z-20">
      {WAR_ROOM_PROPS.map((prop) => (
        <span
          key={prop.id}
          data-war-room-prop={prop.id}
          data-war-room-waypoint={prop.waypoint}
          className="pointer-events-none absolute size-1 opacity-0"
          style={{
            left: `${WAR_ROOM_WAYPOINTS[prop.waypoint].x}%`,
            top: `${WAR_ROOM_WAYPOINTS[prop.waypoint].y}%`,
          }}
        />
      ))}
      {artifacts
        .filter((artifact) => artifact.status === "ready")
        .slice(0, 5)
        .map((artifact) => (
          <span
            key={artifact.filepath}
            data-war-room-artifact-drop={artifact.name}
            data-war-room-artifact-role={artifact.role}
            className="pointer-events-none absolute size-1 opacity-0"
            style={{
              left: `${WAR_ROOM_WAYPOINTS.artifactConveyor.x}%`,
              top: `${WAR_ROOM_WAYPOINTS.artifactConveyor.y}%`,
            }}
          />
        ))}
      {renderedAgents
        .filter(({ motion }) => motion.state === "reporting")
        .flatMap(({ agent, motion }) => {
          const artifact = artifacts.find(
            (item) => item.status === "ready" && item.role === agent.id,
          );
          if (!artifact) return [];
          return [
            <span
              key={`carry-${agent.id}-${artifact.filepath}`}
              data-war-room-carried-package={artifact.name}
              data-war-room-carried-agent={agent.id}
              className="pointer-events-none absolute size-1 opacity-0"
              style={{
                left: `${motion.position.x}%`,
                top: `${motion.position.y}%`,
              }}
            />,
          ];
        })}
      {artifacts.some((artifact) => artifact.status === "ready") && (
        <span
          data-war-room-vfx="artifact-pulse"
          className="pointer-events-none absolute size-1 opacity-0"
          style={{
            left: `${WAR_ROOM_WAYPOINTS.artifactConveyor.x}%`,
            top: `${WAR_ROOM_WAYPOINTS.artifactConveyor.y}%`,
          }}
        />
      )}
      {renderedAgents
        .filter(
          ({ agent }) =>
            agent.id !== "launch-director" &&
            agent.status !== "error" &&
            agent.active,
        )
        .map(({ agent, motion }) => (
          <span
            key={`active-${agent.id}`}
            data-war-room-vfx="station-active"
            data-war-room-vfx-agent={agent.id}
            className="pointer-events-none absolute size-1 opacity-0"
            style={{
              left: `${WAR_ROOM_WAYPOINTS[motion.home].x}%`,
              top: `${WAR_ROOM_WAYPOINTS[motion.home].y}%`,
            }}
          />
        ))}
      {renderedAgents
        .filter(({ agent }) => agent.status === "error")
        .map(({ agent, motion }) => (
          <span
            key={`blocked-${agent.id}`}
            data-war-room-vfx="station-blocked"
            data-war-room-vfx-agent={agent.id}
            className="pointer-events-none absolute size-1 opacity-0"
            style={{
              left: `${WAR_ROOM_WAYPOINTS[motion.home].x}%`,
              top: `${WAR_ROOM_WAYPOINTS[motion.home].y}%`,
            }}
          />
        ))}
      {renderedAgents.map(({ agent, motion, sprite }) => {
        const selected = selectedAgentId === agent.id;
        return (
          <button
            key={agent.id}
            type="button"
            aria-label={`Select ${agent.name}`}
            data-war-room-agent={agent.id}
            data-war-room-character={agent.id}
            data-war-room-standalone-character={String(sprite.standalone)}
            data-war-room-sprite-frame={sprite.frame}
            data-war-room-path-length={motion.path.length}
            data-motion-state={motion.state}
            className={[
              "absolute size-16 -translate-x-1/2 -translate-y-full rounded-full text-[0px] focus-visible:outline-2 focus-visible:outline-cyan-200",
              selected ? "pointer-events-auto" : "pointer-events-auto",
            ].join(" ")}
            style={{
              left: `${motion.position.x}%`,
              top: `${motion.position.y}%`,
            }}
            onClick={() => onSelectAgent(agent.id)}
          />
        );
      })}
    </div>
  );
}

export function WarRoomCanvasStage({
  agents,
  artifacts,
  motions,
  selectedAgentId,
  onSelectAgent,
}: WarRoomCanvasStageProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<PixiStageState | null>(null);
  const renderedAgents = useRenderedAgents(agents, motions);

  useEffect(() => {
    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    const mountNode = containerRef.current;
    if (!mountNode) return;

    async function setup(mountElement: HTMLDivElement) {
      const app = new Application();
      await app.init({
        backgroundAlpha: 0,
        antialias: false,
        autoDensity: true,
        resizeTo: mountElement,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
      });
      if (cancelled) {
        app.destroy();
        return;
      }

      const root = new Container();
      fitRootToContainer(root, mountElement);
      root.sortableChildren = true;
      const lineLayer = new Graphics();
      const effectLayer = new Container();
      const propLayer = new Container();
      const artifactLayer = new Container();
      const agentLayer = new Container();
      effectLayer.sortableChildren = true;
      propLayer.sortableChildren = true;
      artifactLayer.sortableChildren = true;
      agentLayer.sortableChildren = true;
      drawRoomShell(root);
      root.addChild(
        lineLayer,
        effectLayer,
        propLayer,
        artifactLayer,
        agentLayer,
      );
      app.stage.addChild(root);
      app.canvas.setAttribute("data-war-room-canvas", "true");
      app.canvas.classList.add("size-full", "[image-rendering:pixelated]");
      mountElement.appendChild(app.canvas);

      stageRef.current = {
        app,
        root,
        lineLayer,
        effectLayer,
        propLayer,
        artifactLayer,
        agentLayer,
        textureCache: new Map(),
        agents: new Map(),
        artifacts: new Map(),
        carriedPackages: new Map(),
        effects: new Map(),
        propsRendered: false,
        destroyed: false,
      };
      app.ticker.add(() => {
        if (stageRef.current) {
          tickAgentNodes(stageRef.current);
        }
      });

      resizeObserver = new ResizeObserver(() => {
        fitRootToContainer(root, mountElement);
      });
      resizeObserver.observe(mountElement);

      void syncPixiStage({
        state: stageRef.current,
        renderedAgents,
        artifacts,
        motions,
        selectedAgentId,
        onSelectAgent,
      });
    }

    setup(mountNode);

    return () => {
      cancelled = true;
      const state = stageRef.current;
      if (!state) return;
      state.destroyed = true;
      resizeObserver?.disconnect();
      state.app.destroy(true);
      stageRef.current = null;
    };
  }, []);

  useEffect(() => {
    const state = stageRef.current;
    if (!state) return;
    void syncPixiStage({
      state,
      renderedAgents,
      artifacts,
      motions,
      selectedAgentId,
      onSelectAgent,
    });
  }, [artifacts, renderedAgents, motions, selectedAgentId, onSelectAgent]);

  return (
    <section
      aria-label="Animated EcomLaunch war room"
      className="relative size-full overflow-hidden bg-[#223038]"
    >
      <div ref={containerRef} className="absolute inset-0 z-10" />
      <CanvasHitTargets
        renderedAgents={renderedAgents}
        artifacts={artifacts}
        selectedAgentId={selectedAgentId}
        onSelectAgent={onSelectAgent}
      />
      <div className="pointer-events-none absolute top-5 left-5 z-30 rounded border border-cyan-100/25 bg-[#101714]/88 px-3 py-2 text-cyan-50 shadow-[3px_3px_0_rgba(0,0,0,0.62)]">
        <div className="text-[10px] font-black tracking-[0.2em] text-cyan-100/70 uppercase">
          Launch War Room
        </div>
        <div className="mt-1 text-xs font-black">PixiJS canvas stage</div>
      </div>
    </section>
  );
}
