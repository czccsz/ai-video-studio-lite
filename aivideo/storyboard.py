"""Validated, editable storyboard format shared by the GUI and CLI."""

import json
import math
from pathlib import Path


def _text(value, name, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name}必须是 1–{limit} 字的文字")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise ValueError(f"{name}包含不支持的控制字符")
    return value.strip()


def validate(data, *, allow_images=True):
    if not isinstance(data, dict):
        raise ValueError("分镜必须是 JSON 对象")
    title = _text(data.get("title"), "视频标题", 60)
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 12:
        raise ValueError("需要 1–12 个分镜")
    result = []
    for i, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError(f"分镜 {i} 必须是对象")
        duration = scene.get("duration", 6)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise ValueError(f"分镜 {i} 的 duration 必须是数字")
        if not math.isfinite(duration) or not 3 <= duration <= 30:
            raise ValueError(f"分镜 {i} 的时长必须在 3–30 秒之间")
        item = {
            "heading": _text(scene.get("heading"), f"分镜 {i} 标题", 32),
            "narration": _text(scene.get("narration"), f"分镜 {i} 旁白", 120),
            "duration": float(duration),
        }
        if allow_images and scene.get("image"):
            item["image"] = _text(scene["image"], "图片路径", 1024)
        result.append(item)
    return {"title": title, "scenes": result}


def load(path):
    path = Path(path).resolve()
    if path.stat().st_size > 256_000:
        raise ValueError("分镜文件过大，请限制在 256 KB 以内")
    data = validate(json.loads(path.read_text(encoding="utf-8-sig")))
    for scene in data["scenes"]:
        if "image" in scene:
            scene["image"] = str((path.parent / scene["image"]).resolve())
    return data


def dumps(data):
    return json.dumps(validate(data), ensure_ascii=False, indent=2)


def demo():
    return {
        "title": "把想法变成一条视频",
        "scenes": [
            {"heading": "先抓住一个问题", "narration": "别急着剪辑。先想清楚：这条视频，要帮谁解决什么问题？", "duration": 6},
            {"heading": "让 AI 帮你写分镜", "narration": "把主题拆成开头、重点和结尾。每个画面，只讲清楚一件事。", "duration": 6},
            {"heading": "配上画面与声音", "narration": "使用自己的图片，或直接使用文字卡片。需要旁白时，再开启在线配音。", "duration": 7},
            {"heading": "导出，再打磨", "narration": "检查事实、字幕和节奏，导出第一版。先完成，再把它做得更好。", "duration": 6},
        ],
    }
