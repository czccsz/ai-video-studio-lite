"""Original Pillow title cards; no stock assets or bundled fonts."""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


def find_font(explicit=None):
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ValueError("指定字体文件不存在")
        return str(path)
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc",
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    raise ValueError("未找到中文字体，请使用 --font 指定 .ttf/.ttc/.otf 字体文件")


def wrap_text(draw, text, font, width):
    lines, current = [], ""
    for char in text:
        if char == "\n":
            lines.append(current)
            current = ""
        elif current and draw.textlength(current + char, font=font) > width:
            lines.append(current)
            current = char
        else:
            current += char
    if current:
        lines.append(current)
    return lines or [""]


def block(draw, text, font_path, max_size, min_size, box, fill):
    x, y, width, height = box
    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(draw, text, font, width)
        step = int(size * 1.55)
        if len(lines) * step <= height:
            for line in lines:
                draw.text((x, y), line, font=font, fill=fill, anchor="lt")
                y += step
            return
    raise ValueError("文字过长，无法放入画面，请缩短标题或旁白")


def make_card(story_title, scene, index, count, path, font_path, size=(720, 1280)):
    width, height = size
    scale = width / 720
    canvas = Image.new("RGB", size)
    draw = ImageDraw.Draw(canvas)
    for y in range(height):
        t = y / height
        draw.line((0, y, width, y), fill=(int(20 + 14 * t), int(24 + 8 * t), int(48 + 22 * t)))
    if scene.get("image"):
        with Image.open(scene["image"]) as source:
            background = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"), size)
        canvas = Image.blend(background, canvas, 0.66)
        draw = ImageDraw.Draw(canvas)
    def n(value):
        return max(1, round(value * scale))
    margin = n(62)
    accent = "#C5F36B"
    draw.rounded_rectangle((margin, n(84), margin + n(168), n(126)), radius=n(21), fill=accent)
    draw.text((margin + n(18), n(94)), f"STORY {index + 1:02d}", font=ImageFont.truetype(font_path, n(20)), fill="#172021", anchor="lt")
    block(draw, story_title, font_path, n(24), n(14), (margin, n(156), width - 2 * margin, n(110)), "#ABB4CC")
    draw.text((margin - n(6), n(285)), f"{index + 1:02d}", font=ImageFont.truetype(font_path, n(144)), fill=accent, anchor="lt")
    block(draw, scene["heading"], font_path, n(65), n(30), (margin, n(495), width - 2 * margin, n(270)), "#FFFFFF")
    draw.rounded_rectangle((margin - n(20), n(850), width - margin + n(20), n(1170)), radius=n(22), fill="#10182B")
    block(draw, scene["narration"], font_path, n(31), n(18), (margin, n(885), width - 2 * margin, n(250)), "#E5EBF5")
    gap = n(10)
    bar = (width - 2 * margin - gap * (count - 1)) / count
    for i in range(count):
        x = margin + i * (bar + gap)
        draw.rounded_rectangle((x, n(1220), x + bar, n(1226)), radius=n(3), fill=accent if i <= index else "#475068")
    canvas.save(path)
