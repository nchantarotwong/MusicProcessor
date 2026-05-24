import os
import tempfile
import unittest
from unittest.mock import patch

from musiclib.metadata_audit import audit_metadata, write_metadata_audit_reports


def track(path, **overrides):
    data = {
        "path": path,
        "relative_path": path,
        "folder": os.path.dirname(path),
        "filename": os.path.basename(path),
        "filename_stem": os.path.splitext(os.path.basename(path))[0],
        "ext": os.path.splitext(path)[1],
        "title": "Song",
        "artist": "Artist",
        "album": "Album",
        "album_artist": "Artist",
        "date": "2000",
        "genre": "Rock",
        "track_number": 1,
        "track_raw": "1",
    }
    data.update(overrides)
    return data


class MetadataAuditTests(unittest.TestCase):
    def test_flags_known_artist_canonical_spelling(self):
        tracks = [
            track(
                "Queens/Songs/01 - Song.mp3",
                artist="queens of the stone age",
                album_artist="Queens Of The Stone Age",
            )
        ]

        with patch("musiclib.metadata_audit.iter_audio_files", return_value=["ignored.mp3"]), \
                patch("musiclib.metadata_audit.read_track_metadata", side_effect=tracks):
            audit = audit_metadata("/music")

        issue_types = {issue["type"] for issue in audit["issues"]}
        self.assertIn("artist_known_name_mismatch", issue_types)
        self.assertIn("album_artist_known_name_mismatch", issue_types)

    def test_flags_duplicate_track_numbers_in_folder(self):
        tracks = [
            track("Artist/Album/01 - A.mp3", title="A", track_number=1),
            track("Artist/Album/01 - B.mp3", title="B", track_number=1),
        ]

        with patch("musiclib.metadata_audit.iter_audio_files", return_value=["a.mp3", "b.mp3"]), \
                patch("musiclib.metadata_audit.read_track_metadata", side_effect=tracks):
            audit = audit_metadata("/music")

        self.assertIn(
            "duplicate_track_numbers_in_folder",
            {issue["type"] for issue in audit["issues"]},
        )

    def test_flags_missing_track_artist_even_when_album_artist_exists(self):
        tracks = [
            track("Artist/Album/01 - Song.mp3", artist="", album_artist="Artist"),
        ]

        with patch("musiclib.metadata_audit.iter_audio_files", return_value=["song.mp3"]), \
                patch("musiclib.metadata_audit.read_track_metadata", side_effect=tracks):
            audit = audit_metadata("/music")

        self.assertIn("missing_artist", {issue["type"] for issue in audit["issues"]})

    def test_writes_json_and_markdown_reports(self):
        audit = {
            "root_dir": "/music",
            "track_count": 1,
            "issue_count": 1,
            "tracks": [],
            "issues": [
                {
                    "type": "missing_title",
                    "severity": "warning",
                    "message": "Track is missing title metadata.",
                    "path": "Artist/Album/01.mp3",
                    "details": {},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            reports = write_metadata_audit_reports(audit, tmpdir)

            self.assertTrue(os.path.exists(reports["json"]))
            self.assertTrue(os.path.exists(reports["markdown"]))

    def test_markdown_report_escapes_table_pipes(self):
        audit = {
            "root_dir": "/music",
            "track_count": 1,
            "issue_count": 1,
            "tracks": [],
            "issues": [
                {
                    "type": "filename_title_mismatch",
                    "severity": "info",
                    "message": "Filename has | in it.",
                    "path": "Artist/Album/A | B.mp3",
                    "details": {},
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            reports = write_metadata_audit_reports(audit, tmpdir)

            with open(reports["markdown"], encoding="utf-8") as f:
                markdown = f.read()

        self.assertIn("A \\| B.mp3", markdown)
        self.assertIn("Filename has \\| in it.", markdown)


if __name__ == "__main__":
    unittest.main()
