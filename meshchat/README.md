# MeshChat Launcher

Auto-updating launcher for [Reticulum MeshChat](https://github.com/liamcottle/reticulum-meshchat/) AppImage.

## Features

- Automatically checks for the latest release from GitHub
- Downloads new versions only if newer than current
- Stores AppImages in `~/.config/meshchat/images/`
- Tracks current version in `~/.config/meshchat/current_version.json`
- Passes through command-line arguments to the AppImage

## Installation

Using pipx:

```bash
pipx install .
```

Or from the directory:

```bash
cd meshchat
pipx install .
```

## Usage

Simply run:

```bash
meshchat
```

The script will:
1. Check if you have the latest version
2. Download it if a newer version is available
3. Launch the AppImage

You can also pass arguments to the AppImage:

```bash
meshchat --help
```

## Version Storage

- AppImages are stored in: `~/.config/meshchat/images/`
- Version info: `~/.config/meshchat/current_version.json`
