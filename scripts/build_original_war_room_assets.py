#!/usr/bin/env python3
"""Build the original War Room runtime assets from approved ImageGen sources.

The selected source files live under ``frontend/public/war-room-original/source``.
This script applies deterministic palette reduction, hard-alpha cleanup, and
directional sprite packing so the browser consumes stable game-ready assets.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageEnhance


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "frontend" / "public" / "war-room-original"
SOURCE_ROOT = ASSET_ROOT / "source"
CHARACTER_ROOT = ASSET_ROOT / "characters"

BACKGROUND_SOURCE = SOURCE_ROOT / "office-map-reference-style.png"
CHARACTER_SOURCE = SOURCE_ROOT / "character-directions-mc-alpha.png"
BACKGROUND_OUTPUT = ASSET_ROOT / "office-map.png"

CHARACTER_IDS = (
    "ecom-launch",
    "market-voc-researcher",
    "offer-architect",
    "asset-studio",
    "evidence-checker",
    "data-inspector",
)

SOURCE_COLUMNS = 6
SOURCE_ROWS = 4
FRAME_WIDTH = 48
FRAME_HEIGHT = 72
MAX_CHARACTER_WIDTH = 38
MAX_CHARACTER_HEIGHT = 58


def reduce_palette(image: Image.Image, colors: int) -> Image.Image:
    """Reduce RGB colors without adding dithering between pixel clusters."""

    rgb = image.convert("RGB")
    return rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).convert(
        "RGB"
    )


def warm_grade(image: Image.Image) -> Image.Image:
    """Move the office toward warm cream, wood, and taupe without changing layout."""

    softened = ImageEnhance.Color(image.convert("RGB")).enhance(0.9)
    red, green, blue = softened.split()
    red = red.point(lambda value: min(255, round(value * 1.04 + 8)))
    green = green.point(lambda value: min(255, round(value * 1.0 + 4)))
    blue = blue.point(lambda value: max(0, round(value * 0.88 - 2)))
    graded = Image.merge("RGB", (red, green, blue))
    return ImageEnhance.Contrast(graded).enhance(1.03)


def build_background() -> None:
    source = Image.open(BACKGROUND_SOURCE).convert("RGB")
    logical_size = (source.width // 2, source.height // 2)
    pixelated = source.resize(logical_size, Image.Resampling.NEAREST).resize(
        source.size, Image.Resampling.NEAREST
    )
    reduce_palette(warm_grade(pixelated), 96).save(BACKGROUND_OUTPUT, optimize=True)


def harden_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda value: 255 if value >= 96 else 0)
    rgba.putalpha(alpha)
    return rgba


def retain_main_component(image: Image.Image) -> Image.Image:
    """Remove neighboring-cell bleed while retaining the cell's main sprite."""

    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    alpha_pixels = alpha.load()
    width, height = rgba.size
    visited = bytearray(width * height)
    components: list[tuple[list[tuple[int, int]], tuple[int, int, int, int]]] = []

    for start_y in range(height):
        for start_x in range(width):
            index = start_y * width + start_x
            if visited[index] or alpha_pixels[start_x, start_y] == 0:
                continue

            visited[index] = 1
            queue = deque([(start_x, start_y)])
            points: list[tuple[int, int]] = []
            min_x = max_x = start_x
            min_y = max_y = start_y

            while queue:
                x, y = queue.popleft()
                points.append((x, y))
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        neighbor_x = x + dx
                        neighbor_y = y + dy
                        if not (0 <= neighbor_x < width and 0 <= neighbor_y < height):
                            continue
                        neighbor_index = neighbor_y * width + neighbor_x
                        if visited[neighbor_index]:
                            continue
                        if alpha_pixels[neighbor_x, neighbor_y] == 0:
                            continue
                        visited[neighbor_index] = 1
                        queue.append((neighbor_x, neighbor_y))

            components.append((points, (min_x, min_y, max_x + 1, max_y + 1)))

    if not components:
        raise ValueError("Sprite cell contains no visible pixels")

    components.sort(key=lambda component: len(component[0]), reverse=True)
    main_points, main_bbox = components[0]
    kept_points = list(main_points)
    main_left, main_top, main_right, main_bottom = main_bbox

    # Keep small nearby pieces such as a hair tuft, but reject fragments that
    # leaked across a generated grid boundary from another direction row.
    for points, bbox in components[1:]:
        left, top, right, bottom = bbox
        horizontal_gap = max(main_left - right, left - main_right, 0)
        vertical_gap = max(main_top - bottom, top - main_bottom, 0)
        if max(horizontal_gap, vertical_gap) <= 5 and len(points) >= 6:
            kept_points.extend(points)

    cleaned_alpha = Image.new("L", rgba.size, 0)
    cleaned_pixels = cleaned_alpha.load()
    for x, y in kept_points:
        cleaned_pixels[x, y] = alpha_pixels[x, y]
    rgba.putalpha(cleaned_alpha)
    return rgba


def fit_sprite(sprite: Image.Image) -> Image.Image:
    sprite = retain_main_component(sprite)
    bbox = sprite.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Sprite cell contains no visible pixels")

    cropped = sprite.crop(bbox)
    # A fixed visible footprint keeps front/back and left/right directions from
    # appearing to change size when the avatar turns.
    resized = cropped.resize(
        (MAX_CHARACTER_WIDTH, MAX_CHARACTER_HEIGHT), Image.Resampling.NEAREST
    )

    rgb = reduce_palette(resized, 32)
    alpha = resized.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    reduced = rgb.convert("RGBA")
    reduced.putalpha(alpha)
    return reduced


def validate_character_sheet(sheet: Image.Image, actor_id: str) -> None:
    for direction in range(SOURCE_ROWS):
        frame = sheet.crop(
            (
                direction * FRAME_WIDTH,
                0,
                (direction + 1) * FRAME_WIDTH,
                FRAME_HEIGHT,
            )
        )
        bbox = frame.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"{actor_id} direction {direction} is empty")
        visible_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        expected_size = (MAX_CHARACTER_WIDTH, MAX_CHARACTER_HEIGHT)
        if visible_size != expected_size:
            raise ValueError(
                f"{actor_id} direction {direction} has visible size {visible_size}; "
                f"expected {expected_size}"
            )


def build_characters() -> None:
    source = harden_alpha(Image.open(CHARACTER_SOURCE))
    if source.width % SOURCE_COLUMNS or source.height % SOURCE_ROWS:
        raise ValueError(
            f"Unexpected directional sheet size {source.size}; expected an exact {SOURCE_COLUMNS}x{SOURCE_ROWS} grid"
        )

    source_cell_width = source.width // SOURCE_COLUMNS
    source_cell_height = source.height // SOURCE_ROWS
    CHARACTER_ROOT.mkdir(parents=True, exist_ok=True)

    for column, actor_id in enumerate(CHARACTER_IDS):
        output = Image.new("RGBA", (FRAME_WIDTH * SOURCE_ROWS, FRAME_HEIGHT), (0, 0, 0, 0))
        for direction in range(SOURCE_ROWS):
            left = column * source_cell_width
            top = direction * source_cell_height
            cell = source.crop(
                (left, top, left + source_cell_width, top + source_cell_height)
            )
            sprite = fit_sprite(cell)
            x = direction * FRAME_WIDTH + (FRAME_WIDTH - sprite.width) // 2
            y = FRAME_HEIGHT - sprite.height - 3
            output.alpha_composite(sprite, (x, y))

        validate_character_sheet(output, actor_id)
        output.save(CHARACTER_ROOT / f"{actor_id}.png", optimize=True)


def main() -> None:
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    build_background()
    build_characters()
    print(f"Built {BACKGROUND_OUTPUT.relative_to(REPO_ROOT)}")
    for actor_id in CHARACTER_IDS:
        print(f"Built {(CHARACTER_ROOT / f'{actor_id}.png').relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
