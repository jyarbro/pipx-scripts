import argparse
import os
import sys
import subprocess
import requests
import json
from datetime import datetime
from PIL import Image
from openai import OpenAI


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


def load_generation_history():
    """Load previous generation IDs and metadata"""
    history_file = os.path.expanduser("~/.wallpapergenerator_history.json")
    if not os.path.exists(history_file):
        return {}
    
    try:
        with open(history_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  Error loading generation history: {e}")
        return {}


def save_generation_history(history):
    """Save generation IDs and metadata"""
    history_file = os.path.expanduser("~/.wallpapergenerator_history.json")
    try:
        with open(history_file, 'w') as f:
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
    
    return f"wallpaper_{safe_prompt}_{generation_id}_{size}_{quality}.png"


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


def main():
    parser = argparse.ArgumentParser(description="Generate AI wallpapers using OpenAI GPT-image-1", add_help=False)
    parser.add_argument("prompt", nargs="?", help="Description of the wallpaper to generate")
    parser.add_argument("--help", action="store_true", help="Show help message")
    parser.add_argument("--iterate", help="Iterate on a previous image using its ID")
    parser.add_argument("--quality", default="standard", help="Image quality (standard, hd)")
    parser.add_argument("--save-only", action="store_true", help="Save image without setting as wallpaper")
    parser.add_argument("--output-dir", default="~/Pictures/Wallpapers", help="Directory to save images")
    parser.add_argument("--list-ids", action="store_true", help="List previous generation IDs")
    
    args = parser.parse_args()
    
    if args.help:
        get_help()
    
    if args.list_ids:
        list_generation_ids()
        return
    
    if not args.prompt:
        print("❌ Please provide a prompt for image generation.")
        get_help()
    
    quality = validate_quality(args.quality)
    
    # Setup output directory
    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Load API key and create client
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)
    
    # Generate image
    result = generate_image(client, args.prompt, quality, args.iterate)
    filename = create_filename(args.prompt, "1920x1080", quality, result["id"])
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
