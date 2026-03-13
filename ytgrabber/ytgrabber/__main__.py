#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import requests
from datetime import datetime
from mutagen.mp4 import MP4
import anthropic

def get_help():
    print("""
Downloads YouTube content using yt-dlp with configurable settings.

Defaults to highest-quality audio in M4A format. In default (event) mode, uses
Claude to extract concert/event metadata from the title. Use --simple for generic
content like tutorials or yoga videos — skips Claude and uses the video title directly.

Usage:
  ytgrabber <url> [options]

Options:
  --simple            Generic mode: use video title as track name, artist from channel
  --artist <name>     Override artist name (otherwise uses channel/uploader name)
  --include-video     Download video (default: audio only)
  --quality           Video quality: best (default), 720p, 480p, 360p (only with --include-video)
  --playlist          Download entire playlist
  --yt-dlp-path       Path to yt-dlp binary directory
  --yt-output-dir     Output directory for downloads

Examples:
  ytgrabber URL                                    # DJ set / concert mode
  ytgrabber URL --simple                           # Generic video, artist from channel
  ytgrabber URL --simple --artist "John Doe"       # Override artist name
""")
    sys.exit(0)

def update_ytdlp(yt_dlp_path):
    os.makedirs(yt_dlp_path, exist_ok=True)
    bin_path = os.path.join(yt_dlp_path, "yt-dlp")
    update_check_path = os.path.join(yt_dlp_path, "last_update.txt")

    try:
        last_update = None
        if os.path.exists(update_check_path):
            with open(update_check_path, "r") as f:
                last_update = datetime.fromisoformat(f.read().strip())

        print("Checking GitHub for latest yt-dlp release...")
        headers = {"User-Agent": "Python"}
        r = requests.get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", headers=headers)
        release = r.json()
        release_date = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))

        if last_update and last_update >= release_date:
            print("yt-dlp is already up to date.")
            return

        asset = next((a for a in release["assets"] if a["name"] == "yt-dlp_linux"), None)
        if not asset:
            print("Could not find yt-dlp_linux asset in release")
            return
        url = asset["browser_download_url"]
        print(f"Downloading yt-dlp from {url}...")
        data = requests.get(url, headers=headers).content
        with open(bin_path, "wb") as f:
            f.write(data)
        os.chmod(bin_path, 0o755)
        with open(update_check_path, "w") as f:
            f.write(release_date.isoformat())
        print("yt-dlp has been updated to latest release.")

    except Exception as e:
        print(f"Update failed: {e}")

def get_video_info(binary, url):
    try:
        result = subprocess.run(
            [binary, "--print", "title,upload_date,uploader", url],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True
        )
        lines = result.stdout.decode().strip().splitlines()
        title = lines[0] if len(lines) > 0 else ""
        upload_date = lines[1] if len(lines) > 1 else ""
        uploader = lines[2] if len(lines) > 2 else ""
        if not title or not upload_date:
            raise ValueError("Missing title or upload_date in yt-dlp output")
        return title, upload_date, uploader
    except Exception as e:
        print(f"Error retrieving video info: {e}")
        return None, None, None

def sanitize_title(title):
    """Strip trailing periods and spaces to avoid double-dots in filenames."""
    return title.rstrip(". ")

def format_upload_date(upload_date):
    """Convert YYYYMMDD to YYYY-MM-DD."""
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

def parse_field(text, label):
    """Search for a labeled field anywhere in the response text."""
    for line in text.splitlines():
        if label.lower() in line.lower():
            parts = line.split(":", 1)
            if len(parts) == 2:
                value = parts[1].strip().lstrip("-").strip()
                if value:
                    return value
    return "Unknown"

SYSTEM_PROMPT = """You are a research assistant. Given a YouTube video title and upload date, perform a web search to find the real-world event (concert, performance, or show) the video is from.

Return ONLY the following structured data, one per line, with no extra commentary:
- Date: When the event occurred (YYYY-MM-DD)
- Event: The name of the event or show
- Location: The venue and city
- Artist: Who performed

If you can't find reliable info for a field, use "Unknown"."""

def extract_metadata_from_claude(title, upload_date):
    try:
        with open(os.path.expanduser("~/.anthropic_api_key")) as f:
            api_key = f.read().strip()
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": f'Title: "{title}"\nUploaded to YouTube on: {upload_date}',
            }],
        )
        text_parts = [block.text for block in response.content if block.type == "text"]
        content = "\n".join(text_parts).strip()
        return content if content else None
    except Exception as e:
        print(f"Claude metadata fetch failed: {e}")
        return None

def tag_file(path, artist, title, year):
    try:
        audio = MP4(path)
        audio["©nam"] = [title]
        audio["©ART"] = [artist]
        audio["©day"] = [str(year)]
        audio.save()
        print("Tagged audio file with metadata.")
    except Exception as e:
        print(f"Failed to tag file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Download and tag YouTube audio", add_help=False)
    parser.add_argument("url")
    parser.add_argument("--simple", action="store_true", help="Generic mode: use video title, skip Claude")
    parser.add_argument("--artist", help="Pre-supply artist name")
    parser.add_argument("--include-video", action="store_true")
    parser.add_argument("--quality", choices=["best", "720p", "480p", "360p"], default="best")
    parser.add_argument("--playlist", action="store_true")
    parser.add_argument("--yt-dlp-path")
    parser.add_argument("--yt-output-dir")
    parser.add_argument("-?", "--help", action="store_true")
    args = parser.parse_args()

    if args.help:
        get_help()

    yt_dlp_path = args.yt_dlp_path or os.getenv("YT_DLP_PATH") or os.path.expanduser("~/.local/bin/yt-dlp")
    yt_output_dir = args.yt_output_dir or os.getenv("YT_OUTPUT_DIR") or os.path.expanduser("~/Downloads")
    yt_dlp_bin = os.path.join(yt_dlp_path, "yt-dlp")

    update_ytdlp(yt_dlp_path)

    if not os.path.exists(yt_dlp_bin):
        print(f"yt-dlp not found at {yt_dlp_bin}")
        sys.exit(1)

    title, upload_date, uploader = get_video_info(yt_dlp_bin, args.url)
    if not title or not upload_date:
        sys.exit(1)

    event_date = format_upload_date(upload_date)

    if args.simple:
        # Generic mode: use video title directly, artist from uploader or --artist
        track_title = sanitize_title(title)
        artist_name = args.artist or uploader or input("Enter artist name: ").strip()
        if not args.artist and uploader:
            print(f"Using channel as artist: {uploader}")
        full_title = f"{event_date} {track_title}"
    else:
        # Event mode: use Claude to find concert/event metadata
        metadata = extract_metadata_from_claude(title, upload_date)

        event_title = ""
        event_location = ""
        artist_name = ""

        if metadata:
            print("\nClaude Metadata Response:\n" + metadata)
            event_date = parse_field(metadata, "Date:")
            event_title = parse_field(metadata, "Event:")
            event_location = parse_field(metadata, "Location:")
            artist_name = parse_field(metadata, "Artist:")

            # If all fields are Unknown, treat as parse failure
            if all(v == "Unknown" for v in [event_title, event_location, artist_name]):
                print("Could not extract useful metadata from Claude response.")
                metadata = None

        if not metadata:
            print("Falling back to manual entry:")
            event_date = input("Enter full date (YYYY-MM-DD): ").strip()
            event_title = input("Enter event/show name: ").strip()
            event_location = input("Enter location (City, Venue): ").strip()
            artist_name = args.artist or input("Enter artist name: ").strip()

        # Override artist if --artist was passed
        if args.artist:
            artist_name = args.artist

        full_title = f"{event_date} {event_title} ({event_location})"

    output_template = f"{full_title}.%(ext)s"

    args_list = [
        "--ignore-errors",
        "--sponsorblock-remove", "all",
        "--output", os.path.join(yt_output_dir, output_template)
    ]

    quality_format = {
        "best":  None,
        "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }

    if not args.include_video:
        args_list += ["--extract-audio", "--audio-format", "m4a", "--audio-quality", "0"]
    else:
        args_list += ["--merge-output-format", "mp4"]
        fmt = quality_format[args.quality]
        if fmt:
            args_list += ["--format", fmt]

    if args.playlist:
        args_list.append("--yes-playlist")

    args_list.append(args.url)

    print("Running yt-dlp...")
    try:
        subprocess.run([yt_dlp_bin] + args_list, check=True)
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed: {e}")
        sys.exit(e.returncode)

    ext = "mp4" if args.include_video else "m4a"
    file_path = os.path.join(yt_output_dir, f"{full_title}.{ext}")
    try:
        tag_file(file_path, artist_name, full_title, int(event_date[:4]))
    except Exception as e:
        print(f"Tagging failed: {e}")

if __name__ == "__main__":
    main()
