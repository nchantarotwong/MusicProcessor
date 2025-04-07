import argparse
import os
import shutil
import json

import caffeine

from musiclib.convert import (
    ensure_dir,
    convert_to_flac,
    convert_to_aac,
    copy_metadata_and_artwork,
    is_lossless,
)
from musiclib.analyze import run_rsgain, analyze_gain
from musiclib.report import generate_reports

FAILED_CONVERSION_DIR = "_failed_conversions"
RESOURCING_FOLDER_NAME = "_flagged_for_resourcing"


def process_library(input_dir, output_dir):
    """
    Processes a music library by converting, normalizing, tagging, analyzing, and reporting.

    This function:
      - Walks the input directory recursively
      - Converts files to FLAC or AAC depending on their format
      - Preserves metadata and folder structure
      - Applies ReplayGain normalization for FLAC files
      - Analyzes audio loudness and clipping risk
      - Flags and copies problematic files
      - Outputs HTML, Markdown, and JSON reports

    Args:
        input_dir (str): Path to the input music folder.
        output_dir (str): Path to write the converted and analyzed output.
    """
    log_data = []
    flagged_dir = os.path.join(output_dir, RESOURCING_FOLDER_NAME)
    failed_dir = os.path.join(output_dir, FAILED_CONVERSION_DIR)
    ensure_dir(flagged_dir)
    ensure_dir(failed_dir)

    for root, _, files in os.walk(input_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in ['.mp3', '.flac', '.m4a', '.alac', '.mp4']:
                continue

            input_file = os.path.join(root, file)
            rel_path = os.path.relpath(input_file, input_dir)
            output_base = os.path.splitext(os.path.join(output_dir, rel_path))[0]
            if is_lossless(input_file):
                output_file = output_base + ".flac"
            else:
                output_file = output_base + ".m4a"

            output_folder = os.path.dirname(output_file)
            ensure_dir(output_folder)

            try:
                print(f"Converting: {rel_path}")
                if is_lossless(input_file):
                    convert_to_flac(input_file, output_file, failed_dir=FAILED_CONVERSION_DIR)
                else:
                    convert_to_aac(input_file, output_file)
                    analysis = analyze_gain(input_file)
                    gain = analysis.get("track_gain")
                    convert_to_aac(input_file, output_file, failed_dir=FAILED_CONVERSION_DIR, track_gain_db=gain)

                copy_metadata_and_artwork(input_file, output_file)
            except Exception as e:
                print(f"[ERROR] Skipping file due to conversion error: {input_file}\n{e}")
                continue

    print("\nRunning ReplayGain normalization...")
    run_rsgain(output_dir)

    print("Analyzing and flagging...")
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.endswith(".flac"):
                full_path = os.path.join(root, file)
                analysis = analyze_gain(full_path)
                log_data.append(analysis)

                if analysis["resourcing_recommended"]:
                    flagged_path = os.path.join(flagged_dir, os.path.relpath(full_path, output_dir))
                    ensure_dir(os.path.dirname(flagged_path))
                    shutil.copy2(full_path, flagged_path)

    log_path = os.path.join(output_dir, "conversion_log_with_flags.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2)

    generate_reports(log_path, output_dir)

    print(f"\nAll processing complete. Log saved to: {log_path}")
    print(f"Flagged files (if any) copied to: {flagged_dir}")
    print(f"Files that failed to convert copied to: {failed_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MusicProcessor: Normalize and convert a music library.")
    parser.add_argument("input", help="Path to input directory")
    parser.add_argument("output", help="Path to output directory")

    # Future expansion (e.g.):
    # parser.add_argument("--normalize-all", action="store_true", help="Apply gain to all formats, not just FLAC")
    # parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")

    args = parser.parse_args()

    try:
        print("☕ Preventing system sleep...")
        caffeine.on(display=True)

        process_library(args.input, args.output,)
    finally:
        print("💤 Re-enabling system sleep.")
        caffeine.off()
