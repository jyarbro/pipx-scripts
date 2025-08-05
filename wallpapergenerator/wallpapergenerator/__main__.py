#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import json
from datetime import datetime, date
from openai import OpenAI
import pytz


CONFIG_DIR = os.path.expanduser("~/.config/wallpapergenerator")
DAILY_PROMPT_FILE = os.path.join(CONFIG_DIR, "daily_prompt.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
LOCATION_FILE = os.path.join(CONFIG_DIR, "location.json")


def get_help():
    print("""
WallpaperGenerator - Generate AI wallpapers using OpenAI's GPT-image-1

This tool generates custom wallpapers (always 1920x1080, 16:9) for your Cinnamon desktop.
The image will be stretched to fit ultrawide monitors (e.g., 2560x1080).

Usage:
  wallpapergenerator "a serene mountain landscape at sunset"
  wallpapergenerator --iterate <image-id> "make it more vibrant with golden colors"
  wallpapergenerator --save-only "cyberpunk city at night"

Options:
  --iterate     Iterate on a previous image using its ID
  --save-only   Save image without setting as wallpaper
  --output-dir  Directory to save images (default: ~/Pictures/Wallpapers)
  --list-ids    List previous generation IDs
  --help        Show this help message

API Key:
  Place your OpenAI API key in ~/.openai_api_key

Response Models:
  This tool uses response models to track generated images by ID, allowing
  you to iterate and refine previous generations with feedback.
""")
    sys.exit(0)


def load_api_key():
    """Load OpenAI API key from file"""
    key_file = os.path.expanduser("~/.openai_api_key")
    if not os.path.exists(key_file):
        print("❌ OpenAI API key not found!")
        print("Please save your API key to ~/.openai_api_key")
        print("You can get an API key from: https://platform.openai.com/api-keys")
        sys.exit(1)
    
    try:
        with open(key_file, 'r') as f:
            return f.read().strip()
    except Exception as e:
        print(f"❌ Error reading API key: {e}")
        sys.exit(1)


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_location():
    ensure_config_dir()
    if not os.path.exists(LOCATION_FILE):
        print("❌ Location config not found!")
        print("Please create ~/.config/wallpapergenerator/location.json with e.g. {\"location\": \"Your City, Country\"}")
        sys.exit(1)
    try:
        with open(LOCATION_FILE, "r") as f:
            data = json.load(f)
            location = data.get("location")
            if not location:
                print("❌ Location not set in config file!")
                print("Please set 'location' in ~/.config/wallpapergenerator/location.json")
                sys.exit(1)
            return location
    except Exception:
        print("❌ Error reading location config!")
        sys.exit(1)


def load_generation_history():
    """Load previous generation IDs and metadata"""
    ensure_config_dir()
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading generation history: {e}")
        return {}


def save_generation_history(history):
    """Save generation IDs and metadata"""
    ensure_config_dir()
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving generation history: {e}")


def generate_image(client, prompt, quality="standard", iterate_id=None):
    """Generate image using OpenAI responses API with image_generation tool"""
    try:
        print(f"🎨 Generating image: '{prompt}'")
        print(f"📐 Size: 1920x1080 (16:9), Quality: {quality}")
        
        history = load_generation_history()
        previous_response_id = None
        if iterate_id and iterate_id in history:
            previous_response_id = history[iterate_id].get("response_id")
            print(f"🔄 Iterating on response ID: {previous_response_id}")
        
        # Use gpt-4.1-mini as in your example
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            tools=[{"type": "image_generation"}],
            previous_response_id=previous_response_id if previous_response_id else None
        )
        image_data = [
            output.result
            for output in response.output
            if output.type == "image_generation_call"
        ]
        if not image_data:
            print("❌ No image data returned from OpenAI.")
            sys.exit(1)
        image_base64 = image_data[0]
        generation_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(prompt) % 10000}"
        return {
            "id": generation_id,
            "image_base64": image_base64,
            "response_id": response.id,
            "prompt": prompt,
            "size": "1920x1080",
            "quality": quality,
            "timestamp": datetime.now().isoformat(),
            "iterate_from": iterate_id
        }
    except Exception as e:
        print(f"❌ Error generating image: {e}")
        sys.exit(1)


def save_image_from_base64(b64_data, output_path):
    """Save base64 image data to file"""
    try:
        import base64
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(b64_data))
        print(f"💾 Image saved to: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving image: {e}")
        return False


def set_wallpaper(image_path):
    """Set image as desktop wallpaper (Cinnamon only)"""
    try:
        # Cinnamon desktop uses gsettings for org.cinnamon.desktop.background
        result = subprocess.run([
            "gsettings", "set", "org.cinnamon.desktop.background", 
            "picture-uri", f"file://{image_path}"
        ], capture_output=True)
        
        if result.returncode == 0:
            print("🖼️  Wallpaper set successfully (Cinnamon)")
            return True
        
        print("⚠️  Could not set wallpaper automatically for Cinnamon.")
        print("Please set it manually from the saved file.")
        return False
    except Exception as e:
        print(f"⚠️  Error setting wallpaper: {e}")
        print("You can set it manually from the saved file.")
        return False


def validate_quality(quality):
    """Validate image quality parameter"""
    valid_qualities = ["standard", "hd"]
    if quality not in valid_qualities:
        print(f"❌ Invalid quality '{quality}'. Valid options: {', '.join(valid_qualities)}")
        sys.exit(1)
    return quality


def create_filename(prompt, size, quality, generation_id):
    """Create a safe filename from prompt and parameters"""
    # Clean prompt for filename
    safe_prompt = "".join(c for c in prompt if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_prompt = safe_prompt.replace(' ', '_')[:30]  # Limit length
    # Extract date/time from generation_id
    # generation_id: gen_YYYYMMDD_HHMMSS_xxxx
    try:
        dt_part = generation_id.split('_')[1] + '_' + generation_id.split('_')[2]
        dt_fmt = datetime.strptime(dt_part, "%Y%m%d_%H%M%S")
        date_str = dt_fmt.strftime("%Y-%m-%d_%H-%M-%S")
    except Exception:
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{date_str}_wallpaper_{safe_prompt}_1920x1080.png"


def list_generation_ids():
    """List previous generation IDs with metadata"""
    history = load_generation_history()
    if not history:
        print("📝 No previous generations found.")
        return
    
    print("📜 Previous Generations:")
    print("-" * 80)
    
    for gen_id, data in sorted(history.items(), key=lambda x: x[1].get('timestamp', '')):
        timestamp = data.get('timestamp', 'Unknown')
        prompt = data.get('prompt', 'No prompt')[:50]
        size = data.get('size', 'Unknown')
        quality = data.get('quality', 'Unknown')
        iterate_from = data.get('iterate_from')
        
        print(f"ID: {gen_id}")
        print(f"  Time: {timestamp}")
        print(f"  Prompt: {prompt}{'...' if len(data.get('prompt', '')) > 50 else ''}")
        print(f"  Size: {size}, Quality: {quality}")
        if iterate_from:
            print(f"  Iterated from: {iterate_from}")
        print()


# Helper to get today's date string
def get_today_str():
    return date.today().isoformat()

# Load daily prompt from file
def load_daily_prompt():
    ensure_config_dir()
    if not os.path.exists(DAILY_PROMPT_FILE):
        return None
    try:
        with open(DAILY_PROMPT_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") == get_today_str():
                return data.get("prompt")
    except Exception:
        pass
    return None

# Save daily prompt to file
def save_daily_prompt(prompt):
    ensure_config_dir()
    with open(DAILY_PROMPT_FILE, "w") as f:
        json.dump({"date": get_today_str(), "prompt": prompt}, f)

# Generate a new base prompt for the day using GPT
def get_new_base_prompt(client):
    system_prompt = (
        "Generate a creative, visually interesting wallpaper prompt for an AI image generator. "
        "Do not include any time, weather, or season information."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_prompt}]
    )
    return response.choices[0].message.content.strip()

# Build the full prompt for image generation
def build_full_prompt(base_prompt, client):
    location = load_location()
    tz = pytz.timezone("America/New_York")
    now = datetime.now(tz)
    time_str = now.strftime("%I:%M %p").lstrip("0")
    date_str = now.strftime("%B %d, %Y")
    # Ask GPT for a phrase describing the current season, climate, weather, and time in the user's location
    weather_season_prompt = (
        f"Describe the current season, climate, weather, and time in {location} at {time_str} on {date_str}. Respond with a short phrase suitable for an image prompt."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": weather_season_prompt}]
    )
    location_context = response.choices[0].message.content.strip()
    # Compose final prompt
    return (
        f"{base_prompt} The image can take place anywhere, but it should reflect the current season, climate, weather, and time in your location. Context: {location_context}."
    )

# Find previous image ID for today (threading)
def get_previous_image_id_today():
    history = load_generation_history()
    today = get_today_str()
    # Find latest image for today
    images_today = [
        (gen_id, data) for gen_id, data in history.items()
        if data.get("timestamp", "").startswith(today)
    ]
    if not images_today:
        return None
    # Return most recent
    return sorted(images_today, key=lambda x: x[1]["timestamp"], reverse=True)[0][0]


def is_session_unlocked_and_active():
    try:
        import getpass
        user = getpass.getuser()
        session = None
        # Find session for current user (accept any session ID)
        result = subprocess.run(["loginctl", "list-sessions"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == user:
                session = parts[0]
                break
        if not session:
            print(f"⚠️  No active session found for user '{user}'.")
            return False
        status_result = subprocess.run(["loginctl", "show-session", session, "-p", "LockedHint", "-p", "IdleHint"], capture_output=True, text=True)
        status = status_result.stdout
        return ("LockedHint=no" in status) and ("IdleHint=no" in status)
    except Exception as e:
        print(f"⚠️  Session check error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate AI wallpapers using OpenAI GPT-image-1", add_help=False)
    parser.add_argument("prompt", nargs="?", help="Description of the wallpaper to generate")
    parser.add_argument("--help", action="store_true", help="Show help message")
    parser.add_argument("--iterate", help="Iterate on a previous image using its ID")
    parser.add_argument("--quality", default="standard", help="Image quality (standard, hd)")
    parser.add_argument("--save-only", action="store_true", help="Save image without setting as wallpaper")
    parser.add_argument("--output-dir", default="~/Pictures/Wallpapers", help="Directory to save images")
    parser.add_argument("--list-ids", action="store_true", help="List previous generation IDs")
    parser.add_argument("--test-session", action="store_true", help="Test session lock/idle status and exit")
    parser.add_argument("--reset-base-prompt", action="store_true", help="Reset the base prompt for today and start from scratch")
    args = parser.parse_args()

    if args.test_session:
        if is_session_unlocked_and_active():
            print("Session is unlocked and active.")
        else:
            print("Session is locked or idle.")
        return
    if args.help:
        get_help()
    if args.list_ids:
        list_generation_ids()
        return
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)
    if args.reset_base_prompt:
        print("🔄 Resetting base prompt for today...")
        base_prompt = get_new_base_prompt(client)
        save_daily_prompt(base_prompt)
        print(f"📝 New base prompt: {base_prompt}")
    else:
        base_prompt = load_daily_prompt()
        if not base_prompt:
            print("🌅 Generating new base prompt for today...")
            base_prompt = get_new_base_prompt(client)
            save_daily_prompt(base_prompt)
            print(f"📝 Today's base prompt: {base_prompt}")
        else:
            print(f"📝 Using today's base prompt: {base_prompt}")
    # Build full prompt for this run
    full_prompt = build_full_prompt(base_prompt, client)
    print(f"🔗 Full prompt: {full_prompt}")
    # Find previous image for today (thread)
    iterate_id = get_previous_image_id_today()
    quality = validate_quality(args.quality)
    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    # Generate image
    result = generate_image(client, full_prompt, quality, iterate_id)
    filename = create_filename(full_prompt, "1920x1080", quality, result["id"])
    output_path = os.path.join(output_dir, filename)
    if save_image_from_base64(result["image_base64"], output_path):
        print(f"✅ Image generated successfully!")
        print(f"🆔 Generation ID: {result['id']}")
        history = load_generation_history()
        history[result["id"]] = {
            "prompt": result["prompt"],
            "response_id": result["response_id"],
            "size": "1920x1080",
            "quality": result["quality"],
            "timestamp": result["timestamp"],
            "iterate_from": result["iterate_from"],
            "file_path": output_path
        }
        save_generation_history(history)
        if not args.save_only:
            set_wallpaper(output_path)
        else:
            print(f"📁 Image saved to: {output_path}")
        print(f"💡 Use '--iterate {result['id']}' to refine this image")
    print("🎉 Done!")


if __name__ == "__main__":
    main()