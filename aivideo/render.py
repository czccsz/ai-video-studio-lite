"""Render local cards, optional online narration, and scene-level subtitles."""

import asyncio
import json
import math
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

from .cards import find_font, make_card
from .storyboard import validate

PROFILES = {"vertical": (720, 1280), "landscape": (1280, 720), "preview": (360, 640)}


def run_ffmpeg(args):
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-nostdin", *map(str, args)]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=600)
    except subprocess.TimeoutExpired:
        raise RuntimeError("视频处理超过 10 分钟，请降低分辨率或减少分镜后重试") from None
    if result.returncode:
        raise RuntimeError("视频处理失败：" + result.stderr.decode("utf-8", errors="replace")[-1800:])
    return result


def audio_seconds(path):
    # FFmpeg emits file metadata before intentionally exiting without an output.
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                            capture_output=True, timeout=30,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    match = re.search(rb"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        raise RuntimeError("无法读取配音时长")
    h, m, s = map(float, match.groups())
    return 3600 * h + 60 * m + s


async def speak(text, voice, path):
    try:
        import edge_tts
    except ImportError:
        raise RuntimeError('请先安装配音组件：pip install -e ".[voice]"') from None
    await asyncio.wait_for(edge_tts.Communicate(text, voice).save(str(path)), timeout=90)


def stamp(seconds):
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    seconds, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def render(data, output, *, profile="vertical", font=None, voice=None, progress=print):
    data = validate(data)
    if profile not in PROFILES:
        raise ValueError("不支持的画面比例")
    font_path = find_font(font)
    for scene in data["scenes"]:
        if scene.get("image") and not Path(scene["image"]).is_file():
            raise ValueError(f"图片不存在：{scene['image']}")
    output = Path(output).resolve()
    # Never merge with a previous render or overwrite an existing file.
    output.mkdir(parents=True, exist_ok=False)
    (output / "storyboard.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    work = output / "assets"
    work.mkdir()
    timings, captions = [], []
    elapsed = 0.0
    width, height = PROFILES[profile]
    for i, scene in enumerate(data["scenes"]):
        progress(f"正在制作分镜 {i + 1}/{len(data['scenes'])}：{scene['heading']}")
        # Cards are designed vertically; landscape uses centered pillarboxing.
        card = work / f"card-{i:02}.png"
        make_card(data["title"], scene, i, len(data["scenes"]), card, font_path,
                  (360, 640) if profile == "preview" else (720, 1280))
        audio = work / f"voice-{i:02}.mp3"
        duration = scene["duration"]
        if voice:
            progress("正在请求在线配音……")
            try:
                asyncio.run(speak(scene["narration"], voice, audio))
                duration = max(duration, audio_seconds(audio) + 0.4)
            except Exception as exc:
                raise RuntimeError("在线配音失败。可关闭配音后重试；分镜已保存在输出目录。" ) from exc
        duration = math.ceil(duration * 24) / 24
        clip = work / f"clip-{i:02}.mp4"
        args = ["-y", "-loop", "1", "-framerate", "24", "-i", card]
        args += ["-i", audio] if voice else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        fade_out = max(0, duration - 0.25)
        filters = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x141830,"
                   f"fade=t=in:st=0:d=0.2,fade=t=out:st={fade_out}:d=0.25,format=yuv420p")
        args += ["-vf", filters, "-af", "apad", "-t", f"{duration:.6f}", "-map", "0:v:0", "-map", "1:a:0",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-r", "24",
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k", "-movflags", "+faststart", clip]
        run_ffmpeg(args)
        captions.append(f"{i + 1}\n{stamp(elapsed)} --> {stamp(elapsed + duration)}\n{scene['narration']}\n")
        timings.append({"scene": i + 1, "start": elapsed, "duration": duration})
        elapsed += duration
    # Only generated relative names enter the concat manifest, never user paths.
    manifest = work / "concat.txt"
    manifest.write_text("\n".join(f"file 'clip-{i:02}.mp4'" for i in range(len(data["scenes"]))) + "\n", encoding="utf-8")
    progress("正在合并 MP4 和导出字幕……")
    run_ffmpeg(["-y", "-f", "concat", "-safe", "1", "-i", manifest, "-c", "copy", "-movflags", "+faststart", output / "video.mp4"])
    (output / "subtitles.srt").write_text("\n".join(captions), encoding="utf-8")
    (output / "timings.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
    progress(f"已完成：{output / 'video.mp4'}")
    return output / "video.mp4"
