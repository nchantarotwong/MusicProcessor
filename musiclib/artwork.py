"""
Utilities for extracting and stripping embedded artwork from audio files.

Supports MP3 (ID3/APIC), FLAC (METADATA_BLOCK_PICTURE), and M4A (MP4 'covr' atoms).
Used to remove bloated or problematic embedded images and optionally extract album
artwork to standalone JPEGs for consistent folder-level organization.

Functions:
    - strip_embedded_artwork(filepath): Removes all embedded artwork from a file.
    - extract_embedded_artwork(filepath, output_image_path): Saves the first embedded
      image (if any) to a given location as a .jpg.

Intended for use in preprocessing pipelines to reduce file size, avoid ffmpeg issues,
and maintain clean, consistent metadata handling across libraries.
"""
import os
from mutagen import File
from mutagen.id3 import ID3
from mutagen.flac import FLAC


def strip_embedded_artwork(filepath):
    """
    Removes all embedded artwork from the audio file (MP3, FLAC, M4A).
    """
    audio = File(filepath)
    if audio is None:
        return

    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".mp3" and isinstance(audio, ID3):
            audio.delall("APIC")
            audio.save()
        elif ext == ".flac" and isinstance(audio, FLAC):
            audio.clear_pictures()
            audio.save()
        elif ext == ".m4a":
            if "covr" in audio:
                del audio["covr"]
                audio.save()
    except Exception as e:
        print(f"[WARN] Failed to strip artwork from {filepath}: {e}")


def extract_embedded_artwork(filepath, output_image_path):
    """
    Extracts the first embedded image (if any) to output_image_path (JPEG).
    Returns True if extraction succeeded.
    """
    audio = File(filepath)
    if audio is None:
        return False

    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == ".mp3" and isinstance(audio, ID3):
            for tag in audio.getall("APIC"):
                with open(output_image_path, "wb") as f:
                    f.write(tag.data)
                return True
        elif ext == ".flac" and isinstance(audio, FLAC):
            if audio.pictures:
                with open(output_image_path, "wb") as f:
                    f.write(audio.pictures[0].data)
                return True
        elif ext == ".m4a" and "covr" in audio:
            cover_data = audio["covr"][0]
            with open(output_image_path, "wb") as f:
                f.write(bytes(cover_data))
            return True
    except Exception as e:
        print(f"[WARN] Failed to extract artwork from {filepath}: {e}")

    return False
