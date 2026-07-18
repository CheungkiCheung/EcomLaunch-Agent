from __future__ import annotations

from collections import deque
from pathlib import Path
from shutil import copyfile

from PIL import Image


SOURCE_ROOT = Path("/Users/zhangqixiang/0_2实习/deepagents/image2/ecom-war-room-accepted")
TARGET_ROOT = (
    Path(__file__).resolve().parents[1]
    / "public"
    / "images"
    / "ecom-launch"
    / "war-room"
)

SOURCE_FILES = {
    "room-background.png": "01-room-background.png",
    "command-console.png": "02-command-console.png",
    "market-voc-researcher-spritesheet.png": "10-agent-market-voc-researcher.png",
    "offer-architect-spritesheet.png": "11-agent-offer-architect.png",
    "evidence-checker-spritesheet.png": "12-agent-evidence-checker.png",
    "growth-analyst-spritesheet.png": "13-agent-growth-analyst.png",
    "asset-studio-spritesheet.png": "14-agent-asset-studio.png",
    "launch-director-spritesheet.png": "15-agent-launch-director-seated.png",
    "workstation.png": "20-prop-workstation.png",
    "big-screen.png": "21-prop-big-launch-screen.png",
    "whiteboard.png": "22-prop-strategy-whiteboard.png",
    "artifact-conveyor.png": "23-prop-artifact-conveyor.png",
    "coffee-station.png": "24-prop-coffee-station.png",
    "artifact-items-sheet.png": "30-artifact-items-sheet.png",
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
    "coffee-station.png",
]

ARTIFACT_ITEM_FILES = [
    "package.png",
    "product-card.png",
    "research-report.png",
    "evidence-checklist.png",
    "creative-thumbnail.png",
    "analytics-folder.png",
    "launch-calendar.png",
    "approval-stamp.png",
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


def alpha_bbox_with_padding(image: Image.Image, padding: int) -> tuple[int, int, int, int] | None:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    return (
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    )


def component_bboxes(image: Image.Image, min_area: int) -> list[tuple[int, int, int, int]]:
    alpha = image.getchannel("A")
    width, height = image.size
    pixels = alpha.load()
    seen = bytearray(width * height)
    bboxes: list[tuple[int, int, int, int]] = []

    for start_y in range(height):
        for start_x in range(width):
            index = start_y * width + start_x
            if seen[index] or pixels[start_x, start_y] == 0:
                continue
            seen[index] = 1
            queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
            left = right = start_x
            top = bottom = start_y
            area = 0

            while queue:
                x, y = queue.popleft()
                area += 1
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
                for next_x, next_y in (
                    (x + 1, y),
                    (x - 1, y),
                    (x, y + 1),
                    (x, y - 1),
                ):
                    if not (0 <= next_x < width and 0 <= next_y < height):
                        continue
                    next_index = next_y * width + next_x
                    if seen[next_index] or pixels[next_x, next_y] == 0:
                        continue
                    seen[next_index] = 1
                    queue.append((next_x, next_y))

            if area >= min_area:
                bboxes.append((left, top, right + 1, bottom + 1))

    return sorted(bboxes, key=lambda bbox: bbox[0])


def save_artifact_items(sheet: Image.Image, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    bboxes = component_bboxes(sheet, min_area=650)
    if len(bboxes) != len(ARTIFACT_ITEM_FILES):
        # Fall back to eight visual bands if antialiased shadows connect oddly.
        cell_width = sheet.width / len(ARTIFACT_ITEM_FILES)
        bboxes = []
        for index in range(len(ARTIFACT_ITEM_FILES)):
            band = sheet.crop(
                (
                    round(index * cell_width),
                    0,
                    round((index + 1) * cell_width),
                    sheet.height,
                )
            )
            bbox = alpha_bbox_with_padding(band, padding=10)
            if bbox is None:
                continue
            left, top, right, bottom = bbox
            band_left = round(index * cell_width)
            bboxes.append((left + band_left, top, right + band_left, bottom))

    if len(bboxes) != len(ARTIFACT_ITEM_FILES):
        raise ValueError(f"Expected 8 artifact items, found {len(bboxes)}")

    packed_sheet = Image.new("RGBA", (256 * len(ARTIFACT_ITEM_FILES), 256))
    for index, (name, bbox) in enumerate(zip(ARTIFACT_ITEM_FILES, bboxes)):
        left, top, right, bottom = bbox
        item = trim_alpha(sheet.crop((left, top, right, bottom)), padding=12)
        item.thumbnail((210, 210), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (256, 256))
        canvas.alpha_composite(
            item,
            ((256 - item.width) // 2, (256 - item.height) // 2),
        )
        canvas.save(target_dir / name)
        packed_sheet.alpha_composite(canvas, (index * 256, 0))
    packed_sheet.save(target_dir / "items-sheet.png")


def main() -> None:
    working_root = SOURCE_ROOT / "_processed-runtime"
    working_root.mkdir(parents=True, exist_ok=True)

    for target_name, source_name in SOURCE_FILES.items():
        source_path = SOURCE_ROOT / source_name
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        target_path = working_root / target_name
        if target_name == "room-background.png":
            remove_edge_checkerboard(Image.open(source_path)).save(
                TARGET_ROOT / "room" / "background.png"
            )
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

    artifact_sheet = Image.open(working_root / "artifact-items-sheet.png").convert(
        "RGBA"
    )
    save_artifact_items(artifact_sheet, TARGET_ROOT / "artifacts")


if __name__ == "__main__":
    main()
