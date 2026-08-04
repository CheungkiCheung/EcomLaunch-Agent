/**
 * Original pixel-office scene for the War Room.
 *
 * The environment and six directional character sheets were created for this
 * repository. Phaser keeps the existing real-state movement, collision,
 * pathfinding, status, and interaction behavior without loading Agent Town or
 * LimeZu runtime assets.
 */

import * as Phaser from "phaser";

import type { Translations } from "@/core/i18n/locales/types";

import { InteractionMenu } from "./interaction-menu";
import {
  ORIGINAL_ACTOR_LAYOUT,
  ORIGINAL_OFFICE_BACKGROUND,
  ORIGINAL_OFFICE_COLLISIONS,
  ORIGINAL_OFFICE_HEIGHT,
  ORIGINAL_OFFICE_POIS,
  ORIGINAL_OFFICE_WIDTH,
  originalCharacterPath,
} from "./original-office-layout";
import { Pathfinder, type PathPoint } from "./pathfinder";
import type { WarRoomActorId, WarRoomSnapshot, WarRoomStatus } from "./types";

const GAME_WIDTH = 1280;
const GAME_HEIGHT = 720;
const FRAME_WIDTH = 48;
const FRAME_HEIGHT = 72;
const CHARACTER_SCALE = 1.2;
const DEFAULT_CAMERA_ZOOM = 0.72;
const MOVE_SPEED = 160;
const WORKER_SPEED = 110;
const INTERACT_DISTANCE = 64;
const ARRIVE_THRESHOLD = 4;
const PF_PADDING = 9;

type Facing = "down" | "left" | "right" | "up";

const DIRECTION_FRAME: Record<Facing, number> = {
  down: 0,
  left: 1,
  right: 2,
  up: 3,
};

const STATUS_COLORS: Record<WarRoomStatus, number> = {
  idle: 0xa8a29e,
  queued: 0xd99b3f,
  working: 0xe76f2e,
  done: 0x4d9d7a,
  failed: 0xc85a58,
};

const EMOTE_LABELS: Partial<Record<WarRoomStatus, string>> = {
  queued: "…",
  working: "…",
  done: "★",
  failed: "!",
};

function textureKey(actorId: WarRoomActorId) {
  return `original-war-room-${actorId}`;
}

interface ActorSprite {
  id: WarRoomActorId;
  name: string;
  sprite: Phaser.Physics.Arcade.Sprite;
  nameLabel: Phaser.GameObjects.Text;
  statusLabel: Phaser.GameObjects.Text;
  emote: Phaser.GameObjects.Text;
  bubble: Phaser.GameObjects.Text;
  status: WarRoomStatus;
  homeX: number;
  homeY: number;
  workX: number;
  workY: number;
  facing: Facing;
  moving: boolean;
  path: PathPoint[];
  pathIndex: number;
  stuckFrames: number;
  lastX: number;
  lastY: number;
  wanderTarget: { x: number; y: number } | null;
  wanderTimer: Phaser.Time.TimerEvent | null;
  wanderStayUntil: number;
  lastTask: string | undefined;
}

export type WarRoomGameHandle = {
  updateSnapshot: (snapshot: WarRoomSnapshot) => void;
  destroy: () => void;
};

export type ActorView = "chat" | "task" | "output";

function setSpriteFacing(sprite: Phaser.Physics.Arcade.Sprite, facing: Facing) {
  sprite.setFrame(DIRECTION_FRAME[facing]);
  sprite.setFlipX(false);
}

function setMovementPose(
  sprite: Phaser.Physics.Arcade.Sprite,
  moving: boolean,
  time: number,
) {
  if (!moving) {
    sprite.setAngle(0);
    sprite.setScale(CHARACTER_SCALE);
    return;
  }

  const step = Math.sin(time / 78);
  sprite.setAngle(step * 1.8);
  sprite.setScale(CHARACTER_SCALE, CHARACTER_SCALE + Math.abs(step) * 0.035);
}

export async function createWarRoomGame({
  parent,
  initialSnapshot,
  onActorSelect,
  labels,
}: {
  parent: HTMLElement;
  initialSnapshot: WarRoomSnapshot;
  onActorSelect: (actorId: WarRoomActorId, view?: ActorView) => void;
  labels: Translations["warRoom"];
}): Promise<WarRoomGameHandle> {
  const PhaserModule = await import("phaser");

  class OfficeScene extends PhaserModule.Scene {
    private collisionGroup: Phaser.Physics.Arcade.StaticGroup | null = null;
    private pathfinder: Pathfinder | null = null;
    private interactionMenu: InteractionMenu | null = null;
    private cameraFollowing = false;
    private actors: ActorSprite[] = [];
    private bossSprite!: Phaser.Physics.Arcade.Sprite;
    private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
    private wasd!: Record<string, Phaser.Input.Keyboard.Key>;
    private interactKey!: Phaser.Input.Keyboard.Key;
    private bossFacing: Facing = "up";
    private selectedActorId: WarRoomActorId = "ecom-launch";
    private talkingActorId: WarRoomActorId | null = null;
    private interactionPrompt: Phaser.GameObjects.Text | null = null;
    private snapshot: WarRoomSnapshot = initialSnapshot;

    constructor() {
      super({ key: "OfficeScene" });
    }

    preload() {
      this.load.image("original-war-room-office", ORIGINAL_OFFICE_BACKGROUND);
      for (const actor of initialSnapshot.actors) {
        this.load.spritesheet(
          textureKey(actor.id),
          originalCharacterPath(actor.id),
          {
            frameWidth: FRAME_WIDTH,
            frameHeight: FRAME_HEIGHT,
          },
        );
      }
    }

    create() {
      this.add
        .image(0, 0, "original-war-room-office")
        .setOrigin(0, 0)
        .setDepth(0);

      this.physics.world.setBounds(
        0,
        0,
        ORIGINAL_OFFICE_WIDTH,
        ORIGINAL_OFFICE_HEIGHT,
      );
      this.collisionGroup = this.buildCollisionGroup();
      this.pathfinder = new Pathfinder(
        ORIGINAL_OFFICE_WIDTH,
        ORIGINAL_OFFICE_HEIGHT,
        ORIGINAL_OFFICE_COLLISIONS,
        PF_PADDING,
      );

      const bossLayout = ORIGINAL_ACTOR_LAYOUT["ecom-launch"];
      this.bossFacing = bossLayout.facing;
      this.bossSprite = this.physics.add
        .sprite(
          bossLayout.homeX,
          bossLayout.homeY,
          textureKey("ecom-launch"),
          DIRECTION_FRAME[bossLayout.facing],
        )
        .setDepth(100 + bossLayout.homeY)
        .setScale(CHARACTER_SCALE)
        .setCollideWorldBounds(true);
      this.configureBody(this.bossSprite);
      this.physics.add.collider(this.bossSprite, this.collisionGroup);

      const kb = this.input.keyboard;
      if (!kb) throw new Error("Keyboard plugin not available");
      this.cursors = kb.createCursorKeys();
      kb.clearCaptures();
      this.wasd = kb.addKeys(
        {
          W: Phaser.Input.Keyboard.KeyCodes.W,
          A: Phaser.Input.Keyboard.KeyCodes.A,
          S: Phaser.Input.Keyboard.KeyCodes.S,
          D: Phaser.Input.Keyboard.KeyCodes.D,
        },
        false,
      ) as Record<string, Phaser.Input.Keyboard.Key>;
      this.interactKey = kb.addKey(Phaser.Input.Keyboard.KeyCodes.E);

      this.interactionPrompt = this.add
        .text(0, 0, labels.canvas.interactionPrompt, {
          fontSize: "14px",
          fontStyle: "bold",
          color: "#f8f7f4",
          backgroundColor: "rgba(46, 46, 62, 0.86)",
          padding: { x: 7, y: 3 },
          fontFamily: "ui-monospace, Menlo, monospace",
        })
        .setOrigin(0.5, 1)
        .setDepth(5000)
        .setVisible(false);

      this.buildActors();
      this.configureCamera();

      this.interactionMenu = new InteractionMenu(this);
      this.interactionMenu.onClose = () => {
        this.interactionPrompt?.setVisible(true);
      };

      this.updateSnapshot(initialSnapshot);
    }

    private buildCollisionGroup() {
      const group = this.physics.add.staticGroup();
      for (const rect of ORIGINAL_OFFICE_COLLISIONS) {
        const blocker = group.create(
          rect.x + rect.width / 2,
          rect.y + rect.height / 2,
          undefined,
          undefined,
          false,
        ) as Phaser.Physics.Arcade.Sprite;
        blocker.body!.setSize(rect.width, rect.height);
        blocker.setVisible(false).setActive(true);
        (blocker.body as Phaser.Physics.Arcade.StaticBody).enable = true;
      }
      return group;
    }

    private configureBody(sprite: Phaser.Physics.Arcade.Sprite) {
      sprite.setBodySize(20, 12);
      sprite.setOffset(14, 56);
      const body = sprite.body as Phaser.Physics.Arcade.Body;
      body.allowGravity = false;
      body.pushable = false;
    }

    private configureCamera() {
      const cam = this.cameras.main;
      cam.setBackgroundColor("#f1dfc7");
      cam.setZoom(DEFAULT_CAMERA_ZOOM);
      cam.setBounds(0, 0, ORIGINAL_OFFICE_WIDTH, ORIGINAL_OFFICE_HEIGHT);
      cam.centerOn(this.bossSprite.x, this.bossSprite.y - 120);
      this.cameraFollowing = false;

      this.input.on(
        "wheel",
        (
          pointer: Phaser.Input.Pointer,
          _currentlyOver: unknown,
          _dx: number,
          dy: number,
        ) => {
          const oldZoom = cam.zoom;
          const newZoom = Phaser.Math.Clamp(oldZoom - dy * 0.001, 0.5, 2);
          if (newZoom === oldZoom) return;
          const worldBefore = cam.getWorldPoint(pointer.x, pointer.y);
          cam.setZoom(newZoom);
          const worldAfter = cam.getWorldPoint(pointer.x, pointer.y);
          cam.scrollX += worldBefore.x - worldAfter.x;
          cam.scrollY += worldBefore.y - worldAfter.y;
        },
      );

      let dragStart: {
        x: number;
        y: number;
        scrollX: number;
        scrollY: number;
      } | null = null;
      this.input.on("pointerdown", (pointer: Phaser.Input.Pointer) => {
        dragStart = {
          x: pointer.x,
          y: pointer.y,
          scrollX: cam.scrollX,
          scrollY: cam.scrollY,
        };
      });
      this.input.on("pointermove", (pointer: Phaser.Input.Pointer) => {
        if (!this.cameraFollowing && dragStart) {
          cam.scrollX =
            dragStart.scrollX - (pointer.x - dragStart.x) / cam.zoom;
          cam.scrollY =
            dragStart.scrollY - (pointer.y - dragStart.y) / cam.zoom;
        }
      });
      this.input.on("pointerup", () => {
        dragStart = null;
      });
    }

    private buildActors() {
      this.actors = [];
      for (const actor of this.snapshot.actors) {
        if (actor.id === "ecom-launch") continue;
        const layout = ORIGINAL_ACTOR_LAYOUT[actor.id];
        const sprite = this.physics.add
          .sprite(
            layout.homeX,
            layout.homeY,
            textureKey(actor.id),
            DIRECTION_FRAME[layout.facing],
          )
          .setDepth(100 + layout.homeY)
          .setScale(CHARACTER_SCALE);
        this.configureBody(sprite);
        const workerBody = sprite.body as Phaser.Physics.Arcade.Body;
        workerBody.mass = 999;

        const nameLabel = this.add
          .text(layout.homeX, layout.homeY - 50, actor.name, {
            fontSize: "15px",
            color: "#f7f5f1",
            backgroundColor: "rgba(47, 47, 62, 0.78)",
            padding: { x: 5, y: 2 },
            fontFamily: "ui-monospace, Menlo, monospace",
          })
          .setOrigin(0.5)
          .setDepth(4000);

        const statusLabel = this.add
          .text(layout.homeX, layout.homeY - 34, "", {
            fontSize: "12px",
            color: "#a8a29e",
            backgroundColor: "rgba(247, 245, 241, 0.9)",
            padding: { x: 4, y: 1 },
            fontFamily: "ui-monospace, Menlo, monospace",
          })
          .setOrigin(0.5)
          .setDepth(4000);

        const emote = this.add
          .text(layout.homeX + 24, layout.homeY - 58, "", {
            fontSize: "20px",
            fontStyle: "bold",
            color: "#353547",
            backgroundColor: "rgba(247, 245, 241, 0.92)",
            padding: { x: 5, y: 1 },
            fontFamily: "ui-monospace, Menlo, monospace",
          })
          .setOrigin(0.5)
          .setDepth(4100)
          .setVisible(false);

        const bubble = this.add
          .text(layout.homeX, layout.homeY - 76, "", {
            fontSize: "13px",
            color: "#f7f5f1",
            backgroundColor: "rgba(47, 47, 62, 0.88)",
            padding: { x: 6, y: 3 },
            fontFamily: "ui-monospace, Menlo, monospace",
            wordWrap: { width: 200 },
          })
          .setOrigin(0.5)
          .setDepth(4200)
          .setVisible(false);

        this.actors.push({
          id: actor.id,
          name: actor.name,
          sprite,
          nameLabel,
          statusLabel,
          emote,
          bubble,
          status: "idle",
          homeX: layout.homeX,
          homeY: layout.homeY,
          workX: layout.workX,
          workY: layout.workY,
          facing: layout.facing,
          moving: false,
          path: [],
          pathIndex: 0,
          stuckFrames: 0,
          lastX: layout.homeX,
          lastY: layout.homeY,
          wanderTarget: null,
          wanderTimer: null,
          wanderStayUntil: 0,
          lastTask: undefined,
        });

        sprite.setInteractive({ useHandCursor: true });
        sprite.on("pointerdown", () => {
          this.selectedActorId = actor.id;
          this.talkingActorId = actor.id;
          onActorSelect(actor.id);
        });
      }
    }

    private scheduleWander(actor: ActorSprite) {
      if (actor.wanderTimer || ORIGINAL_OFFICE_POIS.length === 0) return;
      const poi =
        ORIGINAL_OFFICE_POIS[
          PhaserModule.Math.Between(0, ORIGINAL_OFFICE_POIS.length - 1)
        ]!;
      actor.wanderTimer = this.time.delayedCall(
        PhaserModule.Math.Between(1800, 5200),
        () => {
          actor.wanderTimer = null;
          if (actor.status !== "idle" || actor.id === this.talkingActorId)
            return;
          actor.wanderTarget = { x: poi.x, y: poi.y };
          actor.path = [];
          actor.moving = true;
        },
      );
    }

    private handleInteract() {
      const nearest = this.nearestActor();
      if (!nearest || !this.interactionMenu) return;
      this.interactionPrompt?.setVisible(false);

      const actorSnapshot = this.snapshot.actors.find(
        (actor) => actor.id === nearest.id,
      );
      this.interactionMenu.show(this.bossSprite.x, this.bossSprite.y - 42, [
        {
          label: `💬 ${labels.chat}`,
          enabled: true,
          action: () => {
            this.selectedActorId = nearest.id;
            this.talkingActorId = nearest.id;
            onActorSelect(nearest.id, "chat");
          },
        },
        {
          label: `📋 ${labels.canvas.viewTask}`,
          enabled: Boolean(actorSnapshot?.task),
          action: () => {
            this.selectedActorId = nearest.id;
            this.talkingActorId = nearest.id;
            onActorSelect(nearest.id, "task");
          },
        },
        {
          label: `📄 ${labels.canvas.viewOutput}`,
          enabled: Boolean(actorSnapshot?.taskDetail?.output),
          action: () => {
            this.selectedActorId = nearest.id;
            this.talkingActorId = nearest.id;
            onActorSelect(nearest.id, "output");
          },
        },
      ]);
    }

    private nearestActor(): ActorSprite | null {
      let nearest: ActorSprite | null = null;
      let minDistance = Infinity;
      for (const actor of this.actors) {
        const distance = PhaserModule.Math.Distance.Between(
          this.bossSprite.x,
          this.bossSprite.y,
          actor.sprite.x,
          actor.sprite.y,
        );
        if (distance < INTERACT_DISTANCE && distance < minDistance) {
          nearest = actor;
          minDistance = distance;
        }
      }
      return nearest;
    }

    private setActorFacing(actor: ActorSprite, facing: Facing) {
      actor.facing = facing;
      setSpriteFacing(actor.sprite, facing);
    }

    private moveWorker(actor: ActorSprite, time: number) {
      const isTalking = actor.id === this.talkingActorId;
      if (isTalking && actor.status !== "working") {
        actor.wanderTarget = null;
        actor.wanderTimer?.destroy();
        actor.wanderTimer = null;
        actor.moving = false;
        actor.path = [];
        actor.sprite.setVelocity(0, 0);
        const dx = this.bossSprite.x - actor.sprite.x;
        const dy = this.bossSprite.y - actor.sprite.y;
        this.setActorFacing(
          actor,
          Math.abs(dx) > Math.abs(dy)
            ? dx > 0
              ? "right"
              : "left"
            : dy > 0
              ? "down"
              : "up",
        );
        setMovementPose(actor.sprite, false, time);
        return;
      }

      let targetX = actor.homeX;
      let targetY = actor.homeY;
      if (actor.status === "working") {
        targetX = actor.workX;
        targetY = actor.workY;
      } else if (actor.wanderTarget) {
        targetX = actor.wanderTarget.x;
        targetY = actor.wanderTarget.y;
      }

      if (actor.moving) {
        const pathEnd = actor.path[actor.path.length - 1];
        const pathMatchesTarget =
          pathEnd &&
          Math.abs(pathEnd.x - targetX) < 4 &&
          Math.abs(pathEnd.y - targetY) < 4;
        if (!pathMatchesTarget) {
          const path = this.pathfinder?.findPath(
            actor.sprite.x,
            actor.sprite.y,
            targetX,
            targetY,
          );
          if (path && path.length > 1) {
            actor.path = path.slice(1);
            actor.pathIndex = 0;
          } else {
            actor.path = [];
            actor.moving = false;
          }
        }
      }

      let reached = !actor.moving;
      if (actor.path.length > 0 && actor.pathIndex < actor.path.length) {
        const waypoint = actor.path[actor.pathIndex]!;
        const dx = waypoint.x - actor.sprite.x;
        const dy = waypoint.y - actor.sprite.y;
        const distance = Math.hypot(dx, dy);

        const moved =
          Math.abs(actor.sprite.x - actor.lastX) +
          Math.abs(actor.sprite.y - actor.lastY);
        actor.lastX = actor.sprite.x;
        actor.lastY = actor.sprite.y;
        if (moved < 0.5) {
          actor.stuckFrames += 1;
          if (actor.stuckFrames > 12) {
            actor.stuckFrames = 0;
            actor.pathIndex += 1;
          }
        } else {
          actor.stuckFrames = 0;
        }

        if (distance < ARRIVE_THRESHOLD) {
          actor.pathIndex += 1;
          reached = actor.pathIndex >= actor.path.length;
        } else {
          const facing: Facing =
            Math.abs(dx) > Math.abs(dy)
              ? dx > 0
                ? "right"
                : "left"
              : dy > 0
                ? "down"
                : "up";
          if (facing !== actor.facing) this.setActorFacing(actor, facing);
          actor.sprite.setVelocity(
            (dx / distance) * WORKER_SPEED,
            (dy / distance) * WORKER_SPEED,
          );
          setMovementPose(actor.sprite, true, time);
        }
      } else if (actor.moving) {
        reached = true;
      }

      if (reached) {
        actor.sprite.setVelocity(0, 0);
        setMovementPose(actor.sprite, false, time);
        if (actor.moving) {
          actor.moving = false;
          actor.path = [];
          if (actor.wanderTarget) {
            actor.wanderTarget = null;
            actor.wanderStayUntil =
              this.time.now + PhaserModule.Math.Between(2800, 5800);
          }
        }
        if (
          actor.status === "idle" &&
          !actor.wanderTarget &&
          this.time.now > actor.wanderStayUntil
        ) {
          this.scheduleWander(actor);
        }
      }
    }

    update(time: number) {
      let velocityX = 0;
      let velocityY = 0;
      if (this.cursors.left?.isDown || this.wasd.A!.isDown) velocityX = -1;
      else if (this.cursors.right?.isDown || this.wasd.D!.isDown) velocityX = 1;
      if (this.cursors.up?.isDown || this.wasd.W!.isDown) velocityY = -1;
      else if (this.cursors.down?.isDown || this.wasd.S!.isDown) velocityY = 1;

      const bossMoving = velocityX !== 0 || velocityY !== 0;
      if (bossMoving) {
        if (!this.cameraFollowing) {
          this.cameraFollowing = true;
          this.cameras.main.startFollow(this.bossSprite, true, 0.08, 0.08);
        }
        const length = Math.hypot(velocityX, velocityY);
        this.bossSprite.setVelocity(
          (velocityX / length) * MOVE_SPEED,
          (velocityY / length) * MOVE_SPEED,
        );
        const facing: Facing =
          Math.abs(velocityX) > Math.abs(velocityY)
            ? velocityX > 0
              ? "right"
              : "left"
            : velocityY > 0
              ? "down"
              : "up";
        if (facing !== this.bossFacing) {
          this.bossFacing = facing;
          setSpriteFacing(this.bossSprite, facing);
        }
      } else {
        this.bossSprite.setVelocity(0, 0);
      }
      setMovementPose(this.bossSprite, bossMoving, time);
      this.bossSprite.setDepth(100 + Math.round(this.bossSprite.y));

      for (const actor of this.actors) {
        this.moveWorker(actor, time);
        actor.sprite.setDepth(100 + Math.round(actor.sprite.y));
        actor.nameLabel.setPosition(actor.sprite.x, actor.sprite.y - 62);
        actor.statusLabel.setPosition(actor.sprite.x, actor.sprite.y - 42);
        actor.emote.setPosition(actor.sprite.x + 28, actor.sprite.y - 70);
        if (actor.bubble.visible) {
          actor.bubble.setPosition(actor.sprite.x, actor.sprite.y - 92);
        }
      }

      const nearest = this.nearestActor();
      if (this.interactionPrompt) {
        if (nearest && !this.interactionMenu?.visible) {
          this.interactionPrompt
            .setVisible(true)
            .setPosition(this.bossSprite.x, this.bossSprite.y - 52);
        } else {
          this.interactionPrompt.setVisible(false);
        }
      }

      if (
        !this.interactionMenu?.visible &&
        Phaser.Input.Keyboard.JustDown(this.interactKey)
      ) {
        this.handleInteract();
      }
      this.interactionMenu?.update();
    }

    updateSnapshot(snapshot: WarRoomSnapshot) {
      this.snapshot = snapshot;
      for (const actor of this.actors) {
        const actorSnapshot = snapshot.actors.find(
          (candidate) => candidate.id === actor.id,
        );
        if (!actorSnapshot) continue;

        actor.status = actorSnapshot.status;
        actor.statusLabel
          .setText(labels.statuses[actorSnapshot.status])
          .setColor(
            `#${STATUS_COLORS[actorSnapshot.status].toString(16).padStart(6, "0")}`,
          );

        const emoteLabel = EMOTE_LABELS[actorSnapshot.status];
        if (emoteLabel) {
          actor.emote.setText(emoteLabel).setVisible(true);
          if (
            actorSnapshot.status === "done" ||
            actorSnapshot.status === "failed"
          ) {
            this.time.delayedCall(2500, () => actor.emote.setVisible(false));
          }
        } else if (
          actorSnapshot.status === "idle" &&
          !actor.emote.visible &&
          Math.random() < 0.05
        ) {
          actor.emote.setText("Zz").setVisible(true);
          this.time.delayedCall(3200, () => actor.emote.setVisible(false));
        } else if (actorSnapshot.status === "idle") {
          actor.emote.setVisible(false);
        }

        if (
          actorSnapshot.status === "working" &&
          actorSnapshot.task &&
          actorSnapshot.task !== actor.lastTask
        ) {
          actor.lastTask = actorSnapshot.task;
          actor.bubble
            .setText(
              actorSnapshot.task.length > 24
                ? `${actorSnapshot.task.slice(0, 24)}…`
                : actorSnapshot.task,
            )
            .setVisible(true);
        } else if (actorSnapshot.status !== "working") {
          actor.lastTask = undefined;
          actor.bubble.setVisible(false);
        }

        actor.wanderTarget = null;
        actor.path = [];
        actor.moving = true;
      }
    }

    destroy() {
      this.scene.stop();
      this.scene.remove();
    }
  }

  const game = new PhaserModule.Game({
    type: PhaserModule.AUTO,
    width: GAME_WIDTH,
    height: GAME_HEIGHT,
    backgroundColor: "#f1dfc7",
    pixelArt: true,
    antialias: false,
    roundPixels: true,
    scene: [OfficeScene],
    parent,
    scale: {
      mode: PhaserModule.Scale.RESIZE,
      autoCenter: PhaserModule.Scale.NO_CENTER,
    },
    physics: {
      default: "arcade",
      arcade: { gravity: { x: 0, y: 0 } },
    },
  });
  let sceneInstance: OfficeScene | null = null;
  game.events.on("ready", () => {
    sceneInstance = game.scene.getScene("OfficeScene") as OfficeScene;
  });

  return {
    updateSnapshot: (snapshot) => {
      sceneInstance?.updateSnapshot(snapshot);
    },
    destroy: () => {
      game.destroy(true);
    },
  };
}
