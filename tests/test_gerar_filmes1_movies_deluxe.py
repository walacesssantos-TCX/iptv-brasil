import importlib.util
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "builder", Path(__file__).resolve().parents[1] / "scripts/gerar_filmes1_movies_deluxe.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuilderTests(unittest.TestCase):
    def test_incremental_batch_and_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db, out, cache = root / "movies.json", root / "filmes1.m3u", root / "cache.json"
            curated = root / "curated.json"
            db.write_text(json.dumps({str(i): {
                "title": f"Movie {i}", "year": 2018, "sources": [{"type": "archive.org", "id": f"item{i}"}]
            } for i in range(3)}))
            original = 'LibreFlix (2018)\nhttps://example.org/film.mp4\n'
            curated.write_text(json.dumps([{"title": "LibreFlix", "year": 2018, "url": "https://example.org/film.mp4"}]))
            out.write_text("#EXTM3U\n" + original)
            def resolve(identifier):
                return {"status": "ok", "url": f"https://archive.org/download/{identifier}/film.mp4",
                        "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/", "release_year": 2018, "item_title": "Movie " + identifier[-1]}
            with patch.multiple(builder, DB=db, OUT=out, CACHE=cache, CURATED=curated, BATCH_SIZE=2), patch.object(builder, "resolve_identifier", side_effect=resolve) as resolver:
                builder.main()
                self.assertEqual(resolver.call_count, 2)
                self.assertEqual(out.read_text().count("#EXTINF"), 3)
                builder.main()
                self.assertEqual(resolver.call_count, 3)
                self.assertEqual(out.read_text().count("#EXTINF"), 4)
                self.assertIn(original, out.read_text())
                builder.main()
                self.assertEqual(resolver.call_count, 3)

    def test_transient_errors_retry_later_and_legacy_cache_rechecks(self):
        self.assertTrue(builder.needs_resolution("", 100000))
        self.assertTrue(builder.needs_resolution("https://archive.org/download/id/video.mp4", 100000))
        self.assertFalse(builder.needs_resolution({"status": "retry", "checked_at": 99999}, 100000))
        self.assertTrue(builder.needs_resolution({"status": "retry", "checked_at": 1}, 100000))
        with patch.object(builder, "request_bytes", side_effect=urllib.error.URLError("timeout")):
            self.assertEqual(builder.resolve_identifier("id")["status"], "retry")

    def test_license_filter_and_video_validation(self):
        licensed = {"licenseurl": "http://creativecommons.org/licenses/by/4.0/"}
        self.assertTrue(builder.license_evidence(licensed))
        self.assertFalse(builder.license_evidence({"licenseurl": "https://creativecommons.org.evil.test/licenses/by/4.0/"}))
        self.assertFalse(builder.license_evidence({"description": "free movie"}))
        with patch.object(builder, "request_bytes", return_value=b'{"metadata":{"title":"Test"},"files":[]}'), patch.object(builder, "validate_video_url") as validate:
            self.assertEqual(builder.resolve_identifier("id")["status"], "unlicensed")
            validate.assert_not_called()
        payload = {"metadata": dict(licensed, year="2018"), "files": [{"name": "movie.mp4", "size": 10000000, "format": "h.264"}]}
        with patch.object(builder, "request_bytes", return_value=json.dumps(payload).encode()), patch.object(builder, "validate_video_url", return_value=True):
            result = builder.resolve_identifier("id with spaces")
            self.assertEqual(result["status"], "ok")
            self.assertIn("id%20with%20spaces/movie.mp4", result["url"])
        with patch.object(builder, "request_bytes", return_value=json.dumps(payload).encode()), patch.object(builder, "validate_video_url", return_value=False):
            self.assertEqual(builder.resolve_identifier("id")["status"], "retry")

    def test_select_h264_derivative_and_exclude_private_trailer(self):
        files = [
            {"name": "original.mp4", "size": 90000000, "source": "original", "format": "MPEG4"},
            {"name": "movie.mp4", "size": 9000000, "source": "derivative", "format": "h.264"},
            {"name": "movie1080.mp4", "size": 900000000, "private": "true"},
            {"name": "trailer.mp4", "size": 900000000},
        ]
        self.assertEqual(builder.choose_from_files(files), "movie.mp4")

    def test_old_and_unknown_years_are_excluded(self):
        self.assertEqual(builder.release_year({"metadata": {"Year": "1936"}, "year": 2025}), 1936)
        licensed = {"licenseurl": "https://creativecommons.org/licenses/by/4.0/", "year": "1936"}
        with patch.object(builder, "request_bytes", return_value=json.dumps({"metadata": licensed}).encode()), patch.object(builder, "validate_video_url") as validate:
            self.assertEqual(builder.resolve_identifier("classic")["status"], "old_or_undated")
            validate.assert_not_called()
        self.assertEqual(builder.cache_url({"status": "ok", "url": "old.mp4", "release_year": 1936}), "")
        self.assertEqual(builder.cache_url({"status": "ok", "url": "unknown.mp4"}), "")
        self.assertTrue(builder.needs_resolution({"status": "ok", "url": "legacy.mp4"}, 100000))
        self.assertFalse(builder.matching_title({"title": "The Last Human Taxi Driver"}, "Taxi Driver Film and Analysis"))
        self.assertTrue(builder.matching_title({"title": "Spring"}, "Spring - Blender Open Movie"))

    def test_corrupt_cache_does_not_silently_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "cache.json"
            cache.write_text("invalid")
            with patch.object(builder, "CACHE", cache), self.assertRaises(RuntimeError):
                builder.load_cache()


if __name__ == "__main__":
    unittest.main()
