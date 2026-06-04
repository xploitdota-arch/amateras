import json
import urllib.request
from pathlib import Path

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"

def get_version_list(mc_dir: Path = None) -> list[dict]:
    try:
        with urllib.request.urlopen(MANIFEST_URL, timeout=10) as resp:
            data = json.loads(resp.read())
        if mc_dir:
            with open(mc_dir / "manifest.json", 'w', encoding='utf-8') as f:
                json.dump(data, f)
        return data["versions"]
    except Exception:
        if mc_dir and (mc_dir / "manifest.json").exists():
            with open(mc_dir / "manifest.json", 'r', encoding='utf-8') as f:
                return json.load(f)["versions"]
        return []

def get_version_info(version_id: str) -> dict | None:
    try:
        versions = get_version_list()
        ver_entry = next((v for v in versions if v["id"] == version_id), None)
        if not ver_entry: return None
        with urllib.request.urlopen(ver_entry["url"], timeout=10) as resp:
            return json.loads(resp.read())
    except Exception:
        return None