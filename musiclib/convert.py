import os
import shutil
import subprocess
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp4 import MP4, MP4Cover

TARGET_SAMPLE_RATE = 96000
TARGET_BIT_DEPTH = 24

LOSSLESS_EXTENSIONS = {'.flac', '.alac', '.wav', '.aiff', '.aif'}

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_audio_info(filepath):
    audio = File(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    sample_rate = getattr(audio.info, 'sample_rate', 44100)
    bits_per_sample = getattr(audio.info, 'bits_per_sample', 16)
    return ext, sample_rate, bits_per_sample

def is_lossless(filepath):
    return os.path.splitext(filepath)[1].lower() in LOSSLESS_EXTENSIONS

def convert_to_flac(input_path, output_path, failed_dir=None):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", str(TARGET_SAMPLE_RATE),
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

def convert_to_aac(input_path, output_path, failed_dir=None, track_gain_db=None):
    # Ensure .m4a extension
    if not output_path.endswith(".m4a"):
        output_path = os.path.splitext(output_path)[0] + ".m4a"

    # Build filter chain if gain is specified
    filters = []
    if track_gain_db is not None:
        try:
            gain_val = float(track_gain_db)
            filters.append(f"volume={gain_val}dB")
        except ValueError:
            print(f"[WARN] Invalid track_gain value: {track_gain_db} — skipping gain filter")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        *(["-af", ",".join(filters)] if filters else []),
        "-c:a", "aac", "-b:a", "256k",
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
        raise RuntimeError(f"[ERROR] Failed to convert to AAC: {input_path}\n{e.stderr.decode()}")

def copy_metadata_and_artwork(original_path, output_path):
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
