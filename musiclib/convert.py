import os
import shutil
import subprocess
from mutagen import File
from mutagen.flac import FLAC

TARGET_SAMPLE_RATE = 96000
TARGET_BIT_DEPTH = 24

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def get_audio_info(filepath):
    audio = File(filepath)
    ext = os.path.splitext(filepath)[1].lower()
    sample_rate = getattr(audio.info, 'sample_rate', 44100)
    bits_per_sample = getattr(audio.info, 'bits_per_sample', 16)
    return ext, sample_rate, bits_per_sample

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

def copy_metadata_and_artwork(original_path, flac_path):
    original = File(original_path)
    flac = FLAC(flac_path)
    if original and flac:
        try:
            for key in original.keys():
                value = original[key]
                # Mutagen ID3 frames (like TIT2) return a list of text frames
                if isinstance(value, list):
                    value = [str(v) for v in value]
                else:
                    value = [str(value)]

                # Convert common ID3 keys to FLAC/Vorbis-style
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
                # You can add more mappings here as needed

        except Exception as e:
            print(f"[WARN] Failed to copy tags from {original_path}: {e}")

        # Copy artwork if supported
        if hasattr(original, "pictures") and original.pictures:
            for pic in original.pictures:
                flac.add_picture(pic)

        flac.save()
