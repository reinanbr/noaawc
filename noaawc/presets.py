# mypy: disable-error-code="attr-defined"

from __future__ import annotations

from typing import Any

QUALITY_PRESETS_SQUARE: dict[str, dict[str, Any]] = {
    "sd": {
        "dpi": 72,
        "figsize": (8.0, 8.0),
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "Standard Definition — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (10.0, 10.0),
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD (1080p-range) — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.07, 17.07),
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K — maximum quality, large file and slow render",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.07, 17.07),
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K @ 60 fps — silky smooth, very large file",
    },
}

QUALITY_PRESETS_WIDE: dict[str, dict[str, Any]] = {
    "sd": {
        "dpi": 72,
        "figsize": (17.7778, 10.0000),
        "fps": 6,
        "codec": "libx264",
        "quality": 6,
        "description": "SD 720p 16:9 — fast render, small file",
    },
    "hd": {
        "dpi": 120,
        "figsize": (16.0000, 9.0000),
        "fps": 24,
        "codec": "libx264",
        "quality": 8,
        "description": "Full HD 1080p 16:9 — balanced quality and speed",
    },
    "4k": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),
        "fps": 30,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 — maximum quality, large file",
    },
    "4k_60": {
        "dpi": 220,
        "figsize": (17.4545, 9.8182),
        "fps": 60,
        "codec": "libx264",
        "quality": 10,
        "description": "Ultra HD 4K 16:9 @ 60 fps — silky smooth, very large file",
    },
}

# Backward-compatible alias
QUALITY_PRESETS = QUALITY_PRESETS_SQUARE


def list_quality_presets(wide: bool = False) -> None:
    """Print all available quality presets and their settings."""
    presets = QUALITY_PRESETS_WIDE if wide else QUALITY_PRESETS_SQUARE
    label = "16:9 wide" if wide else "square"
    print(f"\n  Quality presets ({label})\n")
    print(
        f"  {'Preset':<10}  {'DPI':<5}  {'Figsize (in)':<20}  {'FPS':<5}  {'Codec':<10}  Description"
    )
    print("  " + "─" * 100)
    for name, p in presets.items():
        w, h = p["figsize"]
        px_w = int(w * p["dpi"])
        px_h = int(h * p["dpi"])
        print(
            f"  {name:<10}  {p['dpi']:<5}  {w:.1f}×{h:.1f} ({px_w}×{px_h} px)"
            f"{'':>2}  {p['fps']:<5}  {p['codec']:<10}  {p['description']}"
        )
    print()
