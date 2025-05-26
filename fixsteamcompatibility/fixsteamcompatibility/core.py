import os
import shutil
from pathlib import Path

def main():
    original_compatdata = Path("/mnt/games/Games/Steam/steamapps/compatdata")
    new_compatdata_root = Path.home() / "SteamCompatData"

    new_compatdata_root.mkdir(parents=True, exist_ok=True)

    for prefix_dir in original_compatdata.iterdir():
        if prefix_dir.is_dir():
            appid = prefix_dir.name
            new_location = new_compatdata_root / appid

            if prefix_dir.is_symlink():
                print(f"[SKIP] {appid} is already a symlink.")
                continue
            if new_location.exists():
                print(f"[SKIP] {appid} already exists at new location.")
                continue

            print(f"[MOVE] {appid} -> {new_location}")
            shutil.move(str(prefix_dir), str(new_location))
            os.symlink(str(new_location), str(prefix_dir))

    print("Done.")
