import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from aivideo.render import render, run_ffmpeg, stamp
from aivideo.storyboard import demo


class RenderTests(unittest.TestCase):
    def test_caption_clock_rollover(self):
        self.assertEqual(stamp(59.9996), "00:01:00,000")
        self.assertEqual(stamp(3661.25), "01:01:01,250")

    def test_real_export_with_image_and_full_decode(self):
        with tempfile.TemporaryDirectory(prefix="video test '") as folder:
            root = Path(folder)
            source = root / "测试图片.png"
            Image.new("RGB", (200, 120), "#375875").save(source)
            data = demo()
            data["scenes"] = data["scenes"][:2]
            for scene in data["scenes"]:
                scene["duration"] = 3
            data["scenes"][0]["image"] = str(source)
            output = root / "成片 ' 文件夹"
            video = render(data, output, profile="preview", progress=lambda _: None)
            self.assertGreater(video.stat().st_size, 10_000)
            # Decode every audio/video packet, rather than only checking existence.
            result = run_ffmpeg(["-v", "error", "-i", video, "-f", "null", "-"])
            self.assertEqual(result.returncode, 0)
            subtitles = (output / "subtitles.srt").read_text(encoding="utf-8")
            self.assertIn("00:00:03,000 --> 00:00:06,000", subtitles)
            self.assertIn(data["scenes"][1]["narration"], subtitles)
            with self.assertRaises(FileExistsError):
                render(data, output, profile="preview", progress=lambda _: None)

    def test_missing_image_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            data = demo()
            data["scenes"][0]["image"] = str(Path(folder) / "missing.jpg")
            output = Path(folder) / "output"
            with self.assertRaisesRegex(ValueError, "图片不存在"):
                render(data, output)
            self.assertFalse(output.exists())

    def test_voice_failure_keeps_storyboard_without_fake_success(self):
        async def failure(*args):
            raise RuntimeError("offline")
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "output"
            with patch("aivideo.render.speak", failure):
                with self.assertRaisesRegex(RuntimeError, "在线配音失败"):
                    render(demo(), output, profile="preview", voice="test", progress=lambda _: None)
            self.assertTrue((output / "storyboard.json").exists())
            self.assertFalse((output / "video.mp4").exists())
