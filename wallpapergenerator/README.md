# WallpaperGenerator

Generate AI wallpapers using OpenAI's GPT-image-1 with response models for iterative refinement.

## Features

- **GPT-image-1 Integration**: Uses the latest image generation model
- **Response Models**: Track generated images by ID for future reference
- **Iterative Refinement**: Generate variations of previous images with feedback
- **Generation History**: Maintains a local database of all generated images
- **Cross-Platform Wallpaper Setting**: Supports GNOME, KDE, and feh

## Installation

Install via pipx:
```bash
pipx install /path/to/wallpapergenerator
```

## Setup

1. Get an OpenAI API key from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Save your API key to `~/.openai_api_key`:
   ```bash
   echo "your-api-key-here" > ~/.openai_api_key
   ```

## Usage

### Basic Generation
```bash
wallpapergenerator "a serene mountain landscape at sunset"
```

### Iterative Refinement
```bash
# Generate initial image
wallpapergenerator "abstract geometric patterns"

# List previous generations to get ID
wallpapergenerator --list-ids

# Iterate on a previous image
wallpapergenerator --iterate gen_20250727_143022_1234 "make it more vibrant with golden colors"
```

### Advanced Options
```bash
# High-definition wide wallpaper
wallpapergenerator --size 1792x1024 --quality hd "cyberpunk city at night"

# Save without setting as wallpaper
wallpapergenerator --save-only "minimalist forest scene"

# Custom output directory
wallpapergenerator --output-dir ~/Desktop/MyWallpapers "space nebula"
```

## Commands

- `wallpapergenerator "prompt"` - Generate new wallpaper
- `wallpapergenerator --iterate <id> "feedback"` - Refine existing image
- `wallpapergenerator --list-ids` - Show generation history
- `wallpapergenerator --help` - Show detailed help

## Options

- `--iterate <id>`: Iterate on a previous image using its generation ID
- `--size`: Image dimensions (1024x1024, 1792x1024, 1024x1792)
- `--quality`: Image quality (standard, hd)
- `--save-only`: Save image without setting as wallpaper
- `--output-dir`: Directory to save images (default: ~/Pictures/Wallpapers)
- `--list-ids`: List previous generation IDs with metadata

## Response Model Benefits

The tool uses OpenAI's response format to track generated images:

1. **Persistent History**: All generations are saved with unique IDs
2. **Iterative Workflow**: Reference previous images to create variations
3. **Metadata Tracking**: Store prompts, settings, and relationships
4. **Easy Management**: List and reference past generations

## Examples

```bash
# Nature series
wallpapergenerator "misty forest with sunbeams"
wallpapergenerator --iterate gen_123 "add more wildlife and birds"

# Abstract progression
wallpapergenerator "geometric patterns in blue"
wallpapergenerator --iterate gen_456 "make it more angular and add red accents"

# Seasonal variations
wallpapergenerator "autumn landscape"
wallpapergenerator --iterate gen_789 "transform to winter scene with snow"
```

## Files

- `~/.openai_api_key` - Your OpenAI API key
- `~/.wallpapergenerator_history.json` - Generation history and metadata
- `~/Pictures/Wallpapers/` - Default save location for generated images
