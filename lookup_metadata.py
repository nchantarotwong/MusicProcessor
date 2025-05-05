#!/usr/bin/env python3
import os
import argparse
from musiclib.metadata_lookup import (
    guess_metadata_from_filename,
    search_musicbrainz,
    prompt_choice,
    apply_metadata
)


def lookup_and_update(filepath):
    """Performs metadata lookup and update for a single file."""
    print(f"\n🔍 Processing: {filepath}")
    artist, title = guess_metadata_from_filename(filepath)
    if not title:
        print("[⚠️] Could not guess metadata from filename.")
        return

    print(f"Guess: {artist} – {title}")
    try:
        matches = search_musicbrainz(artist, title)
        if not matches:
            print("[ℹ️] No matches found.")
            return

        selected = prompt_choice(matches)
        if selected:
            apply_metadata(filepath, selected)
            print("[✔] Metadata updated.")
        else:
            print("[→] Skipped.")
    except Exception as e:
        print(f"[ERROR] Lookup failed: {e}")


def walk_and_process(input_dir):
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith((".mp3", ".flac", ".m4a")):
                full_path = os.path.join(root, file)
                lookup_and_update(full_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lookup and update music metadata via MusicBrainz.")
    parser.add_argument("input", help="Path to your processed music folder")
    args = parser.parse_args()

    walk_and_process(args.input)
