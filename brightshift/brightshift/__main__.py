#!/usr/bin/env python3

import sys
import subprocess

def get_connected_outputs():
    try:
        xrandr_output = subprocess.check_output(["xrandr", "--current"], text=True)
        return [
            line.split()[0]
            for line in xrandr_output.splitlines()
            if " connected" in line
        ]
    except Exception as e:
        print(f"Failed to detect displays: {e}")
        sys.exit(1)

def set_brightness(output: str, level: float):
    try:
        subprocess.run(["xrandr", "--output", output, "--brightness", str(level)],
                       check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error setting brightness on {output}: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: brightshift [night|day|custom <value>]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "night":
        level = 0.3
    elif command == "day":
        level = 1.0
    elif command == "custom" and len(sys.argv) == 3:
        try:
            level = float(sys.argv[2])
        except ValueError:
            print("custom value must be a float (e.g., 0.5)")
            sys.exit(1)
    else:
        print("Invalid command.")
        print("Usage: brightshift [night|day|custom <value>]")
        sys.exit(1)

    outputs = get_connected_outputs()
    for output in outputs:
        set_brightness(output, level)

if __name__ == "__main__":
    main()