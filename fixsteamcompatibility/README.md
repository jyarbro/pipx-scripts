# fixsteamcompatibility

Utility that moves Steam Proton `compatdata/` prefixes to a native filesystem and replaces them with symlinks.

## Usage

```bash
fixsteamcompatibility
```

## Features

* Detects Steam library locations
* Moves Proton prefixes to native filesystem
* Creates symlinks to maintain functionality
* Fixes issues with non-native filesystems like NTFS or exFAT

## Requirements

* Steam with Proton compatibility tools installed
* Write access to Steam library folders
