"""Konwertuje dostarczoną grafikę PNG na ikonę aplikacji macOS.

Wykrywa obrys squircle'a (skan jasności), kadruje, wpasowuje w siatkę ikon
macOS (824 px treści na płótnie 1024) i maskuje rogi na przezroczysto.
Wyjście: assets/icon_1024.png + assets/AppIcon.icns.

  .venv/bin/python scripts/make_icon_from_png.py <plik.png>
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSCompositingOperationSourceOver,
    NSImage,
    NSMakeRect,
    NSPNGFileType,
)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CANVAS = 1024
CONTENT = 824  # standardowa siatka ikon macOS
RADIUS = CONTENT * 0.225


def content_bbox(path: Path) -> tuple[int, int, int, int]:
    """Bounding box jasnej treści (squircle świeci na czarnym tle)."""
    rep = NSBitmapImageRep.imageRepWithData_(path.read_bytes())
    w, h = rep.pixelsWide(), rep.pixelsHigh()
    buf = np.frombuffer(rep.bitmapData(), dtype=np.uint8)
    bpp = rep.bitsPerPixel() // 8  # uwaga: bywa 4 (RGBX) przy samplesPerPixel == 3
    row = rep.bytesPerRow()
    img = buf[: h * row].reshape(h, row)[:, : w * bpp].reshape(h, w, bpp)
    lum = img[:, :, :3].astype(np.uint16).sum(axis=2)
    mask = lum > 140  # wyraźny obrys squircle'a, nie łapiemy halo poświaty
    ys, xs = np.where(mask)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    margin = int((x1 - x0) * 0.03)  # mały oddech na krawędź szkła
    return x0 - margin, y0 - margin, x1 + margin, y1 + margin


def main() -> None:
    src = Path(sys.argv[1]).expanduser()
    x0, y0, x1, y1 = content_bbox(src)
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    image = NSImage.alloc().initWithContentsOfFile_(str(src))
    src_w, src_h = image.size().width, image.size().height
    rep0 = NSBitmapImageRep.imageRepWithData_(src.read_bytes())
    # przelicznik pikseli bboxa na punkty NSImage (uwaga na oś Y w górę)
    sx, sy = src_w / rep0.pixelsWide(), src_h / rep0.pixelsHigh()

    out = NSImage.alloc().initWithSize_((CANVAS, CANVAS))
    out.lockFocus()
    offset = (CANVAS - CONTENT) / 2
    clip = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(offset, offset, CONTENT, CONTENT), RADIUS, RADIUS
    )
    clip.addClip()
    # źródłowy kwadrat wokół środka squircle'a -> cały obszar CONTENT
    crop = NSMakeRect(
        (cx - side / 2) * sx,
        src_h - (cy + side / 2) * sy,  # konwersja na układ y-w-górę
        side * sx,
        side * sy,
    )
    image.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(offset, offset, CONTENT, CONTENT),
        crop,
        NSCompositingOperationSourceOver,
        1.0,
    )
    out.unlockFocus()

    ASSETS.mkdir(exist_ok=True)
    png = ASSETS / "icon_1024.png"
    rep = NSBitmapImageRep.imageRepWithData_(out.TIFFRepresentation())
    png.write_bytes(bytes(rep.representationUsingType_properties_(NSPNGFileType, None)))
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
    main()
