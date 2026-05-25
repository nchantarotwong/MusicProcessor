import os
import tempfile
import unittest
from unittest.mock import patch

from musiclib.analyze import (
    _get_tag_value,
    analyze_quality,
    audit_quality,
    choose_aac_bitrate,
    decide_encoding_strategy,
    run_rsgain,
    write_quality_audit_reports,
)


class EncodingStrategyTests(unittest.TestCase):
    def audio_info(self, ext, **overrides):
        info = {
            "ext": ext,
            "sample_rate": 44100,
            "bits_per_sample": None,
            "bitrate": 320,
            "duration": 180,
            "codec": None,
            "codec_description": None,
            "parser": None,
        }
        info.update(overrides)
        return info

    def test_lossy_sources_are_copied(self):
        cases = [
            (".mp3", {}),
            (".aac", {}),
            (".m4a", {"codec": "mp4a.40.2"}),
            (".mp4", {"codec": "mp4a.40.2"}),
            (".ogg", {}),
            (".wma", {}),
        ]
        for ext, overrides in cases:
            with self.subTest(ext=ext):
                strategy = decide_encoding_strategy(self.audio_info(ext, **overrides))

                self.assertEqual(strategy["format"], "copy")
                self.assertEqual(strategy["extension"], ext)

    def test_flac_sources_are_copied(self):
        strategy = decide_encoding_strategy(self.audio_info(".flac"))

        self.assertEqual(strategy["format"], "copy")
        self.assertEqual(strategy["extension"], ".flac")

    def test_non_flac_lossless_sources_convert_to_flac(self):
        cases = [
            (".alac", {}),
            (".m4a", {"codec": "alac"}),
            (".mp4", {"codec": "alac"}),
            (".wav", {}),
            (".aiff", {}),
            (".aif", {}),
        ]
        for ext, overrides in cases:
            with self.subTest(ext=ext, overrides=overrides):
                strategy = decide_encoding_strategy(self.audio_info(ext, **overrides))

                self.assertEqual(strategy["format"], "flac")
                self.assertEqual(strategy["extension"], ".flac")

    def test_aac_bitrate_uses_kbps_units(self):
        self.assertEqual(choose_aac_bitrate({"bitrate": 96}), "128k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 128}), "160k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 191}), "160k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 192}), "192k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 255}), "192k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 256}), "256k")
        self.assertEqual(choose_aac_bitrate({"bitrate": 320}), "256k")


class ReplayGainTests(unittest.TestCase):
    def test_run_rsgain_track_profile_disables_album_tags(self):
        with patch("musiclib.analyze.subprocess.run") as run:
            run_rsgain("/music/out", gain_profile="track", threads=2)

        run.assert_called_once_with(
            [
                "rsgain",
                "easy",
                "--skip-existing",
                "--multithread=2",
                "-p",
                "no_album",
                "/music/out",
            ],
            check=True,
        )

    def test_run_rsgain_album_profile_keeps_album_tags(self):
        with patch("musiclib.analyze.subprocess.run") as run:
            run_rsgain("/music/out", gain_profile="album", threads=2)

        run.assert_called_once_with(
            [
                "rsgain",
                "easy",
                "--skip-existing",
                "--multithread=2",
                "/music/out",
            ],
            check=True,
        )

    def test_get_tag_value_reads_plain_replaygain_tags_case_insensitively(self):
        tags = {"REPLAYGAIN_TRACK_GAIN": ["-7.25 dB"]}

        self.assertEqual(_get_tag_value(tags, "replaygain_track_gain"), "-7.25 dB")

    def test_get_tag_value_reads_mp4_freeform_replaygain_tags(self):
        tags = {"----:com.apple.iTunes:replaygain_track_gain": [b"-7.25 dB"]}

        self.assertEqual(_get_tag_value(tags, "replaygain_track_gain"), "-7.25 dB")


class QualityAuditTests(unittest.TestCase):
    def test_analyze_quality_flags_low_bitrate_lossy(self):
        with patch("musiclib.analyze.get_audio_info", return_value={
            "ext": ".mp3",
            "sample_rate": 44100,
            "bits_per_sample": None,
            "bitrate": 128,
            "duration": 180,
            "codec": None,
            "codec_description": "MP3",
            "parser": "mp3",
        }), patch("musiclib.analyze.analyze_gain", return_value=gain_info()):
            result = analyze_quality("/music/song.mp3", root_dir="/music")

        self.assertTrue(result["resourcing_recommended"])
        self.assertIn("low_bitrate_lossy", result["reasons"])

    def test_analyze_quality_reports_decode_errors(self):
        with patch("musiclib.analyze.get_audio_info", side_effect=RuntimeError("bad file")), \
                patch("musiclib.analyze.analyze_gain", side_effect=RuntimeError("bad file")):
            result = analyze_quality("/music/bad.mp3", root_dir="/music")

        self.assertTrue(result["resourcing_recommended"])
        self.assertEqual(result["error"], "bad file")
        self.assertIn("decode_error", result["reasons"])

    def test_analyze_quality_flags_suspicious_flac_bitrate(self):
        with patch("musiclib.analyze.get_audio_info", return_value={
            "ext": ".flac",
            "sample_rate": 44100,
            "bits_per_sample": 16,
            "bitrate": 500,
            "duration": 180,
            "codec": "flac",
            "codec_description": "FLAC",
            "parser": "flac",
        }), patch("musiclib.analyze.analyze_gain", return_value=gain_info()):
            result = analyze_quality("/music/song.flac", root_dir="/music")

        self.assertTrue(result["resourcing_recommended"])
        self.assertIn("suspicious_lossless_bitrate", result["reasons"])

    def test_analyze_quality_missing_replaygain_does_not_recommend_resourcing(self):
        with patch("musiclib.analyze.get_audio_info", return_value={
            "ext": ".mp3",
            "sample_rate": 44100,
            "bits_per_sample": None,
            "bitrate": 320,
            "duration": 180,
            "codec": None,
            "codec_description": "MP3",
            "parser": "mp3",
        }), patch("musiclib.analyze.analyze_gain", return_value=gain_info(track_gain=None)):
            result = analyze_quality("/music/song.mp3", root_dir="/music")

        self.assertFalse(result["resourcing_recommended"])
        self.assertIn("missing_replaygain", result["reasons"])

    def test_analyze_quality_very_short_track_does_not_recommend_resourcing(self):
        with patch("musiclib.analyze.get_audio_info", return_value={
            "ext": ".mp3",
            "sample_rate": 44100,
            "bits_per_sample": None,
            "bitrate": 320,
            "duration": 20,
            "codec": None,
            "codec_description": "MP3",
            "parser": "mp3",
        }), patch("musiclib.analyze.analyze_gain", return_value=gain_info()):
            result = analyze_quality("/music/song.mp3", root_dir="/music")

        self.assertFalse(result["resourcing_recommended"])
        self.assertIn("very_short_track", result["reasons"])

    def test_audit_quality_scans_audio_files(self):
        with patch("musiclib.analyze.iter_quality_audio_files", return_value=["/music/a.mp3", "/music/b.flac"]), \
                patch("musiclib.analyze.analyze_quality", side_effect=[
                    {"resourcing_recommended": False},
                    {"resourcing_recommended": True},
                ]):
            audit = audit_quality("/music")

        self.assertEqual(audit["track_count"], 2)
        self.assertEqual(audit["flagged_count"], 1)

    def test_writes_quality_audit_reports(self):
        audit = {
            "root_dir": "/music",
            "track_count": 1,
            "flagged_count": 1,
            "tracks": [
                {
                    "relative_path": "Artist/Album/song.mp3",
                    "resourcing_recommended": True,
                    "codec_description": "MP3",
                    "codec": None,
                    "parser": "mp3",
                    "bitrate": 128,
                    "sample_rate": 44100,
                    "reasons": ["low_bitrate_lossy"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            reports = write_quality_audit_reports(audit, tmpdir)

            self.assertTrue(os.path.exists(reports["json"]))
            self.assertTrue(os.path.exists(reports["markdown"]))


def gain_info(track_gain=-7.0, track_peak=0.9):
    return {
        "path": "/music/song.mp3",
        "track_gain": track_gain,
        "album_gain": None,
        "track_peak": track_peak,
        "album_peak": None,
        "too_quiet": False,
        "potential_clipping": track_peak is not None and track_peak >= 1.0,
        "resourcing_recommended": False,
    }


if __name__ == "__main__":
    unittest.main()
