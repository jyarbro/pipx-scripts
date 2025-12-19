#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import requests
from datetime import datetime
from mutagen.mp4 import MP4
from openai import OpenAI

def get_help():
    print("""
Downloads YouTube content using yt-dlp with configurable settings.

Defaults to highest-quality audio in M4A format, and uses ChatGPT to extract metadata from the title.
If the GPT call fails, it will prompt you for metadata manually.
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

def get_video_title(binary, url):
    try:
        title_result = subprocess.run([binary, "--get-title", url], stdout=subprocess.PIPE, check=True)
        title = title_result.stdout.decode().strip()
        date_result = subprocess.run([binary, "--print", "upload_date", url], stdout=subprocess.PIPE, check=True)
        upload_date = date_result.stdout.decode().strip()
        return title, upload_date
    except Exception as e:
        print(f"Error retrieving video title or upload date: {e}")
        return None, None

def extract_metadata_from_gpt(title, upload_date):
    try:
        with open(os.path.expanduser("~/.openai_api_key")) as f:
            api_key = f.read().strip()
        client = OpenAI(api_key=api_key)

        prompt = f"""
You are a research assistant. Based on the YouTube video title and the known upload date below, perform a web search to determine the most likely real-world event (concert, performance, or show) the video is from.

Title: \"{title}\"
Uploaded to YouTube on: {upload_date}

Return ONLY the following data in this exact structured format:
- Date: When the event occurred (YYYY-MM-DD)
- Event: The name of the event or show (if known)
- Location: The venue and city
- Artist: Who performed

If you can't find reliable info, respond with \"Unknown\" for the field.
"""

        response = client.chat.completions.create(
            model="gpt-4o-search-preview",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        content = response.choices[0].message.content
        return content.strip() if content else None
    except Exception as e:
        print(f"GPT metadata fetch failed: {e}")
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
    parser.add_argument("--include-video", action="store_true")
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

    title, upload_date = get_video_title(yt_dlp_bin, args.url)
    if not title or not upload_date:
        sys.exit(1)

    metadata = extract_metadata_from_gpt(title, upload_date)

    # Initialize variables
    event_date = ""
    event_title = ""
    event_location = ""
    artist_name = ""

    if metadata:
        print("\nGPT Metadata Response:\n" + metadata)
        try:
            lines = metadata.splitlines()
            event_date = lines[0].split(":", 1)[1].strip()
            event_title = lines[1].split(":", 1)[1].strip()
            event_location = lines[2].split(":", 1)[1].strip()
            artist_name = lines[3].split(":", 1)[1].strip()
        except Exception as e:
            print(f"Metadata parse failed: {e}")
            metadata = None

    if not metadata:
        print("Falling back to manual entry:")
        event_date = input("Enter full date (YYYY-MM-DD): ").strip()
        event_title = input("Enter event/show name: ").strip()
        event_location = input("Enter location (City, Venue): ").strip()
        artist_name = input("Enter artist name: ").strip()

    full_title = f"{event_date} {event_title} ({event_location})"
    output_template = f"{full_title}.%(ext)s"

    args_list = [
        "--ignore-errors",
        "--sponsorblock-remove", "all",
        "--output", os.path.join(yt_output_dir, output_template)
    ]

    if not args.include_video:
        args_list += ["--extract-audio", "--audio-format", "m4a", "--audio-quality", "0"]
    else:
        args_list.append("--keep-video")

    if args.playlist:
        args_list.append("--yes-playlist")

    args_list.append(args.url)

    print("Running yt-dlp...")
    try:
        subprocess.run([yt_dlp_bin] + args_list, check=True)
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed: {e}")
        sys.exit(e.returncode)

    file_path = os.path.join(yt_output_dir, f"{full_title}.m4a")
    try:
        tag_file(file_path, artist_name, full_title, int(event_date[:4]))
    except Exception as e:
        print(f"Tagging failed: {e}")

if __name__ == "__main__":
    main()