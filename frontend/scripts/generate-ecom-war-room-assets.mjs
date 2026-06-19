import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const assetRoot = join(root, "images", "ecom-launch", "war-room");

const roles = [
  {
    id: "market-voc-researcher",
    skin: "#f0b27a",
    jacket: "#2582c7",
    hair: "#164560",
    accent: "#7dd3fc",
    accessory: "cap",
    tool: "tablet",
  },
  {
    id: "offer-architect",
    skin: "#e7a66f",
    jacket: "#279b63",
    hair: "#174b30",
    accent: "#86efac",
    accessory: "cap",
    tool: "blueprint",
  },
  {
    id: "evidence-checker",
    skin: "#f2bd82",
    jacket: "#2563eb",
    hair: "#151a21",
    accent: "#bfdbfe",
    accessory: "glasses",
    tool: "clipboard",
  },
  {
    id: "growth-analyst",
    skin: "#d99b6a",
    jacket: "#d18a25",
    hair: "#7a4a28",
    accent: "#fde68a",
    accessory: "none",
    tool: "chart",
  },
  {
    id: "asset-studio",
    skin: "#f0a7a7",
    jacket: "#df4c92",
    hair: "#ec5ca2",
    accent: "#f9a8d4",
    accessory: "ponytail",
    tool: "stylus",
  },
];

const frames = [
  "idle",
  "walk-left",
  "walk-right",
  "walk-up",
  "walk-down",
  "work",
];

function save(relativePath, content) {
  const path = join(assetRoot, relativePath);
  mkdirSync(dirname(path), { recursive: true });
  const normalizedContent = content
    .trim()
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n");
  writeFileSync(path, `${normalizedContent}\n`);
}

function characterSvg(role, frame) {
  const walkingLeft = frame === "walk-left";
  const walkingRight = frame === "walk-right";
  const walkingUp = frame === "walk-up";
  const walkingDown = frame === "walk-down";
  const working = frame === "work";
  const facingSide = walkingLeft || walkingRight;
  const facingBack = walkingUp;
  const bodyLean = walkingLeft ? -2 : walkingRight ? 2 : 0;
  const leftArmY = working ? 54 : walkingLeft || walkingDown ? 49 : 44;
  const rightArmY = working ? 54 : walkingRight || walkingUp ? 49 : 44;
  const leftLegY = walkingLeft || walkingDown ? 73 : 68;
  const rightLegY = walkingRight || walkingUp ? 73 : 68;
  const sideNose = walkingLeft
    ? `<path d="M22 35h4v4h-4z" fill="${role.skin}"/>`
    : walkingRight
      ? `<path d="M54 35h4v4h-4z" fill="${role.skin}"/>`
      : "";
  const ponytail = role.accessory === "ponytail";
  const cap = role.accessory === "cap";
  const glasses = role.accessory === "glasses";
  const showFace = !facingBack;
  const hairFront = facingBack
    ? `<path d="M22 19h36v17H22zM18 29h44v12H18zM24 39h32v7H24z" fill="${role.hair}"/>`
    : `<path d="M22 18h36v12H22zM18 27h44v7H18zM20 33h10v12H20zM50 33h10v12H50z" fill="${role.hair}"/>`;
  const faceDetails =
    showFace && glasses
      ? `<path d="M25 36h10v6H25zM43 36h10v6H43zM35 38h8v2h-8z" fill="#111827"/><path d="M27 37h6v4h-6zM45 37h6v4h-6z" fill="#dbeafe"/>`
      : showFace
        ? `<path d="M29 37h4v5h-4zM46 37h4v5h-4z" fill="#111827"/>`
        : "";
  const expression = showFace
    ? `<path d="M34 47h12v3H34z" fill="#9a3412" opacity=".48"/>`
    : "";
  const tool =
    role.tool === "tablet"
      ? `<path d="M28 59h22v15H28z" fill="#10242f"/><path d="M32 63h14v3H32zM32 69h9v3h-9z" fill="${role.accent}"/>`
      : role.tool === "blueprint"
        ? `<path d="M25 58h28v16H25z" fill="#dcfce7"/><path d="M29 63h18v2H29zM29 68h10v2H29z" fill="#15803d"/>`
        : role.tool === "clipboard"
          ? `<path d="M30 57h20v18H30z" fill="#e2e8f0"/><path d="M34 62h12v2H34zM34 67h8v2h-8z" fill="#334155"/>`
          : role.tool === "chart"
            ? `<path d="M29 58h23v16H29z" fill="#111827"/><path d="M33 69h4v3h-4zM40 64h4v8h-4zM47 60h4v12h-4z" fill="${role.accent}"/>`
            : `<path d="M29 58h22v16H29z" fill="#2b2130"/><path d="M34 65l13-7 2 3-13 7z" fill="${role.accent}"/>`;

  return `
<svg xmlns="http://www.w3.org/2000/svg" width="80" height="98" viewBox="0 0 80 98" shape-rendering="crispEdges">
  <path d="M20 84h40v6H20zM26 80h28v4H26z" fill="#111827" opacity=".3"/>
  <path d="M25 ${leftLegY}h10v14H25zM45 ${rightLegY}h10v14H45z" fill="#1f2937"/>
  <path d="M23 ${leftLegY + 12}h15v7H23zM42 ${rightLegY + 12}h15v7H42z" fill="#101827"/>
  <path d="M25 ${leftLegY}h10v4H25zM45 ${rightLegY}h10v4H45z" fill="#ffffff" opacity=".1"/>
  <path d="M22 ${43 + bodyLean}h36v31H22z" fill="#111827"/>
  <path d="M24 ${40 + bodyLean}h32v31H24z" fill="${role.jacket}"/>
  <path d="M30 ${44 + bodyLean}h20v22H30z" fill="${role.accent}" opacity=".42"/>
  <path d="M34 ${43 + bodyLean}h12v28H34z" fill="#0f172a" opacity=".14"/>
  <path d="M16 ${leftArmY}h11v22H16zM53 ${rightArmY}h11v22H53z" fill="#111827"/>
  <path d="M18 ${leftArmY - 2}h10v23H18zM52 ${rightArmY - 2}h10v23H52z" fill="${role.jacket}"/>
  <path d="M18 68h11v8H18zM51 68h11v8H51z" fill="${role.skin}"/>
  <path d="M20 20h40v5H20zM18 25h44v22H18zM22 47h36v11H22z" fill="#111827"/>
  <path d="M22 22h36v24H22zM26 46h28v9H26z" fill="${role.skin}"/>
  <path d="M18 32h5v12h-5zM57 32h5v12h-5z" fill="#c97c55"/>
${hairFront}
${cap ? `<path d="M19 15h40v8H19zM27 10h26v9H27zM54 20h14v5H54z" fill="${role.jacket}"/><path d="M27 12h26v3H27z" fill="${role.accent}" opacity=".65"/>` : ""}
${ponytail ? `<path d="M54 26h12v28H54zM58 52h8v12h-8z" fill="${role.hair}"/>` : ""}
${sideNose}
${faceDetails}
${expression}
${working ? tool : ""}
${facingSide ? `<path d="${walkingLeft ? "M20 31h13v19H20z" : "M47 31h13v19H47z"}" fill="${role.hair}"/>` : ""}
  <path d="M24 ${40 + bodyLean}h32v5H24zM24 ${68 + bodyLean}h32v4H24zM18 ${leftArmY - 2}h10v5H18zM52 ${rightArmY - 2}h10v5H52z" fill="#0f172a" opacity=".24"/>
  <path d="M22 22h36v4H22zM22 26h4v20h-4zM54 26h4v20h-4zM24 45h4v23h-4zM52 45h4v23h-4z" fill="#ffffff" opacity=".1"/>
  <path d="M16 76h48v4H16z" fill="#0f172a" opacity=".16"/>
  <title>${role.id} ${frame}</title>
</svg>`;
}

function workstationSvg({ id, accent, mirror = false }) {
  const screenX = mirror ? 31 : 8;
  const towerX = mirror ? 6 : 66;
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="96" height="72" viewBox="0 0 96 72" shape-rendering="crispEdges">
  <path d="M6 44h84v12H6z" fill="#8b6238"/>
  <path d="M10 56h76v8H10z" fill="#3c2b20"/>
  <path d="M14 64h12v6H14zM70 64h12v6H70z" fill="#1f2933"/>
  <path d="M6 42h84v4H6z" fill="#c58b4f"/>
  <path d="M${screenX} 12h48v28h-${48}z" fill="#17262b"/>
  <path d="M${screenX + 4} 16h40v20h-${40}z" fill="#0b3a3f"/>
  <path d="M${screenX + 8} 21h10v3h-10zM${screenX + 8} 28h28v3h-28zM${screenX + 24} 21h12v3h-12z" fill="${accent}"/>
  <path d="M${screenX + 20} 40h8v4h-8zM${screenX + 12} 44h24v4h-24z" fill="#1f2937"/>
  <path d="M30 50h30v6H30z" fill="#111827"/>
  <path d="M${towerX} 32h16v24h-16z" fill="#1f2937"/>
  <path d="M${towerX + 3} 37h10v3h-10zM${towerX + 3} 44h10v3h-10z" fill="${accent}"/>
  <path d="M${mirror ? 76 : 10} 35h10v12h-${10}z" fill="#d7d1bd"/>
  <path d="M0 68h96v4H0z" fill="#0f172a" opacity=".22"/>
  <title>${id}</title>
</svg>`;
}

function commandConsoleSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="180" height="116" viewBox="0 0 180 116" shape-rendering="crispEdges">
  <path d="M18 66h144v24H18z" fill="#31383c"/>
  <path d="M6 82h168v20H6z" fill="#1f2933"/>
  <path d="M30 24h120v38H30z" fill="#142a2f"/>
  <path d="M36 30h108v26H36z" fill="#0b3f42"/>
  <path d="M48 42h20v4H48zM78 35h24v4H78zM112 43h24v4h-24z" fill="#67e8f9"/>
  <path d="M42 68h22v12H42zM78 68h22v12H78zM114 68h22v12h-22z" fill="#121a1f"/>
  <path d="M48 72h10v3H48zM84 72h10v3H84zM120 72h10v3h-10z" fill="#5eead4"/>
  <path d="M64 86h52v20H64z" fill="#111827"/>
  <path d="M70 91h40v5H70z" fill="#20313a"/>
  <path d="M8 102h164v8H8z" fill="#0f172a" opacity=".3"/>
</svg>`;
}

function directorSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="86" height="102" viewBox="0 0 86 102" shape-rendering="crispEdges">
  <path d="M24 86h38v7H24zM29 81h28v5H29z" fill="#111827" opacity=".32"/>
  <path d="M27 72h12v18H27zM48 72h12v18H48z" fill="#1f2937"/>
  <path d="M24 89h18v7H24zM45 89h18v7H45z" fill="#101827"/>
  <path d="M25 50h36v30H25z" fill="#111827"/>
  <path d="M28 47h30v30H28z" fill="#2563eb"/>
  <path d="M34 51h18v22H34z" fill="#93c5fd" opacity=".44"/>
  <path d="M18 52h12v25H18zM56 52h12v25H56z" fill="#2563eb"/>
  <path d="M17 72h12v8H17zM57 72h12v8H57z" fill="#f0b27a"/>
  <path d="M24 23h38v6H24zM22 29h42v24H22zM27 53h32v10H27z" fill="#111827"/>
  <path d="M25 25h36v27H25zM30 52h26v9H30z" fill="#f2bd82"/>
  <path d="M20 35h6v13h-6zM60 35h6v13h-6z" fill="#d8905f"/>
  <path d="M23 20h40v12H23zM20 29h46v7H20zM21 34h11v17H21zM54 34h11v17H54z" fill="#8b542b"/>
  <path d="M32 39h4v5h-4zM50 39h4v5h-4z" fill="#111827"/>
  <path d="M38 49h12v3H38z" fill="#9a3412" opacity=".55"/>
  <path d="M28 47h30v5H28zM28 75h30v4H28zM18 52h12v5H18zM56 52h12v5H56z" fill="#0f172a" opacity=".22"/>
  <path d="M31 66h24v14H31z" fill="#111827"/>
  <path d="M35 70h16v3H35zM35 75h10v3H35z" fill="#67e8f9"/>
  <title>launch-director idle</title>
</svg>`;
}

function bigScreenSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="58" viewBox="0 0 140 58" shape-rendering="crispEdges">
  <path d="M4 4h132v48H4z" fill="#17262b"/>
  <path d="M10 10h120v36H10z" fill="#06343a"/>
  <path d="M24 20h18v3H24zM24 28h32v3H24zM24 36h24v3H24z" fill="#5eead4"/>
  <path d="M72 37l10-12 12 7 16-18 8 5-22 24-13-8-8 10z" fill="#22d3ee"/>
  <path d="M0 52h140v6H0z" fill="#0f172a" opacity=".22"/>
</svg>`;
}

function whiteboardSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="112" height="56" viewBox="0 0 112 56" shape-rendering="crispEdges">
  <path d="M4 4h104v44H4z" fill="#18252a"/>
  <path d="M10 10h92v32H10z" fill="#dbe4df"/>
  <path d="M20 17h18v3H20zM20 25h30v3H20zM20 33h22v3H20z" fill="#475569"/>
  <path d="M60 34l10-12 10 6 12-14 5 4-16 20-11-7-7 8z" fill="#0f766e"/>
  <path d="M0 48h112v6H0z" fill="#0f172a" opacity=".2"/>
</svg>`;
}

function conveyorSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="108" height="42" viewBox="0 0 108 42" shape-rendering="crispEdges">
  <path d="M6 14h96v18H6z" fill="#1f2937"/>
  <path d="M10 18h88v8H10z" fill="#334155"/>
  <path d="M16 28h10v8H16zM82 28h10v8H82z" fill="#111827"/>
  <path d="M26 8h24v16H26z" fill="#d6b36c"/>
  <path d="M30 12h16v3H30zM30 18h10v3H30z" fill="#8a6d3b"/>
  <path d="M62 10h18v14H62z" fill="#0f766e"/>
  <path d="M66 15h10v3H66z" fill="#99f6e4"/>
</svg>`;
}

function coffeeSvg() {
  return `
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="50" viewBox="0 0 48 50" shape-rendering="crispEdges">
  <path d="M12 18h22v24H12z" fill="#334155"/>
  <path d="M16 22h14v16H16z" fill="#7c2d12"/>
  <path d="M34 24h8v12h-8zM36 28h4v4h-4z" fill="#334155"/>
  <path d="M16 8h4v7h-4zM24 6h4v8h-4zM32 9h4v7h-4z" fill="#67e8f9" opacity=".65"/>
  <path d="M10 42h28v4H10z" fill="#0f172a" opacity=".25"/>
</svg>`;
}

for (const role of roles) {
  for (const frame of frames) {
    save(`agents/${role.id}/${frame}.svg`, characterSvg(role, frame));
  }
  save(
    `props/${role.id}-station.svg`,
    workstationSvg({
      id: `${role.id} station`,
      accent: role.accent,
      mirror: role.id === "evidence-checker" || role.id === "asset-studio",
    }),
  );
}

save("agents/launch-director/idle.svg", directorSvg());
save("props/command-console.svg", commandConsoleSvg());
save("props/big-screen.svg", bigScreenSvg());
save("props/whiteboard.svg", whiteboardSvg());
save("props/artifact-conveyor.svg", conveyorSvg());
save("props/coffee.svg", coffeeSvg());
