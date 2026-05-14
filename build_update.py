#!/usr/bin/env python3
"""build_update.py - Create update package for Vault Zero with GitHub Releases support"""

import os
import json
import hashlib
import zipfile
import shutil
import platform
import argparse
from pathlib import Path
from datetime import datetime

def hash_file(path: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def get_file_size(path: Path) -> int:
    return path.stat().st_size

def build_update(version: str, changelog: str, github_repo: str = None):
    """
    Create update.zip package and manifest.json.
    
    Args:
        version: Version string (e.g., "1.0.1")
        changelog: What's new in this version
        github_repo: "username/repo" for GitHub Releases (optional)
    """
    
    build_dir = Path("build_update")
    update_dir = build_dir / f"v{version}"
    update_dir.mkdir(parents=True, exist_ok=True)
    
    # Platform-specific executable name
    exe_name = "VaultZero.exe" if platform.system() == "Windows" else "VaultZero"
    dist_exe = Path("dist") / exe_name
    
    if not dist_exe.exists():
        print(f"❌ Executable not found at {dist_exe}. Run pyinstaller first.")
        return False
    
    # Copy executable
    shutil.copy2(dist_exe, update_dir / exe_name)
    print(f"✓ Copied {exe_name}")
    
    # Copy Lua scripts
    lua_dir = Path("lua")
    if lua_dir.exists():
        if (update_dir / "lua").exists():
            shutil.rmtree(update_dir / "lua")
        shutil.copytree(lua_dir, update_dir / "lua")
        print("✓ Copied Lua scripts")
    
    # Copy audio assets (optional)
    audio_dir = Path("audio")
    if audio_dir.exists():
        if (update_dir / "audio").exists():
            shutil.rmtree(update_dir / "audio")
        shutil.copytree(audio_dir, update_dir / "audio")
        print("✓ Copied audio assets")
    
    # Copy C extension if present
    c_ext_map = {
        "Windows": "c_hash.pyd",
        "Linux": "c_hash.so",
        "Darwin": "c_hash.dylib"
    }
    c_ext = c_ext_map.get(platform.system(), "")
    if c_ext and Path(c_ext).exists():
        shutil.copy2(c_ext, update_dir / c_ext)
        print(f"✓ Copied C extension: {c_ext}")
    
    # Build manifest
    manifest = {
        "version": version,
        "min_version": "1.0.0",
        "release_date": datetime.now().isoformat(),
        "changelog": changelog,
        "components": {
            "python_main": {
                "file": exe_name,
                "hash": hash_file(update_dir / exe_name),
                "size": get_file_size(update_dir / exe_name)
            }
        }
    }
    
    # Add Lua scripts to manifest if any
    lua_files = list((update_dir / "lua").rglob("*.lua")) if (update_dir / "lua").exists() else []
    if lua_files:
        manifest["components"]["lua_scripts"] = {"files": []}
        for lf in lua_files:
            rel_path = lf.relative_to(update_dir)
            manifest["components"]["lua_scripts"]["files"].append({
                "path": str(rel_path),
                "hash": hash_file(lf),
                "size": get_file_size(lf)
            })
    
    # Add C extension to manifest if present
    if c_ext and (update_dir / c_ext).exists():
        plat_key = f"{platform.system().lower()}_{platform.machine().lower()}"
        manifest["components"]["c_extension"] = {
            "platforms": {
                plat_key: {
                    "file": c_ext,
                    "hash": hash_file(update_dir / c_ext),
                    "size": get_file_size(update_dir / c_ext)
                }
            }
        }
    
    # Determine download URL
    if github_repo:
        # GitHub Release asset URL pattern
        download_url = f"https://github.com/EscapeRoomBSCS2A/releases/download/v{version}/v{version}_update.zip"
        manifest["download_url"] = download_url
        print(f"\n🔗 Using GitHub Releases download URL:\n   {download_url}")
    else:
        manifest["download_url"] = f"https://your-server.com/vault-zero/updates/v{version}_update.zip"
        print("\n⚠️ No GitHub repo provided. Update the download_url manually in the manifest.")
    
    # Write manifest
    manifest_path = update_dir / "version_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"✓ Manifest written: {manifest_path}")
    
    # Create ZIP archive
    zip_path = build_dir / f"v{version}_update.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in update_dir.rglob("*"):
            if file.name != "arena.db":  # don't include user DB
                zf.write(file, file.relative_to(update_dir))
    
    zip_hash = hash_file(zip_path)
    print(f"\n✅ Update package created: {zip_path}")
    print(f"   Size: {zip_path.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"   SHA256: {zip_hash}")
    
    # GitHub Release instructions
    if github_repo:
        print(f"\n📦 NEXT STEPS FOR GITHUB RELEASE:")
        print(f"   1. Go to https://github.com/EscapeRoomBSCS2A/releases/new")
        print(f"   2. Tag version: v{version}")
        print(f"   3. Release title: Vault Zero {version}")
        print(f"   4. Attach this file: {zip_path}")
        print(f"   5. (Optional) Attach version_manifest.json as well")
        print(f"   6. Publish the release")
        print(f"\n   Your game will auto-detect the update at:")
        print(f"   {manifest['download_url']}")
    else:
        print(f"\n📋 MANUAL UPLOAD:")
        print(f"   - Upload {zip_path} to your server")
        print(f"   - Serve version_manifest.json at your update URL")
        print(f"   - Update your game's update_url to point there")
    
    # Also save manifest separately for easy upload
    manifest_copy = build_dir / "version_manifest.json"
    shutil.copy2(manifest_path, manifest_copy)
    print(f"\n📄 Manifest also saved to: {manifest_copy}")
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Build Vault Zero update package for GitHub Releases')
    parser.add_argument('--version', required=True, help='Version number (e.g., 1.0.1)')
    parser.add_argument('--changelog', required=True, help='Update changelog (use quotes for multi-line)')
    parser.add_argument('--repo', help='GitHub repo in format "username/repo" (e.g., "BioStaR/vault-zero")')
    args = parser.parse_args()
    
    build_update(args.version, args.changelog, args.repo)