# 🎧 MusicProcessor

**MusicProcessor** is a powerful CLI tool for intelligently converting, normalizing, tagging, and analyzing your local music library. It upscales your audio collection to high-resolution FLAC, preserves metadata and artwork, applies ReplayGain normalization, and generates detailed HTML and Markdown reports — while flagging low-quality or problematic files for easy re-sourcing.

---

## ✅ Features

- 🔊 Convert any audio format to **24-bit / 96kHz FLAC**
- 🖼️ **Preserve metadata and cover art** from original files
- 📐 Apply **ReplayGain normalization** (album and track gain/peak)
- 🧠 Analyze audio quality and flag:
  - Tracks that are **too quiet**
  - Tracks with **potential clipping**
  - Files worth **re-sourcing** (e.g., poor lossy originals)
- 📁 Preserve original **folder structure**
- 📂 Automatically copies flagged files to `_flagged_for_resourcing/`
- 📊 Outputs readable reports:
  - `report.html` (clean, styled)
  - `report.md` (Markdown for GitHub, Obsidian, Notion, etc.)
- 📝 Full conversion log: `conversion_log_with_flags.json`

---

## 🖥️ Requirements

- [Python 3.10+](https://www.python.org/)
- [`ffmpeg`](https://ffmpeg.org/download.html)
- [`r128gain`](https://github.com/kteru/r128gain)
- Python libraries:
  ```bash
  pip install mutagen
  ```

---

## 🚀 Usage

```bash
python upscale_pipeline.py /path/to/input /path/to/output
```

- Your original files remain untouched.
- The output folder will contain:
  - Upsampled FLACs
  - Normalized ReplayGain tags
  - JSON + Markdown + HTML report
  - `_flagged_for_resourcing/` for questionable-quality files

---

## 📂 Example Folder Structure

```
/input/
  Artist/
    Album/
      track1.mp3

/output/
  Artist/
    Album/
      track1.flac
  _flagged_for_resourcing/
    Artist/
      Album/
        track1.flac
  conversion_log_with_flags.json
  report.md
  report.html
```

---

## 📌 Notes

- ReplayGain is based on [EBU R128](https://tech.ebu.ch/publications/r128) standard.
- FLAC output uses 24-bit stored in a 32-bit container (`s32`).
- Metadata copying supports ID3, MP4, FLAC tags and embedded artwork.

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

Built with ❤️ using Python, ffmpeg, mutagen, and r128gain.
