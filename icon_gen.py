"""
icon_gen.py — Vault Zero icon generator
Generates assets/icon.png programmatically so no external image file is needed.
Players can replace assets/icon.png with their own 256×256 image.
"""
import os

BASE     = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE, "assets")
ICON_PATH= os.path.join(ICON_DIR, "icon.png")


def generate_icon(size: int = 256) -> str | None:
    """
    Draw the Vault Zero icon — a stylised vault door —
    and save it to assets/icon.png. Returns path or None.
    """
    os.makedirs(ICON_DIR, exist_ok=True)

    if os.path.exists(ICON_PATH):
        return ICON_PATH

    # Try PIL/Pillow first
    try:
        from PIL import Image, ImageDraw, ImageFont
        img  = Image.new("RGBA", (size, size), (10, 9, 7, 255))
        draw = ImageDraw.Draw(img)

        cx, cy = size // 2, size // 2
        r = int(size * 0.44)

        # Outer ring (gold)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                     outline=(212, 168, 83), width=max(3, size//40))

        # Inner circle (dark)
        ri = int(r * 0.75)
        draw.ellipse([cx-ri, cy-ri, cx+ri, cy+ri],
                     fill=(14, 12, 10), outline=(160, 120, 48), width=max(2, size//60))

        # Spokes (vault wheel)
        import math
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1  = cx + int(ri * 0.25 * math.cos(rad))
            y1  = cy + int(ri * 0.25 * math.sin(rad))
            x2  = cx + int(ri * 0.88 * math.cos(rad))
            y2  = cy + int(ri * 0.88 * math.sin(rad))
            draw.line([x1, y1, x2, y2], fill=(212, 168, 83), width=max(2, size//60))

        # Centre circle
        rc = int(r * 0.20)
        draw.ellipse([cx-rc, cy-rc, cx+rc, cy+rc],
                     fill=(212, 168, 83))

        # "VZ" text
        try:
            font = ImageFont.truetype("arial.ttf", size // 6)
        except Exception:
            font = ImageFont.load_default()
        text = "VZ"
        bb   = draw.textbbox((0, 0), text, font=font)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        draw.text((cx - tw//2, cy - th//2 + int(r*0.55)),
                  text, fill=(212, 168, 83), font=font)

        img.save(ICON_PATH, "PNG")
        print(f"[icon] generated {ICON_PATH}")
        return ICON_PATH

    except ImportError:
        pass

    # Fallback: use pygame to draw the icon
    try:
        import pygame
        pygame.init()
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        surf.fill((10, 9, 7, 255))

        cx, cy = size // 2, size // 2
        r  = int(size * 0.44)
        ri = int(r * 0.75)

        # Gold outer ring
        pygame.draw.circle(surf, (212, 168, 83), (cx, cy), r, max(3, size//40))
        # Dark inner
        pygame.draw.circle(surf, (14, 12, 10),   (cx, cy), ri)
        pygame.draw.circle(surf, (160, 120, 48), (cx, cy), ri, max(2, size//60))

        import math
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = cx + int(ri * 0.25 * math.cos(rad))
            y1 = cy + int(ri * 0.25 * math.sin(rad))
            x2 = cx + int(ri * 0.88 * math.cos(rad))
            y2 = cy + int(ri * 0.88 * math.sin(rad))
            pygame.draw.line(surf, (212, 168, 83), (x1, y1), (x2, y2), max(2, size//60))

        rc = int(r * 0.20)
        pygame.draw.circle(surf, (212, 168, 83), (cx, cy), rc)

        pygame.image.save(surf, ICON_PATH)
        pygame.quit()
        print(f"[icon] generated {ICON_PATH} via pygame")
        return ICON_PATH

    except Exception as e:
        print(f"[icon] generation failed: {e}")
        return None


def load_qt_icon():
    """Return a QIcon for the app, generating it if needed."""
    path = generate_icon()
    if not path:
        return None
    try:
        from PyQt6.QtGui import QIcon
        return QIcon(path)
    except Exception:
        return None
