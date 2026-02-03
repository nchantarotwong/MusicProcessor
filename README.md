# 🎧 MusicProcessor

**MusicProcessor** is a powerful CLI tool for intelligently converting, normalizing, tagging, and analyzing your local music library. It upscales lossless sources to high-resolution FLAC, converts lossy sources to high-quality AAC (`.m4a`), preserves metadata and artwork, applies ReplayGain normalization, and generates detailed HTML and Markdown reports while flagging low-quality or problematic files for easy re-sourcing.

---

## ✅ Features

- 🔁 **Hybrid audio pipeline**:
  - Converts **lossless** formats to **24-bit / 96kHz FLAC**
  - Converts **lossy** formats (e.g., MP3) to **256 kbps AAC (.m4a)**
- 🖼️ **Preserve metadata and cover art** from original files
- 📐 Apply **ReplayGain normalization** (tags for FLAC, baked-in for AAC)
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
- [`rsgain`](https://github.com/complexlogic/rsgain) — ReplayGain normalization for FLAC
- Python packages:
  ```bash
  pip install mutagen caffeine
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

- Your original files remain untouched.
- The output folder will contain:
  - `.flac` files for lossless sources
  - `.m4a` files for lossy sources
  - Normalized ReplayGain tags (FLAC only)
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
      track1.m4a       ← converted from MP3
      track2.flac      ← converted and upsampled from FLAC
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
- FLAC output uses 24-bit stored in a 32-bit container (`s32`).
- AAC output is 256 kbps CBR for excellent quality at small file size.
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
