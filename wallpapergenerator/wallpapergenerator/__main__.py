#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import json
from datetime import datetime, date
from openai import OpenAI
import pytz
import cv2
import numpy as np
from PIL import Image


CONFIG_DIR = os.path.expanduser("~/.config/wallpapergenerator")
DAILY_PROMPT_FILE = os.path.join(CONFIG_DIR, "daily_prompt.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.json")
LOCATION_FILE = os.path.join(CONFIG_DIR, "location.json")
THEME_HISTORY_FILE = os.path.join(CONFIG_DIR, "theme_history.txt")


def get_help():
    print("""
WallpaperGenerator - Generate AI wallpapers using OpenAI's GPT-image-1

This tool generates custom wallpapers with AI upscaling to 4K resolution.
Images are generated at 1792x1024 and automatically upscaled to 3840x2160
using Real-ESRGAN for maximum quality.

Usage:
  wallpapergenerator "a serene mountain landscape at sunset"
  wallpapergenerator --iterate <image-id> "make it more vibrant with golden colors"
  wallpapergenerator --save-only "cyberpunk city at night"
  wallpapergenerator --quality high

Options:
  --iterate        Iterate on a previous image using its ID
  --save-only      Save image without setting as wallpaper
  --quality        Image quality: hd (default), high, standard, medium, low
  --output-dir     Directory to save images (default: ~/Pictures/Wallpapers)
  --skip-upscale   Skip AI upscaling (save original 1792x1024)
  --upscale-size   Target resolution (default: 3840x2160)
  --list-ids       List previous generation IDs
  --help           Show this help message

Upscaling:
  By default, images are upscaled to 3840x2160 (4K) using Real-ESRGAN.
  This process takes 15-30 seconds but produces exceptional quality.
  Use --skip-upscale to save time during testing.
  Use --upscale-size to specify custom resolutions (e.g., 5120x2880).

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


def load_theme_history():
    """Load past themes from history file (one theme per line)"""
    ensure_config_dir()
    if not os.path.exists(THEME_HISTORY_FILE):
        return []
    try:
        with open(THEME_HISTORY_FILE, 'r') as f:
            themes = [line.strip() for line in f if line.strip()]
            return themes
    except Exception as e:
        print(f"⚠️  Error loading theme history: {e}")
        return []


def save_theme_to_history(theme):
    """Append a new theme to the history file"""
    ensure_config_dir()
    try:
        with open(THEME_HISTORY_FILE, 'a') as f:
            f.write(theme + '\n')
    except Exception as e:
        print(f"⚠️  Error saving theme to history: {e}")


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


def generate_image(client, prompt, quality="hd", iterate_id=None):
    """Generate image using OpenAI responses API with image_generation tool"""
    try:
        # Add explicit size and quality instructions to the prompt
        enhanced_prompt = f"{prompt} [Generate as a high-quality 1792x1024 widescreen image with maximum detail and clarity]"

        print(f"🎨 Generating image: '{prompt}'")
        print(f"📐 Target: 1792x1024 (widescreen), Quality: {quality}")

        history = load_generation_history()
        previous_response_id = None
        if iterate_id and iterate_id in history:
            previous_response_id = history[iterate_id].get("response_id")
            print(f"🔄 Iterating on response ID: {previous_response_id}")

        # Use gpt-4.1 (full model, not mini) for better image quality
        response = client.responses.create(
            model="gpt-4.1",
            input=enhanced_prompt,
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
            "size": "1792x1024",
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


def upscale_image_realesrgan(input_path, output_path, target_size=(3840, 2160)):
    """
    Upscale image using Real-ESRGAN to target resolution

    Args:
        input_path: Path to input image
        output_path: Path to save upscaled image
        target_size: Target resolution tuple (width, height), default 3840x2160

    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"🔍 Upscaling image with Real-ESRGAN...")
        print(f"   Input: {input_path}")
        print(f"   Target: {target_size[0]}x{target_size[1]}")

        # Import Real-ESRGAN components
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        # Use RealESRGAN_x4plus model (best quality for general images)
        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)

        # Initialize upscaler
        upsampler = RealESRGANer(
            scale=4,
            model_path='https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth',
            model=model,
            tile=0,  # No tiling for maximum quality (use GPU memory efficiently)
            tile_pad=10,
            pre_pad=0,
            half=False  # Use full precision for best quality
        )

        # Read input image
        img = cv2.imread(input_path, cv2.IMREAD_COLOR)
        if img is None:
            print(f"❌ Failed to read image: {input_path}")
            return False

        # Upscale (this will take 10-15 seconds for quality)
        print("   Processing... (this may take 15-30 seconds)")
        output, _ = upsampler.enhance(img, outscale=4)

        # Resize to exact target dimensions if needed
        current_h, current_w = output.shape[:2]
        target_w, target_h = target_size

        if (current_w, current_h) != (target_w, target_h):
            print(f"   Resizing from {current_w}x{current_h} to {target_w}x{target_h}")
            output = cv2.resize(output, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

        # Save upscaled image
        cv2.imwrite(output_path, output)
        print(f"✨ Upscaled image saved to: {output_path}")

        return True

    except ImportError as e:
        print(f"⚠️  Real-ESRGAN not properly installed: {e}")
        print("   Skipping upscaling. Run: pipx install ./wallpapergenerator --force")
        return False
    except Exception as e:
        print(f"⚠️  Error during upscaling: {e}")
        print("   Original image saved without upscaling")
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
    valid_qualities = ["standard", "hd", "high", "medium", "low"]
    if quality not in valid_qualities:
        print(f"❌ Invalid quality '{quality}'. Valid options: {', '.join(valid_qualities)}")
        sys.exit(1)
    return quality


def create_filename(prompt, size, quality, generation_id, upscaled=False):
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

    if upscaled:
        return f"{date_str}_wallpaper_{safe_prompt}_3840x2160.png"
    else:
        return f"{date_str}_wallpaper_{safe_prompt}_1792x1024.png"


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
        return None, None
    try:
        with open(DAILY_PROMPT_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") == get_today_str():
                return data.get("theme"), data.get("prompt")
    except Exception:
        pass
    return None, None

# Save daily prompt to file
def save_daily_prompt(theme, prompt):
    ensure_config_dir()
    with open(DAILY_PROMPT_FILE, "w") as f:
        json.dump({"date": get_today_str(), "theme": theme, "prompt": prompt}, f)

# Generate a new theme (Stage 1 of 3)
def generate_new_theme(client):
    """Generate a unique theme that doesn't overlap with past themes"""
    past_themes = load_theme_history()

    if past_themes:
        past_themes_text = "\n".join([f"- {theme}" for theme in past_themes[-30:]])  # Last 30 themes for context
        theme_prompt = (
            f"Generate a single, concise theme (2-5 words) for a wallpaper image. "
            f"Be creative and eclectic. Here are recent past themes to AVOID overlapping with:\n\n"
            f"{past_themes_text}\n\n"
            f"Generate a NEW theme that is distinctly different from these past themes. "
            f"Explore different art styles, subjects, moods, and concepts. "
            f"Respond with ONLY the theme, nothing else."
        )
    else:
        theme_prompt = (
            "Generate a single, concise theme (2-5 words) for a wallpaper image. "
            "Be creative and eclectic. Explore different art styles, subjects, moods, and concepts. "
            "Respond with ONLY the theme, nothing else."
        )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": theme_prompt}]
    )
    theme = response.choices[0].message.content.strip()
    # Clean up any quotes or extra formatting
    theme = theme.strip('"\'')
    return theme


# Generate a new base prompt for the day using the theme (Stage 2 of 3)
def get_new_base_prompt(client, theme):
    """Generate a detailed wallpaper prompt based on the given theme"""
    prompt_generation = (
        f"Generate a creative, visually interesting wallpaper prompt for an AI image generator "
        f"based on this theme: '{theme}'. "
        f"Create a detailed description that will result in a stunning wallpaper. "
        f"Do not include any time, weather, or season information - that will be added later. "
        f"Respond with ONLY the prompt description, nothing else."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt_generation}]
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
    parser.add_argument("--quality", default="hd", help="Image quality (standard, hd, high, medium, low)")
    parser.add_argument("--save-only", action="store_true", help="Save image without setting as wallpaper")
    parser.add_argument("--output-dir", default="~/Pictures/Wallpapers", help="Directory to save images")
    parser.add_argument("--list-ids", action="store_true", help="List previous generation IDs")
    parser.add_argument("--test-session", action="store_true", help="Test session lock/idle status and exit")
    parser.add_argument("--reset-base-prompt", action="store_true", help="Reset the base prompt for today and start from scratch")
    parser.add_argument("--skip-upscale", action="store_true", help="Skip AI upscaling (save original 1792x1024)")
    parser.add_argument("--upscale-size", default="3840x2160", help="Target upscale resolution (default: 3840x2160)")
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

    # Three-stage process: Theme -> Prompt -> Image
    if args.reset_base_prompt:
        print("🔄 Resetting theme and base prompt for today...")
        # Stage 1: Generate new theme
        print("🎭 Stage 1/3: Generating new theme...")
        theme = generate_new_theme(client)
        print(f"   Theme: {theme}")
        save_theme_to_history(theme)

        # Stage 2: Generate prompt based on theme
        print("📝 Stage 2/3: Generating prompt from theme...")
        base_prompt = get_new_base_prompt(client, theme)
        save_daily_prompt(theme, base_prompt)
        print(f"   Prompt: {base_prompt}")
    else:
        theme, base_prompt = load_daily_prompt()
        # If we don't have both theme and prompt (e.g., old format or new day), generate both
        if not base_prompt or not theme:
            print("🌅 Generating new theme and base prompt for today...")
            # Stage 1: Generate new theme
            print("🎭 Stage 1/3: Generating new theme...")
            theme = generate_new_theme(client)
            print(f"   Theme: {theme}")
            save_theme_to_history(theme)

            # Stage 2: Generate prompt based on theme
            print("📝 Stage 2/3: Generating prompt from theme...")
            base_prompt = get_new_base_prompt(client, theme)
            save_daily_prompt(theme, base_prompt)
            print(f"   Prompt: {base_prompt}")
        else:
            print(f"🎭 Using today's theme: {theme}")
            print(f"📝 Using today's base prompt: {base_prompt}")
    # Build full prompt for this run (Stage 3 prepares the final image generation prompt)
    print("🖼️  Stage 3/3: Generating image with location/time context...")
    full_prompt = build_full_prompt(base_prompt, client)
    print(f"   Final prompt: {full_prompt}")
    # Find previous image for today (thread)
    iterate_id = get_previous_image_id_today()
    quality = validate_quality(args.quality)
    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    # Generate image
    result = generate_image(client, full_prompt, quality, iterate_id)
    filename = create_filename(full_prompt, "1792x1024", quality, result["id"], upscaled=False)
    output_path = os.path.join(output_dir, filename)

    if save_image_from_base64(result["image_base64"], output_path):
        print(f"✅ Image generated successfully!")
        print(f"🆔 Generation ID: {result['id']}")

        final_path = output_path
        final_size = "1792x1024"

        # Upscale if not skipped
        if not args.skip_upscale:
            # Parse upscale size
            try:
                upscale_w, upscale_h = map(int, args.upscale_size.split('x'))
                upscale_filename = create_filename(full_prompt, "3840x2160", quality, result["id"], upscaled=True)
                upscale_path = os.path.join(output_dir, upscale_filename)

                if upscale_image_realesrgan(output_path, upscale_path, target_size=(upscale_w, upscale_h)):
                    final_path = upscale_path
                    final_size = f"{upscale_w}x{upscale_h}"
                    print(f"🎯 Final resolution: {final_size}")
                else:
                    print(f"⚠️  Using original resolution: {final_size}")
            except ValueError:
                print(f"⚠️  Invalid upscale size format: {args.upscale_size}. Use WIDTHxHEIGHT (e.g., 3840x2160)")
                print(f"   Using original resolution: {final_size}")
        else:
            print(f"⏭️  Skipping upscale (original resolution: {final_size})")

        # Save history
        history = load_generation_history()
        history[result["id"]] = {
            "prompt": result["prompt"],
            "response_id": result["response_id"],
            "size": final_size,
            "quality": result["quality"],
            "timestamp": result["timestamp"],
            "iterate_from": result["iterate_from"],
            "file_path": final_path,
            "original_path": output_path if final_path != output_path else None
        }
        save_generation_history(history)

        # Set wallpaper using final (upscaled or original) image
        if not args.save_only:
            set_wallpaper(final_path)
        else:
            print(f"📁 Image saved to: {final_path}")

        print(f"💡 Use '--iterate {result['id']}' to refine this image")
    print("🎉 Done!")


if __name__ == "__main__":
    main()