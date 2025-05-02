import argparse
import os
import shutil
import json

from concurrent.futures import ProcessPoolExecutor, as_completed

import caffeine

from musiclib.convert import (
    ensure_dir,
    convert_to_flac,
    convert_to_aac,
    copy_metadata_and_artwork,
)
from musiclib.analyze import (
    analyze_gain,
    choose_aac_bitrate,
    decide_encoding_strategy,
    get_audio_info,
    looks_lossless,
    run_rsgain
)
from musiclib.report import generate_reports

FAILED_CONVERSION_DIR = "_failed_conversions"
RESOURCING_FOLDER_NAME = "_flagged_for_resourcing"


def process_one_file(input_path, output_path):
    try:
        audio_info = get_audio_info(input_path)
        strategy = decide_encoding_strategy(audio_info)
        bitrate = choose_aac_bitrate(audio_info)
        print(f"Converting: {input_path} → {output_path} [{strategy['format']} {bitrate}]")

        if strategy["format"] == "flac":
            convert_to_flac(input_path, output_path, failed_dir=FAILED_CONVERSION_DIR)
        else:
            gain = None
            try:
                gain_analysis = analyze_gain(input_path)
                gain = gain_analysis.get("track_gain")
            except Exception:
                pass  # Gain analysis optional for AAC

            convert_to_aac(
                input_path,
                output_path,
                bitrate=bitrate,
                failed_dir=FAILED_CONVERSION_DIR,
                track_gain_db=gain,
                metadata_extra={
                    "original_bitrate": str(audio_info["bitrate"]),
                    "original_sample_rate": str(audio_info["sample_rate"]),
                    "source_format": audio_info["ext"][1:],
                },
            )

        copy_metadata_and_artwork(input_path, output_path)
        return output_path
    except Exception as e:
        return f"[✘] {input_path} failed: {str(e)}"


def process_all_files(file_pairs, max_workers=None):
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_one_file, in_path, out_path)
            for in_path, out_path in file_pairs
        ]

        for future in as_completed(futures):
            result = future.result()
            if isinstance(result, str) and result.startswith("[✘]"):
                print(result)
            else:
                print(f"[✔] Processed: {result}")


def should_process(output_file, overwrite=False):
    return overwrite or not os.path.exists(output_file)


def process_library(input_dir, output_dir, overwrite=False, max_workers=None):
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

    file_jobs = []

    for root, _, files in os.walk(input_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in ['.mp3', '.flac', '.m4a', '.alac', '.mp4']:
                continue

            input_file = os.path.join(root, file)
            rel_path = os.path.relpath(input_file, input_dir)
            output_base = os.path.splitext(os.path.join(output_dir, rel_path))[0]
            output_file = output_base + ".flac" if looks_lossless(input_file) else output_base + ".m4a"

            output_folder = os.path.dirname(output_file)
            ensure_dir(output_folder)

            if not should_process(output_file, overwrite):
                print(f"[✔] Skipping {output_file} (already exists)")
                continue

            file_jobs.append((input_file, output_file))

    if file_jobs:
        process_all_files(file_jobs, max_workers=max_workers)
    else:
        print("[ℹ] No files to process.")

    print("\nRunning ReplayGain normalization...")
    try:
        run_rsgain(output_dir)
    except RuntimeError as e:
        print(f"[✘] ReplayGain failed: {e}")
        raise

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
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers to use")

    args = parser.parse_args()

    try:
        print("* Preventing system sleep...")
        caffeine.on(display=True)
        process_library(args.input, args.output, overwrite=args.overwrite, max_workers=args.workers)
    finally:
        print("* Re-enabling system sleep.")
        caffeine.off()
