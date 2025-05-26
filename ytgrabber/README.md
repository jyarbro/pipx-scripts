# ytgrabber

A command-line tool to download and tag YouTube audio using `yt-dlp` and OpenAI's GPT-4o.

## Features
- Automatically downloads the latest version of `yt-dlp`
- Defaults to extracting highest-quality audio in `.m4a` format
- Uses GPT-4o to look up metadata like event name, date, artist, and location
- Falls back to manual prompts if metadata cannot be retrieved
- Tags downloaded files using `mutagen`

## Installation
Use `pipx` to install this tool in an isolated environment:

```bash
pipx install ./ytgrabber
```

To force a rebuild with all dependencies:
```bash
pipx uninstall ytgrabber
pipx install ./ytgrabber
```

## Dependencies
These are automatically installed via `pyproject.toml`:
- `yt-dlp`
- `mutagen`
- `requests`
- `openai`

Make sure `ffmpeg` is installed on your system:
```bash
sudo apt install ffmpeg
```

## Configuration
Create a file in your home directory with your OpenAI API key:

```bash
echo "sk-..." > ~/.openai_api_key
chmod 600 ~/.openai_api_key
```

This file is required for GPT-powered metadata tagging to work.

## Usage
Download and tag a YouTube video:
```bash
ytgrabber "https://www.youtube.com/watch?v=abc123"
```

Include video (instead of just audio):
```bash
ytgrabber "https://www.youtube.com/watch?v=abc123" --include-video
```

Download a playlist:
```bash
ytgrabber "https://www.youtube.com/playlist?list=xyz" --playlist
```