import os
import json
import tempfile
import unittest
from unittest.mock import patch

from musiclib.metadata_audit import (
    audit_metadata,
    apply_filename_normalization_plan,
    build_filename_normalization_plan,
    write_filename_apply_results,
    write_filename_plan_reports,
    write_metadata_audit_reports,
)


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


def write_plan(root_dir, actions):
    plan = {
        "root_dir": root_dir,
        "track_count": len(actions),
        "rename_count": sum(1 for action in actions if action["status"] == "rename"),
        "blocked_count": sum(1 for action in actions if action["status"] == "blocked"),
        "actions": actions,
    }
    plan_path = os.path.join(root_dir, "filename_normalization_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    return plan_path


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

    def test_build_filename_plan_proposes_track_title_filename(self):
        audit = {
            "root_dir": "/music",
            "track_count": 1,
            "tracks": [
                track(
                    "Artist/Album/song.mp3",
                    title="Go With the Flow",
                    track_number=3,
                )
            ],
            "issues": [],
        }

        plan = build_filename_normalization_plan(audit)

        self.assertEqual(plan["rename_count"], 1)
        self.assertEqual(
            plan["actions"][0]["proposed_path"],
            "Artist/Album/03 - Go With the Flow.mp3",
        )

    def test_build_filename_plan_sanitizes_invalid_filename_characters(self):
        audit = {
            "root_dir": "/music",
            "track_count": 1,
            "tracks": [
                track(
                    "Artist/Album/song.mp3",
                    title='A/B: "C"?',
                    track_number=1,
                )
            ],
            "issues": [],
        }

        plan = build_filename_normalization_plan(audit)

        self.assertEqual(
            plan["actions"][0]["proposed_path"],
            "Artist/Album/01 - A_B_ _C__.mp3",
        )

    def test_build_filename_plan_blocks_target_collisions(self):
        audit = {
            "root_dir": "/music",
            "track_count": 2,
            "tracks": [
                track("Artist/Album/a.mp3", title="Song", track_number=1),
                track("Artist/Album/b.mp3", title="Song", track_number=1),
            ],
            "issues": [],
        }

        plan = build_filename_normalization_plan(audit)

        self.assertEqual(plan["blocked_count"], 2)
        self.assertEqual(
            {action["reason"] for action in plan["actions"]},
            {"target filename collision"},
        )

    def test_writes_filename_plan_reports(self):
        plan = {
            "root_dir": "/music",
            "track_count": 1,
            "rename_count": 1,
            "blocked_count": 0,
            "actions": [
                {
                    "status": "rename",
                    "reason": None,
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/01 - Song.mp3",
                    "current_filename": "song.mp3",
                    "proposed_filename": "01 - Song.mp3",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            reports = write_filename_plan_reports(plan, tmpdir)

            self.assertTrue(os.path.exists(reports["json"]))
            self.assertTrue(os.path.exists(reports["markdown"]))

    def test_apply_filename_plan_renames_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            album_dir = os.path.join(tmpdir, "Artist", "Album")
            os.makedirs(album_dir)
            source = os.path.join(album_dir, "song.mp3")
            target = os.path.join(album_dir, "01 - Song.mp3")
            open(source, "w", encoding="utf-8").close()
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/01 - Song.mp3",
                }
            ])

            result = apply_filename_normalization_plan(plan_path)

            self.assertEqual(result["renamed_count"], 1)
            self.assertFalse(os.path.exists(source))
            self.assertTrue(os.path.exists(target))

    def test_apply_filename_plan_refuses_blocked_plan_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            album_dir = os.path.join(tmpdir, "Artist", "Album")
            os.makedirs(album_dir)
            source = os.path.join(album_dir, "song.mp3")
            open(source, "w", encoding="utf-8").close()
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/01 - Song.mp3",
                },
                {
                    "status": "blocked",
                    "path": "Artist/Album/other.mp3",
                    "proposed_path": None,
                },
            ])

            result = apply_filename_normalization_plan(plan_path)

            self.assertEqual(result["renamed_count"], 0)
            self.assertEqual(result["skipped_count"], 2)
            self.assertTrue(os.path.exists(source))

    def test_apply_filename_plan_allows_partial_renames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            album_dir = os.path.join(tmpdir, "Artist", "Album")
            os.makedirs(album_dir)
            source = os.path.join(album_dir, "song.mp3")
            target = os.path.join(album_dir, "01 - Song.mp3")
            open(source, "w", encoding="utf-8").close()
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/01 - Song.mp3",
                },
                {
                    "status": "blocked",
                    "path": "Artist/Album/other.mp3",
                    "proposed_path": None,
                },
            ])

            result = apply_filename_normalization_plan(plan_path, allow_partial=True)

            self.assertEqual(result["renamed_count"], 1)
            self.assertEqual(result["skipped_count"], 1)
            self.assertFalse(os.path.exists(source))
            self.assertTrue(os.path.exists(target))

    def test_apply_filename_plan_blocks_existing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            album_dir = os.path.join(tmpdir, "Artist", "Album")
            os.makedirs(album_dir)
            source = os.path.join(album_dir, "song.mp3")
            target = os.path.join(album_dir, "01 - Song.mp3")
            open(source, "w", encoding="utf-8").close()
            open(target, "w", encoding="utf-8").close()
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/01 - Song.mp3",
                }
            ])

            result = apply_filename_normalization_plan(plan_path)

            self.assertEqual(result["blocked_count"], 1)
            self.assertEqual(result["results"][0]["reason"], "target file already exists")
            self.assertTrue(os.path.exists(source))

    def test_apply_filename_plan_allows_case_only_renames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            album_dir = os.path.join(tmpdir, "Artist", "Album")
            os.makedirs(album_dir)
            source = os.path.join(album_dir, "song.mp3")
            open(source, "w", encoding="utf-8").close()
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "Artist/Album/song.mp3",
                    "proposed_path": "Artist/Album/Song.mp3",
                }
            ])

            with patch("musiclib.metadata_audit._is_same_file", return_value=True), \
                    patch("musiclib.metadata_audit._rename_file") as rename_file:
                result = apply_filename_normalization_plan(plan_path)

            self.assertEqual(result["renamed_count"], 1)
            rename_file.assert_called_once()

    def test_apply_filename_plan_rejects_paths_outside_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = write_plan(tmpdir, [
                {
                    "status": "rename",
                    "path": "../song.mp3",
                    "proposed_path": "01 - Song.mp3",
                }
            ])

            with self.assertRaises(ValueError):
                apply_filename_normalization_plan(plan_path)

    def test_writes_filename_apply_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = {
                "root_dir": "/music",
                "renamed_count": 1,
                "blocked_count": 0,
                "skipped_count": 0,
                "results": [],
            }

            result_path = write_filename_apply_results(result, tmpdir)

            self.assertTrue(os.path.exists(result_path))


if __name__ == "__main__":
    unittest.main()
