# shrinkaudio

CLI tool for batch downsizing `.mp3` and `.m4a` audio files to fit under a target file size using smart bitrate selection.

## Installation

Install via pipx:
```bash
pipx install /path/to/shrinkaudio
```

## Usage

```bash
shrinkaudio
```

## Features

* Estimates bitrate needed to fit under 200MB
* Uses high-quality VBR when possible, falls back to CBR
* Preserves original files with `OLD.` prefix
* Provides clean output with optional encoding progress

## Requirements

* `ffmpeg` available in system path
* Python package `colorama`

## Notes

* Operates in the current directory only
* Skips any file already starting with `OLD.`
* Outputs are written in-place, replacing original only if successful
