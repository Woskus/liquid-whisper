"""Generuje prowizoryczne logo Liquid Whisper: chromatyczna kropla na ciemnym
squircle (motyw jak HUD). Wyjście: assets/icon_1024.png + assets/AppIcon.icns.

  .venv/bin/python scripts/make_icon.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSColor,
    NSGradient,
    NSImage,
    NSMakePoint,
    NSMakeRect,
    NSPNGFileType,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024


def srgb(r: float, g: float, b: float, a: float = 1.0) -> NSColor:
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, a)


def draw_icon() -> NSImage:
    img = NSImage.alloc().initWithSize_((SIZE, SIZE))
    img.lockFocus()

    # tło: ciemny squircle (proporcje jak ikony macOS)
    inset = SIZE * 0.06
    rect = NSMakeRect(inset, inset, SIZE - 2 * inset, SIZE - 2 * inset)
    bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(rect, SIZE * 0.21, SIZE * 0.21)
    NSGradient.alloc().initWithStartingColor_endingColor_(
        srgb(0.055, 0.055, 0.075), srgb(0.11, 0.11, 0.15)
    ).drawInBezierPath_angle_(bg, 90)

    # subtelny pierścień na krawędzi squircle'a
    srgb(1, 1, 1, 0.07).setStroke()
    bg.setLineWidth_(SIZE * 0.008)
    bg.stroke()

    # kropla: okrąg + wyciągnięty wierzchołek (współrzędne AppKit: y w górę)
    cx, cy, r = SIZE / 2, SIZE * 0.40, SIZE * 0.20
    tip_y = SIZE * 0.78
    drop = NSBezierPath.bezierPath()
    drop.moveToPoint_(NSMakePoint(cx, tip_y))
    drop.curveToPoint_controlPoint1_controlPoint2_(
        NSMakePoint(cx + r, cy),
        NSMakePoint(cx + r * 0.12, tip_y - r * 0.95),
        NSMakePoint(cx + r, cy + r * 0.9),
    )
    drop.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
        NSMakePoint(cx, cy), r, 0.0, 180.0, True
    )
    drop.curveToPoint_controlPoint1_controlPoint2_(
        NSMakePoint(cx, tip_y),
        NSMakePoint(cx - r, cy + r * 0.9),
        NSMakePoint(cx - r * 0.12, tip_y - r * 0.95),
    )
    drop.closePath()

    # chromatyczny gradient (jak preset chromatic w metal-fx)
    chroma = NSGradient.alloc().initWithColors_(
        [
            srgb(0.55, 0.85, 1.0),   # cyjan
            srgb(0.72, 0.62, 1.0),   # fiolet
            srgb(1.0, 0.62, 0.78),   # róż
            srgb(1.0, 0.85, 0.55),   # złoto
        ]
    )
    chroma.drawInBezierPath_angle_(drop, -55.0)

    # odbicie światła: jaśniejszy owal w górnej-lewej części kropli
    hl = NSBezierPath.bezierPathWithOvalInRect_(
        NSMakeRect(cx - r * 0.62, cy + r * 0.05, r * 0.66, r * 0.92)
    )
    NSGradient.alloc().initWithStartingColor_endingColor_(
        srgb(1, 1, 1, 0.55), srgb(1, 1, 1, 0.0)
    ).drawInBezierPath_angle_(hl, -80.0)

    img.unlockFocus()
    return img


def save_png(img: NSImage, path: Path) -> None:
    rep = NSBitmapImageRep.imageRepWithData_(img.TIFFRepresentation())
    path.write_bytes(bytes(rep.representationUsingType_properties_(NSPNGFileType, None)))


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    png = ASSETS / "icon_1024.png"
    save_png(draw_icon(), png)
    print(f"zapisano {png}")

    iconset = ASSETS / "AppIcon.iconset"
    iconset.mkdir(exist_ok=True)
    for pt in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            px = pt * scale
            name = f"icon_{pt}x{pt}{'@2x' if scale == 2 else ''}.png"
            subprocess.run(
                ["sips", "-z", str(px), str(px), str(png), "--out", str(iconset / name)],
                check=True,
                capture_output=True,
            )
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "AppIcon.icns")],
        check=True,
    )
    print(f"zapisano {ASSETS / 'AppIcon.icns'}")


if __name__ == "__main__":
    sys.exit(main())
