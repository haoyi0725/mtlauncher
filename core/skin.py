# -*- coding: utf-8 -*-
"""皮膚檔案 + 產生 MtLauncher 資源包"""
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Optional, List, Tuple
from .logger import get_logger

logger = get_logger()

WIDE_NAMES = [
    "alex.png", "ari.png", "efe.png", "kai.png", "makena.png",
    "noor.png", "steve.png", "sunny.png", "zuri.png",
]
SLIM_NAMES = list(WIDE_NAMES)
LEGACY_NAMES = ["steve.png", "alex.png"]

def get_skins_dir(data_root: Path) -> Path:
    d = Path(data_root) / "skins"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_resource_packs_dir(data_root: Path) -> Path:
    d = Path(data_root) / "resourcepacks"
    d.mkdir(parents=True, exist_ok=True)
    return d

def skin_path_for_player(data_root: Path, player_name: str) -> Path:
    safe = "".join(
        c for c in (player_name or "") if c.isalnum() or c in "-_"
    ).strip() or "player"
    return get_skins_dir(data_root) / f"{safe}.png"

def get_resource_pack_path(data_root: Path) -> Path:
    return get_resource_packs_dir(data_root) / "MtLauncher_Skin.zip"

def get_pack_icon_path(data_root: Path) -> Path:
    """開發者自訂資源包圖示：data/skins/pack.png"""
    return get_skins_dir(data_root) / "pack.png"

def get_player_skin(data_root: Path, player_name: str) -> Optional[Path]:
    p = skin_path_for_player(data_root, player_name)
    return p if p.exists() else None

def _make_pack_icon_bytes(icon_path: Path) -> bytes:
    try:
        from PIL import Image
        img = Image.open(icon_path).convert("RGBA")
        img = img.resize((128, 128), Image.NEAREST)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return Path(icon_path).read_bytes()

def build_skin_resource_pack(
    data_root: Path,
    skin_png: Path,
    pack_icon: Optional[Path] = None
) -> Path:
    skin_png = Path(skin_png)
    if not skin_png.exists():
        raise FileNotFoundError(str(skin_png))

    out = get_resource_pack_path(data_root)
    out.parent.mkdir(parents=True, exist_ok=True)

    pack_mcmeta = {
        "pack": {
            "pack_format": 34,
            "description": "MtLauncher Custom Skin"
        }
    }

    # 優先：開發者放的 data/skins/pack.png
    # 其次：傳入的 pack_icon
    # 最後：用皮膚本身
    dev_icon = get_pack_icon_path(data_root)
    if pack_icon is not None and Path(pack_icon).exists():
        icon_path = Path(pack_icon)
    elif dev_icon.exists():
        icon_path = dev_icon
    else:
        icon_path = skin_png

    icon_bytes = _make_pack_icon_bytes(icon_path)
    skin_bytes = skin_png.read_bytes()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "pack.mcmeta",
            json.dumps(pack_mcmeta, ensure_ascii=False, indent=2)
        )
        zf.writestr("pack.png", icon_bytes)

        for name in WIDE_NAMES:
            zf.writestr(
                f"assets/minecraft/textures/entity/player/wide/{name}",
                skin_bytes
            )
        for name in SLIM_NAMES:
            zf.writestr(
                f"assets/minecraft/textures/entity/player/slim/{name}",
                skin_bytes
            )
        for name in LEGACY_NAMES:
            zf.writestr(
                f"assets/minecraft/textures/entity/{name}",
                skin_bytes
            )

    logger.info(f"Resource pack built: {out} (icon={icon_path})")
    return out

def save_skin(
    data_root: Path,
    player_name: str,
    src_png: Path,
    pack_icon: Optional[Path] = None
) -> Tuple[Path, Path]:
    src = Path(src_png)
    if not src.exists():
        raise FileNotFoundError(str(src))
    if src.suffix.lower() != ".png":
        raise ValueError("皮膚必須是 PNG 檔")

    dest = skin_path_for_player(data_root, player_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    logger.info(f"Skin saved: {dest}")

    # 不讓使用者指定圖示；固定優先讀 data/skins/pack.png
    pack = build_skin_resource_pack(data_root, dest, pack_icon=None)
    return dest, pack

def rebuild_pack_if_possible(data_root: Path, player_name: str) -> Optional[Path]:
    skin = get_player_skin(data_root, player_name)
    if not skin:
        return None
    return build_skin_resource_pack(data_root, skin, pack_icon=None)

def remove_player_skin(data_root: Path, player_name: str) -> bool:
    """只刪玩家皮膚與資源包，不刪開發者的 pack.png"""
    ok = False
    p = skin_path_for_player(data_root, player_name)
    if p.exists():
        p.unlink()
        ok = True
    pack = get_resource_pack_path(data_root)
    if pack.exists():
        pack.unlink()
        ok = True
    return ok

def install_pack_to_instance(data_root: Path, instance_dir: Path) -> Optional[Path]:
    src = get_resource_pack_path(data_root)
    if not src.exists():
        return None
    dest_dir = Path(instance_dir) / "resourcepacks"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "MtLauncher_Skin.zip"
    shutil.copy2(src, dest)
    return dest

def enable_pack_in_options(
    instance_dir: Path,
    pack_filename: str = "MtLauncher_Skin.zip"
):
    options = Path(instance_dir) / "options.txt"
    pack_entry = f"file/{pack_filename}"
    lines: List[str] = []

    if options.exists():
        try:
            lines = options.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
        except Exception:
            lines = []

    new_lines = []
    found = False
    for line in lines:
        if line.startswith("resourcePacks:"):
            new_lines.append(f'resourcePacks:["vanilla","{pack_entry}"]')
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f'resourcePacks:["vanilla","{pack_entry}"]')

    try:
        options.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to write options.txt: {e}")