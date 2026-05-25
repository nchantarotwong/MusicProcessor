import unittest
from contextlib import redirect_stderr
from io import StringIO

from process_music import build_parser


class ProcessMusicCliTests(unittest.TestCase):
    def test_process_subcommand_parses_processing_options(self):
        args = build_parser().parse_args([
            "process",
            "input",
            "output",
            "--overwrite",
            "--workers",
            "2",
            "--gain-mode",
            "none",
        ])

        self.assertEqual(args.command, "process")
        self.assertEqual(args.input, "input")
        self.assertEqual(args.output, "output")
        self.assertTrue(args.overwrite)
        self.assertEqual(args.workers, 2)
        self.assertEqual(args.gain_mode, "none")

    def test_metadata_audit_subcommand_parses_paths(self):
        args = build_parser().parse_args(["metadata-audit", "input", "output"])

        self.assertEqual(args.command, "metadata-audit")
        self.assertEqual(args.input, "input")
        self.assertEqual(args.output, "output")

    def test_quality_audit_subcommand_parses_paths(self):
        args = build_parser().parse_args(["quality-audit", "input", "output"])

        self.assertEqual(args.command, "quality-audit")
        self.assertEqual(args.input, "input")
        self.assertEqual(args.output, "output")

    def test_filename_plan_subcommand_parses_paths(self):
        args = build_parser().parse_args(["filename-plan", "input", "output"])

        self.assertEqual(args.command, "filename-plan")
        self.assertEqual(args.input, "input")
        self.assertEqual(args.output, "output")

    def test_apply_filename_plan_subcommand_parses_plan_and_output(self):
        args = build_parser().parse_args([
            "apply-filename-plan",
            "filename_normalization_plan.json",
            "output",
            "--allow-partial-renames",
        ])

        self.assertEqual(args.command, "apply-filename-plan")
        self.assertEqual(args.plan, "filename_normalization_plan.json")
        self.assertEqual(args.output, "output")
        self.assertTrue(args.allow_partial_renames)

    def test_legacy_no_subcommand_form_is_rejected(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            build_parser().parse_args(["input", "output"])


if __name__ == "__main__":
    unittest.main()
