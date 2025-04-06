import os
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

def convert_to_flac(input_path, output_path):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", str(TARGET_SAMPLE_RATE),
        "-sample_fmt", "s32", "-c:a", "flac",
        output_path
    ]
    subprocess.run(cmd, check=True)

def copy_metadata_and_artwork(original_path, flac_path):
    original = File(original_path)
    flac = FLAC(flac_path)
    if original and flac:
        for key in original.keys():
            try:
                flac[key] = original[key]
            except Exception:
                pass
        pictures = getattr(original, "pictures", [])
        if pictures:
            for pic in pictures:
                flac.add_picture(pic)
        flac.save()
