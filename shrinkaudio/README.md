# shrinkaudio

**shrinkaudio** is a CLI tool for batch downsizing `.mp3` and `.m4a` audio files to fit under a target file size (default: 200MB), using smart VBR/CBR bitrate selection via `ffmpeg`.

---

## 🚀 Usage

```bash
shrinkaudio                # Optimize all .mp3 and .m4a files in the current folder
```

Automatically analyzes each file, skips anything under 200MB, and smartly re-encodes anything larger.

---

## 🎯 Features

* Estimates bitrate needed to fit under 200MB
* Tries high-quality **VBR** first (`q=0` to `q=4`)
* Falls back to **CBR** from 320 kbps down to 192 kbps
* Keeps original file as `OLD.filename`
* Clean output with optional live encode progress

---

## ⚠️ Requirements

* `ffmpeg` must be available in `$PATH`
* Python package `colorama`

---

## 📁 Notes

* Operates in the current directory only
* Skips any file already starting with `OLD.`
* Outputs are written in-place, replacing original only if successful
