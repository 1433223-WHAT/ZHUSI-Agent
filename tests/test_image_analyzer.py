import io
import unittest
from unittest.mock import patch

from PIL import Image

from image_analyzer import ImageAnalysisError, analyze_architecture_image, inspect_image


def png_bytes(width=120, height=80):
    stream = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(stream, format="PNG")
    return stream.getvalue()


class ImageInspectionTests(unittest.TestCase):
    def test_png_is_validated_and_dimensions_are_read(self):
        result = inspect_image("场地.png", png_bytes())
        self.assertEqual("image/png", result["mime_type"])
        self.assertEqual(120, result["width"])
        self.assertEqual(80, result["height"])

    def test_fake_image_extension_is_rejected(self):
        with self.assertRaises(ImageAnalysisError):
            inspect_image("伪装.jpg", b"not an image")

    def test_unsupported_image_type_is_rejected(self):
        with self.assertRaises(ImageAnalysisError):
            inspect_image("图纸.gif", b"GIF89a")

    def test_large_image_is_rejected(self):
        with self.assertRaises(ImageAnalysisError):
            inspect_image("过大.png", b"x" * (8 * 1024 * 1024 + 1))


class ImageAnalysisTests(unittest.TestCase):
    @patch("image_analyzer._call_qwen_vl")
    def test_analysis_separates_observation_inference_and_unknowns(self, mock_call):
        mock_call.return_value = {
            "image_type": "site_photo",
            "visible_facts": ["画面中央可见一栋三层建筑"],
            "inferences": [{"content": "可能是教学建筑", "basis": "重复开间和走廊界面", "confidence": "medium"}],
            "unknowns": ["无法从单张照片确认建筑尺寸"],
            "architecture_questions": ["主要人流从哪个方向进入场地？"],
            "warnings": [],
        }
        result = analyze_architecture_image("场地.png", png_bytes(), "分析周边关系")
        self.assertEqual("analyzed", result["status"])
        self.assertEqual(["画面中央可见一栋三层建筑"], result["visible_facts"])
        self.assertEqual("medium", result["inferences"][0]["confidence"])
        self.assertTrue(result["unknowns"])
        self.assertTrue(result["architecture_questions"])

    @patch("image_analyzer._call_qwen_vl", side_effect=RuntimeError("vision timeout"))
    def test_model_failure_is_reported_truthfully(self, _mock_call):
        result = analyze_architecture_image("场地.png", png_bytes(), "")
        self.assertEqual("failed", result["status"])
        self.assertIn("vision timeout", result["error"])
        self.assertEqual([], result["visible_facts"])


if __name__ == "__main__":
    unittest.main()
