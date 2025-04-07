import os
import subprocess
from mutagen import File


def run_rsgain(directory):
    """
    Applies ReplayGain normalization to audio files in a directory using rsgain.

    Runs `rsgain apply --smart --recursive` on the specified directory. This calculates
    and applies ReplayGain tags based on EBU R128 loudness normalization.

    Args:
        directory (str): Path to the root directory containing audio files.

    Raises:
        FileNotFoundError: If the `rsgain` executable is not found in the system PATH.
        RuntimeError: If `rsgain` fails during execution.
    """
    try:
        subprocess.run(['rsgain', 'easy', '--skip-existing', '--multithread=4', directory], check=True)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Error: 'rsgain' not found. Please install it and ensure it's in your PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"rsgain failed with exit code {e.returncode}: {e.stderr}") from e


def analyze_gain(filepath):
    """
    Parses ReplayGain tags from an audio file and evaluates its loudness quality.

    This extracts ReplayGain tags (track/album gain and peak), and flags the file
    if it appears too quiet or clipped based on thresholds.

    Args:
        filepath (str): Path to the audio file to analyze.

    Returns:
        dict: A dictionary containing:
            - path (str): Original file path
            - track_gain (float or None): dB gain needed for normalization
            - album_gain (float or None): Not currently used
            - track_peak (float or None): Max peak volume (0.0–1.0 scale)
            - album_peak (float or None): Not currently used
            - too_quiet (bool): True if track gain < -10.0 dB
            - potential_clipping (bool): True if track peak >= 1.0
            - resourcing_recommended (bool): True if file is too quiet or clips
    """
    print(f'Analyzing gain on: ({filepath})...')
    audio = File(filepath)
    result = {
        "path": filepath,
        "track_gain": None,
        "album_gain": None,
        "track_peak": None,
        "album_peak": None,
        "too_quiet": False,
        "potential_clipping": False,
        "resourcing_recommended": False
    }
    if audio:
        tg = audio.get('replaygain_track_gain')
        ag = audio.get('replaygain_album_gain')
        tp = audio.get('replaygain_track_peak')
        ap = audio.get('replaygain_album_peak')
        try:
            tg_val = float(tg[0].replace(' dB', '')) if tg else None
            tp_val = float(tp[0]) if tp else None
            result.update({
                "track_gain": tg_val,
                "track_peak": tp_val,
                "too_quiet": tg_val is not None and tg_val < -10.0,
                "potential_clipping": tp_val is not None and tp_val >= 1.0
            })
            result["resourcing_recommended"] = result["too_quiet"] or result["potential_clipping"]
        except Exception:
            pass
    return result


def get_audio_info(filepath):
    """
    Extracts basic audio info from a file.

    Args:
        filepath (str): Path to the audio file.

    Returns:
        dict: A dictionary containing:
            - ext (str): File extension (lowercase)
            - sample_rate (int): Sample rate in Hz
            - bits_per_sample (int or None): Bit depth if available
            - bitrate (int or None): Bitrate in kbps, if available
            - duration (float or None): Duration in seconds
    """
    ext = os.path.splitext(filepath)[1].lower()
    audio = File(filepath)
    sample_rate = getattr(audio.info, 'sample_rate', 44100)
    bits_per_sample = getattr(audio.info, 'bits_per_sample', None)
    bitrate = getattr(audio.info, 'bitrate', None)
    duration = getattr(audio.info, 'length', None)

    if bitrate:
        bitrate = bitrate // 1000  # convert to kbps

    return {
        "ext": ext,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
        "bitrate": bitrate,
        "duration": duration,
    }


def decide_encoding_strategy(audio_info):
    """
    Decides whether to encode as FLAC or AAC, and at what bitrate.

    Args:
        audio_info (dict): Output of get_audio_info().

    Returns:
        dict: Encoding strategy, e.g.:
              {"format": "aac", "bitrate": "160k"}
              or {"format": "flac"}
    """
    ext = audio_info["ext"]
    bitrate = audio_info["bitrate"]

    if ext in [".mp3", ".m4a"] and bitrate:
        if bitrate < 192:
            return {"format": "aac", "bitrate": "160k"}
        elif bitrate < 256:
            return {"format": "aac", "bitrate": "192k"}
        else:
            return {"format": "aac", "bitrate": "256k"}
    else:
        return {"format": "flac"}


def is_lossless(file_path):
    """
    Determines whether the audio file is truly lossless based on codec.
    Returns True for FLAC, ALAC, WAV, AIFF, etc. False for MP3, AAC, etc.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".flac", ".alac", ".wav", ".aiff", ".ape"]:
        audio = File(file_path)
        if audio is None:
            return False
        codec = type(audio).__name__.lower()
        return codec in ["flac", "alac", "aiff", "wavpack", "dsf"]
    return False
