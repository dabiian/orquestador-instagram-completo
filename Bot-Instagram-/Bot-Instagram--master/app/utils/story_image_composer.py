import os
import textwrap
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps


STORY_WIDTH = 1080
STORY_HEIGHT = 1920


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Intenta cargar una fuente limpia y común en Windows.
    Si no encuentra ninguna, usa la default de PIL.
    """
    candidates = []

    if bold:
        candidates = [
            "arialbd.ttf",
            "Arial Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]
    else:
        candidates = [
            "arial.ttf",
            "Arial.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]

    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            continue

    return ImageFont.load_default()


def _fit_cover(image: Image.Image, size=(STORY_WIDTH, STORY_HEIGHT)) -> Image.Image:
    """
    Hace resize tipo cover para llenar 1080x1920 sin deformar.
    """
    return ImageOps.fit(image.convert("RGBA"), size, method=Image.Resampling.LANCZOS)


def _add_dark_gradient_overlay(image: Image.Image, opacity_top=20, opacity_bottom=150) -> Image.Image:
    """
    Agrega un degradado oscuro vertical para mejorar legibilidad del texto.
    """
    width, height = image.size
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for y in range(height):
        ratio = y / max(height - 1, 1)
        alpha = int(opacity_top + (opacity_bottom - opacity_top) * ratio)
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    return Image.alpha_composite(image, overlay)


def _wrap_text_by_width(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """
    Divide texto por ancho real en píxeles, no por cantidad fija de caracteres.
    """
    if not text:
        return []

    words = text.split()
    lines = []
    current = []

    for word in words:
        test_line = " ".join(current + [word]).strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def _draw_text_block(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font,
    fill=(255, 255, 255, 255),
    max_width: int = 900,
    line_spacing: int = 12,
    stroke_width: int = 2,
    stroke_fill=(0, 0, 0, 180),
):
    """
    Dibuja un bloque de texto envuelto y retorna la nueva coordenada Y.
    """
    lines = _wrap_text_by_width(draw, text, font, max_width)

    current_y = y
    for line in lines:
        draw.text(
            (x, current_y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        bbox = draw.textbbox((x, current_y), line, font=font, stroke_width=stroke_width)
        line_height = bbox[3] - bbox[1]
        current_y += line_height + line_spacing

    return current_y


def compose_story_image(
    background_image_path: str,
    output_image_path: str,
    headline: str = "",
    subheadline: str = "",
    cta: str = "",
    add_text: bool = True,
) -> str:
    """
    Genera la imagen final para story con texto limpio y legible.
    """
    if not os.path.exists(background_image_path):
        raise FileNotFoundError(f"No existe la imagen base: {background_image_path}")

    base = Image.open(background_image_path).convert("RGBA")
    base = _fit_cover(base, (STORY_WIDTH, STORY_HEIGHT))
    base = _add_dark_gradient_overlay(base)

    if add_text:
        draw = ImageDraw.Draw(base)

        headline_font = _load_font(92, bold=True)
        subheadline_font = _load_font(52, bold=False)
        cta_font = _load_font(46, bold=True)

        safe_left = 80
        safe_right = 80
        max_text_width = STORY_WIDTH - safe_left - safe_right

        # Safe area superior e inferior para UI de stories
        start_y = 980

        if headline:
            start_y = _draw_text_block(
                draw=draw,
                x=safe_left,
                y=start_y,
                text=headline.strip(),
                font=headline_font,
                fill=(255, 255, 255, 255),
                max_width=max_text_width,
                line_spacing=14,
                stroke_width=2,
            )
            start_y += 20

        if subheadline:
            start_y = _draw_text_block(
                draw=draw,
                x=safe_left,
                y=start_y,
                text=subheadline.strip(),
                font=subheadline_font,
                fill=(245, 245, 245, 255),
                max_width=max_text_width,
                line_spacing=10,
                stroke_width=2,
            )
            start_y += 30

        if cta:
            # caja CTA
            cta_text = cta.strip().upper()
            cta_bbox = draw.textbbox((0, 0), cta_text, font=cta_font, stroke_width=1)
            cta_w = cta_bbox[2] - cta_bbox[0]
            cta_h = cta_bbox[3] - cta_bbox[1]

            padding_x = 28
            padding_y = 18

            rect_x1 = safe_left
            rect_y1 = start_y
            rect_x2 = rect_x1 + cta_w + (padding_x * 2)
            rect_y2 = rect_y1 + cta_h + (padding_y * 2)

            draw.rounded_rectangle(
                [rect_x1, rect_y1, rect_x2, rect_y2],
                radius=28,
                fill=(255, 255, 255, 235),
            )

            draw.text(
                (rect_x1 + padding_x, rect_y1 + padding_y - 4),
                cta_text,
                font=cta_font,
                fill=(20, 20, 20, 255),
            )

    os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
    base.convert("RGB").save(output_image_path, format="PNG", quality=95)

    return os.path.abspath(output_image_path)