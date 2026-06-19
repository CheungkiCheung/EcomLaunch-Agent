import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "public");
const assetRoot = join(root, "images", "ecom-launch", "war-room");

const roles = [
  {
    id: "market-voc-researcher",
    jacket: "#2582c7",
    hair: "#164560",
    accent: "#7dd3fc",
    accessory: "cap",
  },
  {
    id: "offer-architect",
    jacket: "#279b63",
    hair: "#174b30",
    accent: "#86efac",
    accessory: "cap",
  },
  {
    id: "evidence-checker",
    jacket: "#2563eb",
    hair: "#151a21",
    accent: "#bfdbfe",
    accessory: "glasses",
  },
  {
    id: "growth-analyst",
    jacket: "#d18a25",
    hair: "#7a4a28",
    accent: "#fde68a",
    accessory: "none",
  },
  {
    id: "asset-studio",
    jacket: "#df4c92",
    hair: "#ec5ca2",
    accent: "#f9a8d4",
    accessory: "ponytail",
  },
];

const frames = ["idle", "walk-left", "walk-right"];

function save(relativePath, content) {
  const path = join(assetRoot, relativePath);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, `${content.trim()}\n`);
}

function characterSvg(role, frame) {
  const walkingLeft = frame === "walk-left";
  const walkingRight = frame === "walk-right";
  const leftArmY = walkingLeft ? 38 : walkingRight ? 34 : 36;
  const rightArmY = walkingRight ? 38 : walkingLeft ? 34 : 36;
  const leftLegY = walkingLeft ? 60 : walkingRight ? 56 : 58;
  const rightLegY = walkingRight ? 60 : walkingLeft ? 56 : 58;
  const ponytail = role.accessory === "ponytail";
  const cap = role.accessory === "cap";
  const glasses = role.accessory === "glasses";

  return `
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="82" viewBox="0 0 64 82" shape-rendering="crispEdges">
  <path d="M22 68h20v4H22z" fill="#111827" opacity=".28"/>
  <path d="M24 ${leftLegY}h7v12h-7zM34 ${rightLegY}h7v12h-7z" fill="#1f2937"/>
  <path d="M22 35h20v26H22z" fill="${role.jacket}"/>
  <path d="M26 38h12v20H26z" fill="${role.accent}" opacity=".35"/>
  <path d="M18 ${leftArmY}h7v19h-7zM39 ${rightArmY}h7v19h-7z" fill="${role.jacket}"/>
  <path d="M20 54h7v6h-7zM37 54h7v6h-7z" fill="#f0b27a"/>
  <path d="M22 17h20v22H22z" fill="#f2bd82"/>
  <path d="M20 22h4v11h-4zM40 22h4v11h-4z" fill="#d8905f"/>
  <path d="M22 14h20v9H22zM20 20h24v5H20z" fill="${role.hair}"/>
  ${cap ? `<path d="M18 11h28v7H18zM25 7h16v7H25zM43 15h10v4H43z" fill="${role.jacket}"/><path d="M25 9h16v2H25z" fill="${role.accent}" opacity=".5"/>` : ""}
  ${ponytail ? `<path d="M40 20h9v24h-9zM43 41h6v10h-6z" fill="${role.hair}"/>` : ""}
  ${glasses ? `<path d="M24 26h7v5h-7zM34 26h7v5h-7zM31 28h3v1h-3z" fill="#111827"/><path d="M25 27h5v3h-5zM35 27h5v3h-5z" fill="#dbeafe"/>` : ""}
  <path d="M27 29h3v4h-3zM36 29h3v4h-3z" fill="#111827"/>
  <path d="M30 36h7v2h-7z" fill="#9a3412" opacity=".5"/>
  <path d="M22 35h20v4H22zM22 57h20v4H22zM18 ${leftArmY}h7v4h-7zM39 ${rightArmY}h7v4h-7z" fill="#0f172a" opacity=".22"/>
  <path d="M20 17h24v4H20zM20 21h4v14h-4zM40 21h4v14h-4zM22 39h4v18h-4zM38 39h4v18h-4z" fill="#0f172a" opacity=".16"/>
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
<svg xmlns="http://www.w3.org/2000/svg" width="70" height="86" viewBox="0 0 70 86" shape-rendering="crispEdges">
  <path d="M21 64h28v10H21z" fill="#111827" opacity=".3"/>
  <path d="M21 58h28v22H21z" fill="#1f2937"/>
  <path d="M25 45h20v22H25z" fill="#2563eb"/>
  <path d="M19 47h8v20h-8zM43 47h8v20h-8z" fill="#2563eb"/>
  <path d="M21 65h8v6h-8zM41 65h8v6h-8z" fill="#f0b27a"/>
  <path d="M24 22h22v24H24z" fill="#f2bd82"/>
  <path d="M22 28h4v11h-4zM44 28h4v11h-4z" fill="#d8905f"/>
  <path d="M22 18h26v10H22zM20 25h30v5H20z" fill="#8b542b"/>
  <path d="M29 33h3v4h-3zM39 33h3v4h-3z" fill="#111827"/>
  <path d="M31 41h8v2h-8z" fill="#9a3412" opacity=".55"/>
  <path d="M24 48h22v5H24zM25 64h20v4H25z" fill="#0f172a" opacity=".2"/>
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
