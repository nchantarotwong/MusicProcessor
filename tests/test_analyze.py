import unittest
from unittest.mock import patch

from musiclib.analyze import (
    _get_tag_value,
    choose_aac_bitrate,
    decide_encoding_strategy,
    run_rsgain,
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


if __name__ == "__main__":
    unittest.main()
