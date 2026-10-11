#!/usr/bin/env python3
"""Merge a matching signed APK set into a standalone, signed ARM64 APK."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--tools", type=Path, required=True)
parser.add_argument("--java-home", type=Path)
parser.add_argument("--apk-set", type=Path,
                    default=ROOT / "Instagram-450.0.0.50.77-NoReels-APK-set.zip")
parser.add_argument("--signing-dir", type=Path, default=ROOT / ".signing")
parser.add_argument("--output", type=Path,
                    default=ROOT / "Instagram-NoReels-450.0.0.50.77-arm64.apk")
args = parser.parse_args()
java_home = args.java_home or (Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME")
                              else next(args.tools.glob("jdk*/Contents/Home")))
java = str(java_home / "bin/java")
args.output.parent.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory(prefix="instagram-noreels-merge-") as temporary:
    work = Path(temporary)
    sources = work / "input"
    sources.mkdir()
    with zipfile.ZipFile(args.apk_set) as archive:
        names = archive.namelist()
        if len(names) != 5 or "base.apk" not in names:
            raise RuntimeError("Expected the complete five-APK set")
        for name in names:
            if "/" in name or "\\" in name or name.startswith('.') or not name.endswith('.apk'):
                raise RuntimeError("Unexpected archive member: " + name)
            (sources / name).write_bytes(archive.read(name))
    unsigned = work / "merged-unsigned.apk"
    subprocess.run([java, "-Xmx4096m", "-jar", str(args.tools / "APKEditor.jar"),
                    "m", "-i", str(sources), "-o", str(unsigned),
                    "-extractNativeLibs", "true", "-validate-modules"], check=True)
    with zipfile.ZipFile(sources / "base.apk") as base, zipfile.ZipFile(unsigned) as merged:
        dex_names = [name for name in base.namelist() if re.fullmatch(r"classes\d*\.dex", name)]
        for name in dex_names:
            if base.read(name) != merged.read(name):
                raise RuntimeError("Base bytecode changed during merge: " + name)
        if merged.testzip() is not None:
            raise RuntimeError("Merged ZIP integrity failed")
    env = os.environ.copy()
    env["TASK_SIGNING_PASSWORD"] = (args.signing_dir / "key-password.txt").read_text()
    signer = [java, "-cp", str(args.tools / "uber-apk-signer.jar"),
              "com.android.apksigner.ApkSignerTool"]
    subprocess.run(signer + ["sign", "--ks", str(args.signing_dir / "instagram-no-reels.jks"),
        "--ks-key-alias", "instagram-no-reels", "--ks-pass", "env:TASK_SIGNING_PASSWORD",
        "--key-pass", "env:TASK_SIGNING_PASSWORD", "--v4-signing-enabled", "false",
        "--out", str(args.output), str(unsigned)], env=env, check=True)
    subprocess.run(signer + ["verify", "--verbose", "--print-certs", str(args.output)], check=True)
with args.output.open("rb") as stream:
    digest = hashlib.file_digest(stream, "sha256").hexdigest()
print(f"SHA-256 {digest}  {args.output.name}", flush=True)
print(f"Preserved all {len(dex_names)} patched base DEX files", flush=True)
