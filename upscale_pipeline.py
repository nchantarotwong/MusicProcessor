import os
import sys
import shutil
import json
from musiclib.convert import ensure_dir, get_audio_info, convert_to_flac, copy_metadata_and_artwork
from musiclib.analyze import run_rsgain, analyze_gain
from musiclib.report import generate_reports

FAILED_CONVERSION_DIR = "_failed_conversions"
RESOURCING_FOLDER_NAME = "_flagged_for_resourcing"

def process_library(input_dir, output_dir, convert_to_flac, copy_metadata_and_artwork, run_rsgain, analyze_gain, generate_reports):
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
            output_file = os.path.join(output_dir, os.path.splitext(rel_path)[0] + ".flac")
            output_folder = os.path.dirname(output_file)
            ensure_dir(output_folder)

            try:
                print(f"Converting: {rel_path}")
                convert_to_flac(input_file, output_file, failed_dir=failed_dir)
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
    if len(sys.argv) != 3:
        print("Usage: python upscale_pipeline.py /input/dir /output/dir")
        sys.exit(1)

    process_library(
        sys.argv[1],
        sys.argv[2],
        convert_to_flac,
        copy_metadata_and_artwork,
        run_rsgain,
        analyze_gain,
        generate_reports
    )
