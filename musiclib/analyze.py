import subprocess
from mutagen import File

def run_rsgain(directory):
    subprocess.run(['rsgain', 'apply', '--smart', '--recursive', directory], check=True)


def analyze_gain(filepath):
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
