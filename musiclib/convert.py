import os
import shutil
import subprocess
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp4 import MP4, MP4Cover

from musiclib.analyze import get_audio_info, decide_encoding_strategy

TARGET_FLAC_SAMPLE_RATE = 96000
TARGET_AAC_SAMPLE_RATE = 48000
TARGET_BIT_DEPTH = 24

LOSSLESS_EXTENSIONS = {'.flac', '.alac', '.wav', '.aiff', '.aif'}


def ensure_dir(path):
    """
    Ensures that a directory exists, creating it if necessary.

    Args:
        path (str): The directory path to create.
    """
    if not os.path.exists(path):
        os.makedirs(path)


def verify_nonempty_output(output_path: str):
    """
    Verifies that the output file exists and is not empty.

    Args:
        output_path (str): Path to the output file to check.

    Raises:
        RuntimeError: If the file does not exist or has a size of zero bytes.
    """
    if not os.path.exists(output_path):
        raise RuntimeError(f"[✘] Output file not found: {output_path}")
    if os.path.getsize(output_path) == 0:
        raise RuntimeError(f"[✘] Output file is empty: {output_path}")


def convert_to_aac(
    input_path,
    output_path,
    failed_dir=None,
    track_gain_db=None,
    metadata_extra=None
):
    """
    Converts a lossy audio file to AAC format using ffmpeg.

    Args:
        input_path (str): Source file path.
        output_path (str): Output AAC file path.
        failed_dir (str): Optional directory to copy input to on failure.
        track_gain_db (float): Optional track gain adjustment to apply via ffmpeg filter.
        metadata_extra (dict): Additional metadata tags to embed in the output.
    """
    # Ensure .m4a extension
    if not output_path.endswith(".m4a"):
        output_path = os.path.splitext(output_path)[0] + ".m4a"

    # Build filter chain if gain is specified
    filters = []
    if track_gain_db is not None:
        filters.append(f"volume={track_gain_db}dB")
        try:
            gain_val = float(track_gain_db)
            filters.append(f"volume={gain_val}dB")
        except ValueError:
            print(f"[WARN] Invalid track_gain value: {track_gain_db} — skipping gain filter")

    audio_info = get_audio_info(input_path)
    strategy = decide_encoding_strategy(audio_info)
    bitrate = strategy.get("bitrate", "256k")  # default if not using AAC

    if not audio_info["bitrate"]:
        raise RuntimeError(f"Missing bitrate info: {input_path}")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-map", "0:a", # disable video stream output to avoid failures from album art
        *(["-af", ",".join(filters)] if filters else []),
        "-ar", str(TARGET_AAC_SAMPLE_RATE),
        "-c:a", "aac" if strategy["format"] == "aac" else "flac",
        *(["-b:a", bitrate] if strategy["format"] == "aac" else []),
        "-metadata", f"original_bitrate={audio_info['bitrate']}",
        "-metadata", f"original_sample_rate={audio_info['sample_rate']}",
        "-metadata", f"source_format={audio_info['ext'][1:]}",
        output_path
    ]

    if metadata_extra:
        for key, value in metadata_extra.items():
            cmd.extend(["-metadata", f"{key}={value}"])

    cmd.append(output_path)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[✘] ffmpeg failed on: {input_path}")
        if failed_dir:
            rel_path = os.path.relpath(input_path, start=os.path.commonpath([input_path, failed_dir]))
            fail_path = os.path.join(failed_dir, rel_path)
            os.makedirs(os.path.dirname(fail_path), exist_ok=True)
            shutil.copy2(input_path, fail_path)
        raise RuntimeError(f"[ERROR] Failed to convert to AAC: {input_path}\n{e.stderr.decode()}")

    verify_nonempty_output(output_path)


def convert_to_flac(input_path, output_path, failed_dir=None):
    """
    Converts an audio file to 24-bit / 96kHz FLAC format.

    Args:
        input_path (str): Path to the input audio file.
        output_path (str): Path to the output .flac file.
        failed_dir (str, optional): Directory to store failed input files for manual review.

    Raises:
        RuntimeError: If ffmpeg fails to convert the file.
    """
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", str(TARGET_FLAC_SAMPLE_RATE),
        "-sample_fmt", "s32", "-c:a", "flac",
        output_path
    ]
    try:
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        if failed_dir:
            rel_path = os.path.relpath(input_path, start=os.path.commonpath([input_path, failed_dir]))
            fail_path = os.path.join(failed_dir, rel_path)
            os.makedirs(os.path.dirname(fail_path), exist_ok=True)
            shutil.copy2(input_path, fail_path)
        raise RuntimeError(f"[ERROR] Failed to convert {input_path}:\n{e.stderr.decode()}")

    verify_nonempty_output(output_path)


def copy_metadata_and_artwork(original_path, output_path):
    """
    Copies metadata and embedded artwork from the original file to the output file.

    Args:
        original_path (str): Path to the source audio file.
        output_path (str): Path to the destination audio file (.flac or .m4a).

    Notes:
        - FLAC output uses Vorbis comment fields.
        - AAC (.m4a) uses MP4 tags, with limited support for artwork and basic fields.
    """
    original = File(original_path)
    ext = os.path.splitext(output_path)[1].lower()

    if ext == ".flac":
        flac = FLAC(output_path)
        if original and flac:
            try:
                for key in original.keys():
                    value = original[key]
                    if isinstance(value, list):
                        value = [str(v) for v in value]
                    else:
                        value = [str(value)]

                    key_lower = key.lower()
                    if key_lower in ["tit2", "title"]:
                        flac["title"] = value
                    elif key_lower in ["tpe1", "artist"]:
                        flac["artist"] = value
                    elif key_lower in ["talb", "album"]:
                        flac["album"] = value
                    elif key_lower in ["trck", "tracknumber"]:
                        flac["tracknumber"] = value
                    elif key_lower in ["tyer", "date", "tdrc"]:
                        flac["date"] = value
                    elif key_lower in ["tcon", "genre"]:
                        flac["genre"] = value
            except Exception as e:
                print(f"[WARN] Failed to copy tags to FLAC from {original_path}: {e}")

            if hasattr(original, "pictures") and original.pictures:
                for pic in original.pictures:
                    flac.add_picture(pic)
            flac.save()

    elif ext == ".m4a":
        mp4 = MP4(output_path)
        if original and mp4:
            try:
                title = original.get("TIT2") or original.get("title")
                artist = original.get("TPE1") or original.get("artist")
                album = original.get("TALB") or original.get("album")
                genre = original.get("TCON") or original.get("genre")
                track = original.get("TRCK") or original.get("tracknumber")

                if title: mp4["\xa9nam"] = [str(title[0])]
                if artist: mp4["\xa9ART"] = [str(artist[0])]
                if album: mp4["\xa9alb"] = [str(album[0])]
                if genre: mp4["\xa9gen"] = [str(genre[0])]
                if track: mp4["trkn"] = [(int(str(track[0]).split("/")[0]), 0)]

                if hasattr(original, "pictures") and original.pictures:
                    pic = original.pictures[0]
                    mp4["covr"] = [MP4Cover(pic.data, imageformat=MP4Cover.FORMAT_JPEG)]

            except Exception as e:
                print(f"[WARN] Failed to copy tags to AAC from {original_path}: {e}")
            mp4.save()
