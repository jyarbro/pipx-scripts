# kernelcleaner

Tool that removes old Linux kernel versions to help keep your system clean and reclaim disk space.

## Usage

```bash
kernelcleaner
```

## Features

* Detects and lists all installed kernel packages
* Preserves currently running kernel and newest available kernel
* Removes outdated kernel packages using `apt`
* Provides clear, color-coded terminal output

## Requirements

* Debian/Ubuntu-based Linux distribution
* `apt` package manager
* Administrative privileges
