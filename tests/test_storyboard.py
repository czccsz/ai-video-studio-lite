import json
import tempfile
import unittest
from pathlib import Path

from aivideo.storyboard import demo, load, validate


class StoryboardTests(unittest.TestCase):
    def test_demo_and_unknown_fields(self):
        data = dict(demo(), api_key="should-never-be-exported")
        self.assertNotIn("api_key", validate(data))
        self.assertEqual(len(validate(data)["scenes"]), 4)

    def test_invalid_durations(self):
        for duration in [True, "6", 0, float("nan"), float("inf"), 31]:
            with self.subTest(duration=duration):
                data = demo()
                data["scenes"][0]["duration"] = duration
                with self.assertRaises(ValueError):
                    validate(data)

    def test_invalid_shapes_and_text(self):
        for data in [[], {}, {"title": "x", "scenes": []}, {"title": "x", "scenes": ["bad"]}]:
            with self.assertRaises(ValueError):
                validate(data)
        data = demo()
        data["scenes"][0]["narration"] = "x" * 121
        with self.assertRaises(ValueError):
            validate(data)

    def test_model_cannot_select_local_images(self):
        data = demo()
        data["scenes"][0]["image"] = "private-image.jpg"
        self.assertNotIn("image", validate(data, allow_images=False)["scenes"][0])

    def test_relative_images_use_storyboard_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = demo()
            data["scenes"][0]["image"] = "images/photo.jpg"
            path = root / "story.json"
            path.write_text(json.dumps(data), encoding="utf-8-sig")
            self.assertEqual(load(path)["scenes"][0]["image"], str(root / "images/photo.jpg"))


if __name__ == "__main__":
    unittest.main()
