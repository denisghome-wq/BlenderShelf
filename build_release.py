"""Package a clean, shareable copy of BlenderShelf -- stock 3 buttons,
default colors/position, none of your personal customizations.

Run: python build_release.py
Output: dist/BlenderShelf.zip (install it in Blender via
Preferences > Add-ons > Install..., same as any other addon zip).
"""
import os
import shutil
import zipfile

ADDON_SRC = os.path.join(
    os.environ["APPDATA"], "Blender Foundation", "Blender", "4.4",
    "scripts", "addons", "BlenderShelf",
)
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
STAGE_DIR = os.path.join(OUT_DIR, "BlenderShelf")
ZIP_PATH = os.path.join(OUT_DIR, "BlenderShelf.zip")

# shelf_config.json holds your live buttons/colors/position; backups/ is
# your own revert history. Neither belongs in a copy meant for other people.
EXCLUDE_NAMES = {"shelf_config.json", "backups", "__pycache__"}


def _ignore(_dir, names):
    return [n for n in names if n in EXCLUDE_NAMES or n.endswith(".pyc")]


def main():
    if not os.path.isdir(ADDON_SRC):
        raise SystemExit(f"Addon not found at: {ADDON_SRC}")

    shutil.rmtree(STAGE_DIR, ignore_errors=True)
    shutil.copytree(ADDON_SRC, STAGE_DIR, ignore=_ignore)

    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(STAGE_DIR):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, OUT_DIR)  # keeps "BlenderShelf/..." as the zip's top folder
                zf.write(full, rel)

    print(f"Clean release built: {ZIP_PATH}")
    print("Excluded:", ", ".join(sorted(EXCLUDE_NAMES)))
    print("First enable on a fresh install seeds the 3 stock buttons "
          "(Cube/CubeSphere/Cyl) and default colors/position.")


if __name__ == "__main__":
    main()
