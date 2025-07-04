# ytgrabber

Command-line tool to download and tag YouTube audio using `yt-dlp` and OpenAI's GPT-4o.

## Usage

```bash
ytgrabber "https://www.youtube.com/watch?v=abc123"
ytgrabber "https://www.youtube.com/watch?v=abc123" --include-video
ytgrabber "https://www.youtube.com/playlist?list=xyz" --playlist
```

## Features

* Automatically downloads latest version of `yt-dlp`
* Extracts highest-quality audio in `.m4a` format
* Uses GPT-4o for intelligent metadata tagging
* Tags files with event name, date, artist, and location

## Requirements

* `ffmpeg` installed on your system
* OpenAI API key stored in `~/.openai_api_key`
* Python packages: `yt-dlp`, `mutagen`, `requests`, `openai`

## Configuration

Create a file in your home directory with your OpenAI API key:

```bash
echo "sk-..." > ~/.openai_api_key
chmod 600 ~/.openai_api_key
```