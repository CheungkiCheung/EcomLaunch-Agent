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
  LaunchCrewRole,
} from "./launch-crew-activity-model";
import { WAR_ROOM_PROPS, warRoomCharacterSprite } from "./war-room-assets";
import type { WarRoomAgentMotion } from "./war-room-motion";
import { WAR_ROOM_WAYPOINTS, type WarRoomPoint } from "./war-room-motion";

type WarRoomCanvasStageProps = {
  agents: LaunchCrewAgent[];
  motions: WarRoomAgentMotion[];
  selectedAgentId: LaunchCrewAgent["id"];
  onSelectAgent: (id: LaunchCrewAgent["id"]) => void;
};

type RenderedAgent = {
  agent: LaunchCrewAgent;
  motion: WarRoomAgentMotion;
  sprite: ReturnType<typeof warRoomCharacterSprite>;
};

type PixiStageState = {
  app: Application;
  root: Container;
  textureCache: Map<string, Texture>;
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

function drawSignalLines(root: Container, motions: WarRoomAgentMotion[]) {
  const lineLayer = new Graphics();
  const director = stagePoint(WAR_ROOM_WAYPOINTS.directorDesk);
  for (const motion of motions) {
    if (motion.id === "launch-director") continue;
    const point = stagePoint(motion.position);
    lineLayer
      .moveTo(point.x, point.y)
      .lineTo(director.x, director.y)
      .stroke({
        color: 0x78ffd4,
        width: motion.state === "roaming" ? 1 : 2,
        alpha: motion.state === "roaming" ? 0.24 : 0.78,
      });
  }
  root.addChild(lineLayer);
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

function createAgentLabel(label: string, selected: boolean) {
  const text = new Text({
    text: label,
    style: {
      fontFamily: "monospace",
      fontSize: 12,
      fontWeight: "900",
      fill: selected ? 0xeafffb : 0xcffcf1,
      stroke: { color: 0x101714, width: 4 },
    },
  });
  text.anchor.set(0.5, 0);
  return text;
}

function renderSelectionRing(root: Container, x: number, y: number) {
  const ring = new Graphics();
  ring.ellipse(x, y - 2, 54, 18).stroke({
    color: 0x67ffd6,
    alpha: 0.88,
    width: 3,
  });
  ring.ellipse(x, y, 38, 10).fill({ color: 0x67ffd6, alpha: 0.1 });
  ring.zIndex = Math.round(y) - 1;
  root.addChild(ring);
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

async function renderPixiStage({
  state,
  renderedAgents,
  motions,
  selectedAgentId,
  onSelectAgent,
}: {
  state: PixiStageState;
  renderedAgents: RenderedAgent[];
  motions: WarRoomAgentMotion[];
  selectedAgentId: LaunchCrewRole;
  onSelectAgent: (id: LaunchCrewRole) => void;
}) {
  const { root, textureCache } = state;
  root.removeChildren();
  root.sortableChildren = true;

  drawRoomShell(root);
  drawSignalLines(root, motions);

  for (const prop of WAR_ROOM_PROPS) {
    const texture = await loadTexture(textureCache, prop.src);
    if (state.destroyed) return;
    const sprite = new Sprite(texture);
    fitSprite(
      sprite,
      { width: prop.width, height: prop.height },
      WAR_ROOM_WAYPOINTS[prop.waypoint],
      { x: prop.offsetX, y: prop.offsetY },
    );
    sprite.zIndex -= 30;
    root.addChild(sprite);
  }

  for (const renderedAgent of renderedAgents) {
    const texture = await loadTexture(textureCache, renderedAgent.sprite.src);
    if (state.destroyed) return;
    const sprite = new Sprite(texture);
    fitSprite(
      sprite,
      {
        width: renderedAgent.sprite.width,
        height: renderedAgent.sprite.height,
      },
      renderedAgent.motion.position,
    );
    sprite.eventMode = "static";
    sprite.cursor = "pointer";
    sprite.on("pointertap", () => onSelectAgent(renderedAgent.agent.id));
    sprite.zIndex += 20;
    root.addChild(sprite);

    if (renderedAgent.agent.id === selectedAgentId) {
      renderSelectionRing(root, sprite.x, sprite.y);
    }

    const label = createAgentLabel(
      renderedAgent.agent.shortName,
      renderedAgent.agent.id === selectedAgentId,
    );
    label.x = sprite.x;
    label.y = sprite.y + 6;
    label.zIndex = sprite.zIndex + 2;
    root.addChild(label);
  }

  root.sortChildren();
}

function CanvasHitTargets({
  renderedAgents,
  selectedAgentId,
  onSelectAgent,
}: {
  renderedAgents: RenderedAgent[];
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
      app.stage.addChild(root);
      app.canvas.setAttribute("data-war-room-canvas", "true");
      app.canvas.classList.add("size-full", "[image-rendering:pixelated]");
      mountElement.appendChild(app.canvas);

      stageRef.current = {
        app,
        root,
        textureCache: new Map(),
        destroyed: false,
      };

      resizeObserver = new ResizeObserver(() => {
        fitRootToContainer(root, mountElement);
      });
      resizeObserver.observe(mountElement);

      void renderPixiStage({
        state: stageRef.current,
        renderedAgents,
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
    void renderPixiStage({
      state,
      renderedAgents,
      motions,
      selectedAgentId,
      onSelectAgent,
    });
  }, [renderedAgents, motions, selectedAgentId, onSelectAgent]);

  return (
    <section
      aria-label="Animated EcomLaunch war room"
      className="relative size-full overflow-hidden bg-[#223038]"
    >
      <div ref={containerRef} className="absolute inset-0 z-10" />
      <CanvasHitTargets
        renderedAgents={renderedAgents}
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
