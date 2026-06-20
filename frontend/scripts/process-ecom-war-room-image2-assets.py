from __future__ import annotations

from collections import deque
from pathlib import Path
from shutil import copyfile

from PIL import Image


SOURCE_ROOT = Path("/Users/zhangqixiang/0_2实习/deepagents/page")
TARGET_ROOT = (
    Path(__file__).resolve().parents[1]
    / "public"
    / "images"
    / "ecom-launch"
    / "war-room"
)

SOURCE_FILES = {
    "room-background.png": "ChatGPT Image 2026年6月20日 01_33_31.png",
    "market-voc-researcher-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_35.png",
    "offer-architect-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_38.png",
    "evidence-checker-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_40.png",
    "growth-analyst-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_43.png",
    "asset-studio-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_48.png",
    "launch-director-spritesheet.png": "ChatGPT Image 2026年6月20日 01_33_46.png",
    "workstation.png": "ChatGPT Image 2026年6月20日 01_33_55.png",
    "command-console.png": "ChatGPT Image 2026年6月20日 01_33_57.png",
    "big-screen.png": "ChatGPT Image 2026年6月20日 01_34_00.png",
    "whiteboard.png": "ChatGPT Image 2026年6月20日 01_34_05.png",
    "artifact-conveyor.png": "ChatGPT Image 2026年6月20日 01_43_18.png",
}

ROLE_SHEETS = {
    "market-voc-researcher": "market-voc-researcher-spritesheet.png",
    "offer-architect": "offer-architect-spritesheet.png",
    "evidence-checker": "evidence-checker-spritesheet.png",
    "growth-analyst": "growth-analyst-spritesheet.png",
    "asset-studio": "asset-studio-spritesheet.png",
}

CHARACTER_FRAMES = [
    "idle",
    "walk-left",
    "walk-right",
    "walk-up",
    "walk-down",
    "work",
]

DIRECTOR_FRAMES = ["idle", "work", "talk", "alert"]
PROP_FILES = [
    "workstation.png",
    "command-console.png",
    "big-screen.png",
    "whiteboard.png",
    "artifact-conveyor.png",
]


def is_fake_alpha_pixel(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, _alpha = pixel
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    average = (red + green + blue) / 3
    return maximum >= 232 and maximum - minimum <= 26 and average >= 235


def remove_edge_checkerboard(image: Image.Image) -> Image.Image:
    source = image.convert("RGBA")
    width, height = source.size
    pixels = source.load()
    seen = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def enqueue_if_background(x: int, y: int) -> None:
        index = y * width + x
        if seen[index] or not is_fake_alpha_pixel(pixels[x, y]):
            return
        seen[index] = 1
        queue.append((x, y))

    for x in range(width):
        enqueue_if_background(x, 0)
        enqueue_if_background(x, height - 1)
    for y in range(height):
        enqueue_if_background(0, y)
        enqueue_if_background(width - 1, y)

    while queue:
        x, y = queue.popleft()
        for next_x, next_y in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                enqueue_if_background(next_x, next_y)

    result = Image.new("RGBA", source.size)
    result_pixels = result.load()
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            result_pixels[x, y] = (
                red,
                green,
                blue,
                0 if seen[y * width + x] else alpha,
            )
    return result


def trim_alpha(image: Image.Image, padding: int) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    left, top, right, bottom = bbox
    return image.crop(
        (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
    )


def save_frame_sheet(
    sheet: Image.Image,
    frame_names: list[str],
    target_dir: Path,
    padding: int,
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    frame_width = sheet.width // len(frame_names)
    for index, frame_name in enumerate(frame_names):
        frame = sheet.crop(
            (
                index * frame_width,
                0,
                (index + 1) * frame_width,
                sheet.height,
            )
        )
        trim_alpha(frame, padding).save(target_dir / f"{frame_name}.png")


def main() -> None:
    working_root = TARGET_ROOT / "_processed-image2-source"
    working_root.mkdir(parents=True, exist_ok=True)

    for target_name, source_name in SOURCE_FILES.items():
        source_path = SOURCE_ROOT / source_name
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        target_path = working_root / target_name
        if target_name == "room-background.png":
            copyfile(source_path, TARGET_ROOT / "room" / "background.png")
            continue
        remove_edge_checkerboard(Image.open(source_path)).save(target_path)

    for role, sheet_name in ROLE_SHEETS.items():
        sheet = Image.open(working_root / sheet_name).convert("RGBA")
        save_frame_sheet(
            sheet,
            CHARACTER_FRAMES,
            TARGET_ROOT / "agents" / role,
            padding=24,
        )

    director_sheet = Image.open(working_root / "launch-director-spritesheet.png")
    save_frame_sheet(
        director_sheet.convert("RGBA"),
        DIRECTOR_FRAMES,
        TARGET_ROOT / "agents" / "launch-director",
        padding=28,
    )

    props_dir = TARGET_ROOT / "props"
    props_dir.mkdir(parents=True, exist_ok=True)
    for prop_file in PROP_FILES:
        prop = Image.open(working_root / prop_file).convert("RGBA")
        trim_alpha(prop, padding=24).save(props_dir / prop_file)


if __name__ == "__main__":
    main()
