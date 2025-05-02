"""
Provides functionality for metadata lookup and tagging using the MusicBrainz API.

This module includes tools to:
- Guess artist and title from a filename
- Search for matching recordings on MusicBrainz
- Prompt the user to select a match
- Apply selected metadata (title, artist, album) to MP3, M4A, or FLAC files using mutagen

Designed to be used by the `lookup_metadata.py` script for interactive correction
or batch metadata cleanup of an existing music library.
"""
import musicbrainzngs
import os
from mutagen import File
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC

# Setup MusicBrainz API client
musicbrainzngs.set_useragent("MusicProcessor", "2.0", "https://github.com/nchantarotwong/MusicProcessor")


def guess_metadata_from_filename(filepath):
    """Guess artist and title from filename."""
    filename = os.path.splitext(os.path.basename(filepath))[0]
    if " - " in filename:
        artist, title = filename.split(" - ", 1)
        return artist.strip(), title.strip()
    return None, filename.strip()


def search_musicbrainz(artist, title, limit=5):
    """Search MusicBrainz for recordings by artist and title."""
    results = musicbrainzngs.search_recordings(artist=artist, recording=title, limit=limit)
    return results.get("recording-list", [])


def prompt_choice(options):
    """Prompt user to choose from a list of MusicBrainz results."""
    for idx, opt in enumerate(options, 1):
        title = opt.get("title")
        artist = opt["artist-credit"][0]["name"]
        date = opt.get("first-release-date", "")
        print(f"[{idx}] {artist} – {title} ({date})")
    print(f"[{len(options)+1}] Skip / Enter manually")
    choice = input("Select a match: ").strip()
    try:
        num = int(choice)
        if 1 <= num <= len(options):
            return options[num - 1]
    except Exception:
        pass
    return None


def apply_metadata(filepath, data):
    """Write metadata tags to audio file using mutagen."""
    ext = os.path.splitext(filepath)[1].lower()
    audio = File(filepath, easy=True)

    if isinstance(audio, EasyID3) or ext == ".mp3":
        audio["title"] = data.get("title", "")
        audio["artist"] = data["artist-credit"][0]["name"]
        audio["album"] = data.get("releases", [{}])[0].get("title", "")
        audio.save()
    elif ext == ".m4a":
        audio = MP4(filepath)
        audio["\xa9nam"] = [data.get("title", "")]
        audio["\xa9ART"] = [data["artist-credit"][0]["name"]]
        audio["\xa9alb"] = [data.get("releases", [{}])[0].get("title", "")]
        audio.save()
    elif ext == ".flac":
        audio = FLAC(filepath)
        audio["title"] = data.get("title", "")
        audio["artist"] = data["artist-credit"][0]["name"]
        audio["album"] = data.get("releases", [{}])[0].get("title", "")
        audio.save()
    else:
        print(f"[WARN] Unsupported format: {filepath}")
