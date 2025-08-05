# 🧰 pipx-scripts

A collection of custom Python command-line tools designed to be installed and run using [`pipx`](https://github.com/pypa/pipx). Each script lives in its own isolated environment and serves a focused purpose — from system cleanup to Steam fixes to video downloading.

---

## 📦 Included Tools

| Tool                        | Description                                                                                                                           |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------
| **`ytgrabber`**             | Downloads videos using `yt-dlp` and tags them with GPT-4o metadata. Automatically updates to the latest version.                      |
| **`fixsteamcompatibility`** | Moves all Proton compatibility prefixes to a native filesystem and replaces them with symlinks — solving Steam/Proton symlink issues. |
| **`kernelcleaner`**         | Safely removes old Linux kernel versions to free up disk space.                                                                       |
| **`brightshift`**           | Instantly adjusts monitor brightness using `xrandr`, useful for multi-monitor Linux setups.                                           |
| **`shrinkaudio`**           | Batch-downsizes MP3 and M4A files by slightly lowering their bitrate using `ffmpeg`. Skips files prefixed with `OLD`.                 |
| **`wallpapergenerator`**    | Generates AI wallpapers using OpenAI's GPT-image-1 with iterative refinement and generation history tracking.                         |

Each tool is completely self-contained and can be installed or uninstalled independently.

---

## 🚀 Install All Tools at Once

To install every tool in this repository using `pipx`, run:

```bash
./install.sh
```

This script:

* Iterates over each subdirectory
* Looks for a `pyproject.toml`
* Installs each tool using `pipx install ./toolname --force`

> 🔁 Re-running the script will update/reinstall all tools.

---

## 🧰 Requirements

* Python 3.7 or later
* [`pipx`](https://github.com/pypa/pipx)

Install pipx if you haven't:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

---
