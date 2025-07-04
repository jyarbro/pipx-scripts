# brightshift

Simple CLI tool for adjusting screen brightness on all connected displays using `xrandr`.

## Usage

```bash
brightshift night         # Set brightness to 30%
brightshift day           # Set brightness to 100%
brightshift custom 0.5    # Set brightness to 50%
```

## Features

* Works on all `xrandr`-compatible displays
* Automatically detects connected outputs
* Simple command structure
* Compatible with desktop launchers and keyboard shortcuts

## Requirements

* X11 (not compatible with Wayland)
* `xrandr` must be available in system path
