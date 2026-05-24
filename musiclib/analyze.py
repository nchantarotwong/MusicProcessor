import os
import subprocess
from mutagen import File


def run_rsgain(directory, gain_profile="track", threads=4):
    """
    Applies ReplayGain normalization to audio files in a directory using rsgain.

    Runs `rsgain easy` on the specified directory. This calculates and applies
    ReplayGain tags based on EBU R128 loudness normalization without changing
    the audio stream.

    Args:
        directory (str): Path to the root directory containing audio files.
        gain_profile (str): "track" skips album tags for shuffle-oriented
            libraries. "album" writes both track and album tags and assumes
            each album is contained in its own folder.
        threads (int): Number of rsgain scan threads.

    Raises:
        FileNotFoundError: If the `rsgain` executable is not found in the system PATH.
        RuntimeError: If `rsgain` fails during execution.
    """
    cmd = ['rsgain', 'easy', '--skip-existing', f'--multithread={threads}']
    if gain_profile == "track":
        cmd.extend(['-p', 'no_album'])
    elif gain_profile != "album":
        raise ValueError(f"Unknown gain profile: {gain_profile}")
    cmd.append(directory)

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Error: 'rsgain' not found. Please install it and ensure it's in your PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"rsgain failed with exit code {e.returncode}: {e.stderr}") from e


def _decode_tag_value(value):
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip("\x00")
    return str(value).strip()


def _get_tag_value(audio, tag_name):
    tag_name_lower = tag_name.lower()
    mp4_freeform_suffix = f":{tag_name_lower}"

    for key in audio.keys():
        key_lower = key.lower()
        if key_lower == tag_name_lower or key_lower.endswith(mp4_freeform_suffix):
            return _decode_tag_value(audio.get(key))

    return None


def _parse_db(value):
    if value is None:
        return None
    try:
        return float(str(value).replace(" dB", "").replace("db", "").strip())
    except ValueError:
        return None


def _parse_float(value):
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


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
        tg_val = _parse_db(_get_tag_value(audio, 'replaygain_track_gain'))
        ag_val = _parse_db(_get_tag_value(audio, 'replaygain_album_gain'))
        tp_val = _parse_float(_get_tag_value(audio, 'replaygain_track_peak'))
        ap_val = _parse_float(_get_tag_value(audio, 'replaygain_album_peak'))
        result.update({
            "track_gain": tg_val,
            "album_gain": ag_val,
            "track_peak": tp_val,
            "album_peak": ap_val,
            "too_quiet": tg_val is not None and tg_val > 10.0,
            "potential_clipping": tp_val is not None and tp_val >= 1.0
        })
        result["resourcing_recommended"] = result["too_quiet"] or result["potential_clipping"]
    return result


def choose_aac_bitrate(audio_info):
    bitrate = audio_info.get("bitrate")
    if bitrate is None:
        return "256k"  # fallback

    kbps = bitrate
    if kbps < 128:
        return "128k"
    elif kbps < 192:
        return "160k"
    elif kbps < 256:
        return "192k"
    else:
        return "256k"


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
            - codec (str or None): Codec identifier when available
            - codec_description (str or None): Human-readable codec description
            - parser (str or None): Mutagen parser class name
    """
    ext = os.path.splitext(filepath)[1].lower()
    audio = File(filepath)
    if audio is None:
        return {
            "ext": ext,
            "sample_rate": None,
            "bits_per_sample": None,
            "bitrate": None,
            "duration": None,
            "codec": None,
            "codec_description": None,
            "parser": None,
        }

    sample_rate = getattr(audio.info, 'sample_rate', 44100)
    bits_per_sample = getattr(audio.info, 'bits_per_sample', None)
    bitrate = getattr(audio.info, 'bitrate', None)
    duration = getattr(audio.info, 'length', None)
    codec = getattr(audio.info, 'codec', None)
    codec_description = getattr(audio.info, 'codec_description', None)
    parser = type(audio).__name__.lower()

    if bitrate:
        bitrate = bitrate // 1000  # convert to kbps

    return {
        "ext": ext,
        "sample_rate": sample_rate,
        "bits_per_sample": bits_per_sample,
        "bitrate": bitrate,
        "duration": duration,
        "codec": str(codec).lower() if codec else None,
        "codec_description": str(codec_description) if codec_description else None,
        "parser": parser,
    }


def _is_lossless_codec(audio_info):
    codec = (audio_info.get("codec") or "").lower()
    parser = (audio_info.get("parser") or "").lower()

    if codec in {"alac", "flac"}:
        return True

    return parser in {"flac", "wave", "aiff", "aifc"}


def decide_encoding_strategy(audio_info):
    """
    Determines whether an audio file should be copied, re-encoded, or skipped.

    This strategy avoids re-encoding lossy formats and only converts truly lossless
    sources to FLAC. Files with missing or suspicious metadata are skipped.

    Args:
        audio_info (dict): Dictionary from `get_audio_info()` containing keys:
            - ext (str): File extension (e.g., ".mp3", ".flac")
            - sample_rate (int): Sample rate in Hz
            - duration (float or None): Duration in seconds

    Returns:
        dict: Encoding strategy:
            - {"format": "copy"} → Retain original file
            - {"format": "flac"} → Convert non-FLAC lossless sources to FLAC
            - {"format": "skip"} → Skip due to invalid or unsupported file
    """
    ext = audio_info.get("ext")
    sample_rate = audio_info.get("sample_rate")
    duration = audio_info.get("duration")
    codec = (audio_info.get("codec") or "").lower()

    if not ext or not sample_rate or not duration or duration < 5:
        return {"format": "skip"}  # likely corrupt or non-audio

    if ext == ".flac" or codec == "flac":
        return {
            "format": "copy",
            "extension": ".flac",
            "reason": "FLAC source copied without upsampling",
        }

    if _is_lossless_codec(audio_info) or ext in [".alac", ".wav", ".aiff", ".aif"]:
        return {
            "format": "flac",
            "extension": ".flac",
            "reason": "lossless source converted to FLAC without upsampling",
        }

    if ext in [".mp3", ".aac", ".m4a", ".mp4", ".ogg", ".wma"]:
        return {
            "format": "copy",
            "extension": ext,
            "reason": "lossy source copied to avoid generation loss",
        }

    return {"format": "skip"}  # unknown or unsupported format
