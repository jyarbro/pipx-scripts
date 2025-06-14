import subprocess
import os
from pathlib import Path
from colorama import Fore, Style, init
from typing import Optional

init(autoreset=True)

MAX_SIZE_MB = 200
MIN_BITRATE = 192
BITRATE_STEP = 16
VBR_PRIORITY = [0, 1, 2, 3, 4]
CBR_STEPS = [320, 288, 256, 240, 224, 208, 192]

def get_bitrate_kbps(filepath: Path) -> Optional[int]:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=bit_rate", "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
            capture_output=True, text=True, check=True
        )
        bitrate = int(float(result.stdout.strip()) / 1000)
        return bitrate
    except Exception:
        return None

def get_filesize_mb(filepath: Path) -> float:
    return filepath.stat().st_size / 1024 / 1024

def reencode_file(source: Path, target: Path, bitrate: Optional[int] = None, vbr_quality: Optional[int] = None, verbose: bool = False):
    ext = target.suffix.lower()
    codec = "libmp3lame" if ext == ".mp3" else "aac"
    cmd = ["ffmpeg", "-hide_banner"]
    if verbose:
        cmd += ["-loglevel", "error"]
    else:
        cmd += ["-loglevel", "quiet"]
    cmd += ["-i", str(source), "-vn", "-map_metadata", "-1", "-c:a", codec]
    if vbr_quality is not None:
        cmd += ["-q:a", str(vbr_quality)]
    elif bitrate is not None:
        cmd += ["-b:a", f"{bitrate}k"]
    cmd += [str(target), "-y"]

    subprocess.run(cmd, check=True)

def main():
    for ext in ("*.mp3", "*.m4a"):
        for filepath in Path().glob(ext):
            if not filepath.is_file() or filepath.name.startswith("OLD."):
                continue

            size_mb = get_filesize_mb(filepath)
            original_bitrate = get_bitrate_kbps(filepath)

            print(f"{Style.BRIGHT}\n📦  {filepath.name}")
            print(f"    {Style.DIM}├─ Size:     {size_mb:.2f} MB")
            if original_bitrate:
                print(f"    {Style.DIM}├─ Bitrate:  {original_bitrate} kbps")
            else:
                print(f"    {Style.DIM}├─ Bitrate:  unknown")

            if size_mb < MAX_SIZE_MB:
                print(f"    {Fore.GREEN}✔ Skipping (under 200MB)")
                continue

            if original_bitrate is None:
                print(f"    {Fore.RED}✘ Could not get bitrate, skipping")
                continue

            est_target_bitrate = int(original_bitrate * (MAX_SIZE_MB / size_mb))
            trial_bitrate = max(est_target_bitrate, MIN_BITRATE)

            print(f"    {Style.DIM}├─ Target:   under {MAX_SIZE_MB} MB (min {MIN_BITRATE} kbps)")
            print(f"    {Style.DIM}├─ Estimated acceptable CBR bitrate: {trial_bitrate} kbps")

            attempts = [(None, vbr) for vbr in VBR_PRIORITY]
            attempts += [(b, None) for b in CBR_STEPS if b <= original_bitrate and b >= MIN_BITRATE and b <= trial_bitrate]

            for i, (bitrate, vbr_quality) in enumerate(attempts):
                temp_output = filepath.with_name(f"TEMP.{filepath.name}")
                label = f"{bitrate} kbps" if bitrate else f"VBR q={vbr_quality}"
                verbose = i == 0
                try:
                    print(f"    {Fore.CYAN}▶ Trying {label} ...")
                    reencode_file(filepath, temp_output, bitrate, vbr_quality, verbose=verbose)

                    result_size = get_filesize_mb(temp_output)
                    size_report = f"→ Result: {result_size:.2f} MB"
                    if result_size < MAX_SIZE_MB:
                        print(f"    {Fore.GREEN}{size_report} ✅ success — replacing original")
                        backup = filepath.with_name(f"OLD.{filepath.name}")
                        os.rename(filepath, backup)
                        os.rename(temp_output, filepath)
                        break
                    else:
                        print(f"    {Fore.YELLOW}{size_report} ❌ too large")
                        temp_output.unlink(missing_ok=True)
                except Exception:
                    temp_output.unlink(missing_ok=True)
                    print(f"    {Fore.RED}✘ ffmpeg failed for {label}")
            else:
                print(f"    {Fore.RED}❌ Could not reduce below {MAX_SIZE_MB} MB with acceptable quality")
