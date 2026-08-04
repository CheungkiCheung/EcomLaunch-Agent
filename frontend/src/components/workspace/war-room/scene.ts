import type * as PhaserTypes from "phaser";

import type { Translations } from "@/core/i18n/locales/types";

import type {
  WarRoomActorId,
  WarRoomActorSnapshot,
  WarRoomSnapshot,
  WarRoomStatus,
} from "./types";

const BACKGROUND_WIDTH = 1672;
const BACKGROUND_HEIGHT = 941;
const SNAPSHOT_EVENT = "war-room:snapshot";

type ActorRuntime = {
  container: PhaserTypes.GameObjects.Container;
  sprite: PhaserTypes.GameObjects.Image;
  shadow: PhaserTypes.GameObjects.Ellipse;
  glow: PhaserTypes.GameObjects.Ellipse;
  nameLabel: PhaserTypes.GameObjects.Text;
  statusLabel: PhaserTypes.GameObjects.Text;
  bubble: PhaserTypes.GameObjects.Text;
  snapshot: WarRoomActorSnapshot;
  bobTween?: PhaserTypes.Tweens.Tween;
  pulseTween?: PhaserTypes.Tweens.Tween;
  moveTween?: PhaserTypes.Tweens.Tween;
};

export type WarRoomGameHandle = {
  updateSnapshot: (snapshot: WarRoomSnapshot) => void;
  destroy: () => void;
};

const STATUS_COLORS: Record<WarRoomStatus, number> = {
  idle: 0xa8a29e,
  queued: 0xf0b45a,
  working: 0xee8d5a,
  done: 0x65a68e,
  failed: 0xd7655d,
};

export async function createWarRoomGame({
  parent,
  initialSnapshot,
  onActorSelect,
  labels,
}: {
  parent: HTMLElement;
  initialSnapshot: WarRoomSnapshot;
  onActorSelect: (actorId: WarRoomActorId) => void;
  labels: Translations["warRoom"];
}): Promise<WarRoomGameHandle> {
  const Phaser = await import("phaser");

  class WarRoomScene extends Phaser.Scene {
    private background?: PhaserTypes.GameObjects.Image;
    private actorRuntimes = new Map<WarRoomActorId, ActorRuntime>();
    private snapshot = initialSnapshot;
    private sceneBounds = {
      x: 0,
      y: 0,
      width: BACKGROUND_WIDTH,
      height: BACKGROUND_HEIGHT,
    };

    constructor() {
      super({ key: "WarRoomScene" });
    }

    preload() {
      this.load.image("war-room-background", "/war-room/background.png");
      for (const actor of initialSnapshot.actors) {
        this.load.image(
          `war-room-actor-${actor.id}`,
          `/war-room/agent-${actor.id}.png`,
        );
      }
    }

    create() {
      this.cameras.main.setBackgroundColor("#f7f3eb");
      this.background = this.add
        .image(0, 0, "war-room-background")
        .setOrigin(0, 0)
        .setDepth(0);

      for (const actor of this.snapshot.actors) {
        this.actorRuntimes.set(actor.id, this.createActor(actor));
      }

      this.layoutScene();
      this.applySnapshot(this.snapshot, false);
      this.scale.on("resize", this.layoutScene);
      this.game.events.on(SNAPSHOT_EVENT, this.receiveSnapshot);
      this.events.once(Phaser.Scenes.Events.SHUTDOWN, this.cleanup);
      this.events.once(Phaser.Scenes.Events.DESTROY, this.cleanup);
    }

    private createActor(actor: WarRoomActorSnapshot): ActorRuntime {
      const container = this.add.container(0, 0).setDepth(20);
      const glow = this.add
        .ellipse(0, -2, 72, 30, actor.glow, 0.12)
        .setVisible(false);
      const shadow = this.add.ellipse(0, 1, 46, 14, 0x6f5847, 0.16);
      const sprite = this.add
        .image(0, 0, `war-room-actor-${actor.id}`)
        .setOrigin(0.5, 1)
        .setInteractive({ useHandCursor: true });
      const nameLabel = this.add
        .text(0, 10, actor.name, {
          fontFamily:
            'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          fontSize: "11px",
          fontStyle: "600",
          color: "#5c4638",
          backgroundColor: "rgba(255, 253, 248, 0.92)",
          padding: { x: 7, y: 3 },
          align: "center",
        })
        .setOrigin(0.5, 0)
        .setResolution(Math.max(1, window.devicePixelRatio));
      const statusLabel = this.add
        .text(0, 34, labels.statuses[actor.status], {
          fontFamily:
            'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          fontSize: "9px",
          color: "#7a6250",
          backgroundColor: "rgba(255, 251, 244, 0.88)",
          padding: { x: 6, y: 2 },
          align: "center",
        })
        .setOrigin(0.5, 0)
        .setResolution(Math.max(1, window.devicePixelRatio));
      const bubble = this.add
        .text(0, -104, "", {
          fontFamily:
            'ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          fontSize: "10px",
          fontStyle: "600",
          color: "#624839",
          backgroundColor: "rgba(255, 252, 246, 0.96)",
          padding: { x: 8, y: 5 },
          align: "center",
          stroke: "#ffffff",
          strokeThickness: 1,
        })
        .setOrigin(0.5, 1)
        .setResolution(Math.max(1, window.devicePixelRatio))
        .setVisible(false);

      sprite.on("pointerdown", () => onActorSelect(actor.id));
      sprite.on("pointerover", () => {
        this.tweens.add({
          targets: sprite,
          scaleX: sprite.scaleX * 1.04,
          scaleY: sprite.scaleY * 1.04,
          duration: 120,
          ease: "Sine.Out",
        });
      });
      sprite.on("pointerout", () => this.layoutActor(runtime));

      container.add([glow, shadow, sprite, nameLabel, statusLabel, bubble]);
      const runtime: ActorRuntime = {
        container,
        sprite,
        shadow,
        glow,
        nameLabel,
        statusLabel,
        bubble,
        snapshot: actor,
      };
      return runtime;
    }

    private receiveSnapshot = (snapshot: WarRoomSnapshot) => {
      this.snapshot = snapshot;
      this.applySnapshot(snapshot, true);
    };

    private applySnapshot(snapshot: WarRoomSnapshot, animate: boolean) {
      for (const actor of snapshot.actors) {
        const runtime = this.actorRuntimes.get(actor.id);
        if (!runtime) continue;
        const previousStatus = runtime.snapshot.status;
        runtime.snapshot = actor;
        this.updateActorAppearance(runtime, previousStatus, animate);
        this.moveActor(runtime, animate);
      }
    }

    private layoutScene = () => {
      if (!this.background) return;
      const width = this.scale.width;
      const height = this.scale.height;
      const scale = Math.min(
        width / BACKGROUND_WIDTH,
        height / BACKGROUND_HEIGHT,
      );
      const displayWidth = BACKGROUND_WIDTH * scale;
      const displayHeight = BACKGROUND_HEIGHT * scale;
      const x = (width - displayWidth) / 2;
      const y = (height - displayHeight) / 2;
      this.sceneBounds = { x, y, width: displayWidth, height: displayHeight };
      this.background
        .setPosition(x, y)
        .setDisplaySize(displayWidth, displayHeight);
      for (const runtime of this.actorRuntimes.values()) {
        this.layoutActor(runtime);
      }
    };

    private layoutActor(runtime: ActorRuntime) {
      const actorHeight = Math.max(
        78,
        Math.min(122, this.sceneBounds.height * 0.145),
      );
      const source =
        runtime.sprite.texture.getSourceImage() as HTMLImageElement;
      const actorWidth = actorHeight * (source.width / source.height);
      runtime.sprite.setDisplaySize(actorWidth, actorHeight);
      runtime.shadow.setSize(
        actorWidth * 0.56,
        Math.max(8, actorHeight * 0.09),
      );
      runtime.glow.setSize(actorWidth * 0.95, actorHeight * 0.2);
      runtime.bubble.setY(-actorHeight - 8);
      const target = this.positionFor(runtime.snapshot);
      if (!runtime.moveTween?.isPlaying()) {
        runtime.container.setPosition(target.x, target.y);
      }
      runtime.container.setDepth(20 + Math.round(runtime.container.y));
    }

    private positionFor(actor: WarRoomActorSnapshot) {
      const active = actor.status !== "idle";
      const percentX = active ? actor.position.workX : actor.position.x;
      const percentY = active ? actor.position.workY : actor.position.y;
      return {
        x: this.sceneBounds.x + this.sceneBounds.width * (percentX / 100),
        y: this.sceneBounds.y + this.sceneBounds.height * (percentY / 100),
      };
    }

    private moveActor(runtime: ActorRuntime, animate: boolean) {
      const target = this.positionFor(runtime.snapshot);
      const distance = Phaser.Math.Distance.Between(
        runtime.container.x,
        runtime.container.y,
        target.x,
        target.y,
      );
      if (!animate || distance < 2) {
        runtime.container.setPosition(target.x, target.y);
        runtime.container.setDepth(20 + Math.round(target.y));
        return;
      }

      runtime.moveTween?.stop();
      const direction = target.x >= runtime.container.x ? 1 : -1;
      runtime.sprite.setFlipX(direction < 0);
      runtime.moveTween = this.tweens.add({
        targets: runtime.container,
        x: target.x,
        y: target.y,
        duration: Math.max(650, Math.min(1500, distance * 7)),
        ease: "Sine.InOut",
        onUpdate: () => {
          runtime.container.setDepth(20 + Math.round(runtime.container.y));
          runtime.sprite.setAngle(Math.sin(this.time.now / 85) * 2.2);
          runtime.shadow.setScale(
            0.92 + Math.abs(Math.sin(this.time.now / 85)) * 0.1,
            1,
          );
        },
        onComplete: () => {
          runtime.sprite.setAngle(0);
          runtime.sprite.setFlipX(false);
          runtime.shadow.setScale(1);
        },
      });
    }

    private updateActorAppearance(
      runtime: ActorRuntime,
      previousStatus: WarRoomStatus,
      animate: boolean,
    ) {
      const actor = runtime.snapshot;
      const color = STATUS_COLORS[actor.status];
      runtime.statusLabel
        .setText(labels.statuses[actor.status])
        .setColor(`#${color.toString(16).padStart(6, "0")}`);
      runtime.glow.setFillStyle(color, actor.status === "working" ? 0.2 : 0.12);
      runtime.glow.setVisible(actor.status !== "idle");
      runtime.bubble
        .setText(
          actor.status === "failed"
            ? labels.statuses.failed
            : actor.status === "done"
              ? labels.statuses.done
              : labels.activities[actor.activity],
        )
        .setVisible(actor.status !== "idle");

      runtime.bobTween?.stop();
      runtime.pulseTween?.stop();
      runtime.sprite.setPosition(0, 0).setAngle(0).setAlpha(1);
      runtime.glow.setScale(1).setAlpha(1);

      if (actor.status === "working") {
        runtime.bobTween = this.tweens.add({
          targets: runtime.sprite,
          y: -4,
          duration: 460,
          yoyo: true,
          repeat: -1,
          ease: "Sine.InOut",
        });
        runtime.pulseTween = this.tweens.add({
          targets: runtime.glow,
          scaleX: 1.18,
          scaleY: 1.18,
          alpha: 0.45,
          duration: 760,
          yoyo: true,
          repeat: -1,
          ease: "Sine.InOut",
        });
      } else if (actor.status === "queued") {
        runtime.pulseTween = this.tweens.add({
          targets: runtime.glow,
          alpha: 0.35,
          duration: 520,
          yoyo: true,
          repeat: -1,
        });
      } else if (
        actor.status === "done" &&
        previousStatus !== "done" &&
        animate
      ) {
        this.tweens.add({
          targets: runtime.sprite,
          y: -10,
          duration: 180,
          yoyo: true,
          repeat: 1,
          ease: "Back.Out",
        });
      } else if (
        actor.status === "failed" &&
        previousStatus !== "failed" &&
        animate
      ) {
        this.tweens.add({
          targets: runtime.sprite,
          x: { from: -3, to: 3 },
          duration: 70,
          yoyo: true,
          repeat: 4,
        });
      } else {
        runtime.bobTween = this.tweens.add({
          targets: runtime.sprite,
          y: -2,
          duration: 1250 + Math.floor(Math.random() * 350),
          yoyo: true,
          repeat: -1,
          ease: "Sine.InOut",
        });
      }
    }

    private cleanup = () => {
      this.scale.off("resize", this.layoutScene);
      this.game.events.off(SNAPSHOT_EVENT, this.receiveSnapshot);
      for (const runtime of this.actorRuntimes.values()) {
        runtime.bobTween?.stop();
        runtime.pulseTween?.stop();
        runtime.moveTween?.stop();
      }
      this.actorRuntimes.clear();
    };
  }

  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent,
    width: parent.clientWidth || BACKGROUND_WIDTH,
    height: parent.clientHeight || BACKGROUND_HEIGHT,
    transparent: false,
    backgroundColor: "#f7f3eb",
    scene: [WarRoomScene],
    scale: {
      mode: Phaser.Scale.RESIZE,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
    render: {
      antialias: false,
      pixelArt: true,
      roundPixels: true,
    },
  });

  return {
    updateSnapshot: (snapshot) => game.events.emit(SNAPSHOT_EVENT, snapshot),
    destroy: () => game.destroy(true),
  };
}
