# 🎧 MusicProcessor

**MusicProcessor** is a CLI tool for intelligently organizing, normalizing, tagging, and analyzing your local music library. It preserves existing lossy files without transcoding, copies existing FLAC files without upsampling, converts other lossless sources to FLAC, preserves metadata and artwork, applies ReplayGain normalization, and generates detailed HTML and Markdown reports while flagging low-quality or problematic files for easy re-sourcing.

---

## ✅ Features

- 🔁 **Preservation-first audio pipeline**:
  - Copies existing **lossy** formats instead of transcoding them
  - Copies existing **FLAC** files without upsampling
  - Converts non-FLAC **lossless** formats to FLAC without changing sample rate or bit depth
- 🖼️ **Preserve metadata and cover art** from original files
- 📐 Apply **ReplayGain tag normalization** without changing audio data
- 🧠 Analyze audio quality and flag:
  - Tracks that are **too quiet**
  - Tracks with **potential clipping**
  - Files worth **re-sourcing** (e.g., poor lossy originals)
- 📁 Preserve original **folder structure**
- 📂 Automatically copies flagged files to `_flagged_for_resourcing/`
- 🧩 Optionally copy broken or corrupt files to `_failed_conversions/`
- 📊 Outputs readable reports:
  - `report.html` (clean, styled)
  - `report.md` (Markdown for GitHub, Obsidian, Notion, etc.)
- 📝 Full conversion log: `conversion_log_with_flags.json`

---

## 🖥️ Requirements

- [Python 3.10+](https://www.python.org/)
- [`ffmpeg`](https://ffmpeg.org/download.html) — audio transcoding
- [`rsgain`](https://github.com/complexlogic/rsgain) — ReplayGain tagging
- Python packages:
  ```bash
  pip install mutagen musicbrainzngs
  ```

### 🛠 Install `ffmpeg` and `rsgain` on macOS:
```bash
brew install ffmpeg rsgain
```

---

## 🚀 Usage

```bash
python process_music.py /path/to/input /path/to/output
```

By default, MusicProcessor uses track ReplayGain tags, which is the best fit
for shuffle playback and making songs land at a similar perceived loudness.

```bash
python process_music.py /path/to/input /path/to/output --gain-profile track
```

For album playback, use album mode. This writes album gain tags in addition to
track gain tags and assumes each album is contained in its own folder.

```bash
python process_music.py /path/to/input /path/to/output --gain-profile album
```

To skip loudness tagging entirely:

```bash
python process_music.py /path/to/input /path/to/output --gain-mode none
```

To run a read-only metadata audit without converting or copying audio:

```bash
python process_music.py /path/to/input /path/to/output --metadata-audit-only
```

This writes:

- `metadata_audit.json`
- `metadata_audit.md`

To write a read-only filename normalization plan:

```bash
python process_music.py /path/to/input /path/to/output --filename-plan-only
```

This proposes filename-only changes like `01 - Track Title.mp3`, reports
blocked actions such as missing title/track metadata or target filename
collisions, and does not rename files.

- Your original files remain untouched.
- The output folder will contain:
  - Original lossy files copied without generation loss
  - Original FLAC files copied without upsampling
  - `.flac` files for converted non-FLAC lossless sources
  - ReplayGain tags, unless disabled with `--gain-mode none`
  - JSON + Markdown + HTML report
  - `_flagged_for_resourcing/` for problematic audio
  - `_failed_conversions/` for files that couldn’t be decoded

---

## 📂 Example Folder Structure

```
/input/
  Artist/
    Album/
      track1.mp3
      track2.flac

/output/
  Artist/
    Album/
      track1.mp3       ← copied from MP3
      track2.flac      ← copied from FLAC
  _flagged_for_resourcing/
    Artist/
      Album/
        track2.flac    ← flagged as too quiet or clipping
  _failed_conversions/
    Artist/
      Album/
        corrupted.mp3  ← unprocessable file copied here
  conversion_log_with_flags.json
  report.md
  report.html
```

---

## 📌 Notes

- ReplayGain is applied using [rsgain](https://github.com/complexlogic/rsgain) based on the EBU R128 loudness standard.
- ReplayGain tags require player support. They do not modify MP3, AAC, or FLAC audio data.
- `--gain-profile track` is intended for shuffled libraries and similar loudness across songs.
- `--gain-profile album` preserves album-relative loudness and depends on album-per-folder organization.
- `--metadata-audit-only` is read-only. It reports metadata problems but does not rename files or modify tags.
- `--filename-plan-only` is read-only. It proposes filename changes but does not apply them.
- Personal canonical artist spellings can be added to `CANONICAL_ARTIST_OVERRIDES` in `musiclib/metadata_audit.py`, for example `Queens of the Stone Age`.
- FLAC conversion preserves source sample rate and bit depth by default.
- Lossy-to-lossy conversion is avoided by default because it reduces quality.
- Metadata copying supports ID3, MP4, FLAC tags and embedded artwork (including cover art).

---

## 💡 Ideas for Future Enhancements

- Export playlist of flagged tracks
- Integrate MusicBrainz for automatic metadata fixing
- GUI version (Tkinter or Electron)
- ZIP export of flagged files for re-sourcing or backup

---

## 🛠️ License

MIT License

---

## ✨ Credits

Built with ❤️ using Python, `ffmpeg`, `mutagen`, and `rsgain`.
