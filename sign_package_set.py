#!/usr/bin/env python3
"""Combine the patched base with matching official companion APKs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--original-set", type=Path, required=True)
parser.add_argument("--tools", type=Path, required=True)
parser.add_argument("--java-home", type=Path)
args = parser.parse_args()
report_path = ROOT / "build-report.json"
report = json.loads(report_path.read_text())
with (args.original_set / "base.apk").open("rb") as stream:
    restored_digest = hashlib.file_digest(stream, "sha256").hexdigest()
if restored_digest != report["source_sha256"]:
    raise RuntimeError("Restored base differs from the inspected APK; inspect it before combining splits")
signing = ROOT / ".signing"
env = os.environ.copy()
env["TASK_SIGNING_PASSWORD"] = (signing / "key-password.txt").read_text()
java_home = args.java_home or (Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME") else next(args.tools.glob("jdk*/Contents/Home")))
java = str(java_home / "bin/java")
signer = [java, "-cp", str(args.tools / "uber-apk-signer.jar"),
          "com.android.apksigner.ApkSignerTool"]
output = ROOT / "installable-package"
output.mkdir(exist_ok=True)
shutil.copyfile(ROOT / "Instagram-450.0.0.50.77-NoReels.apk", output / "base.apk")
splits = [p for p in sorted(args.original_set.glob("*.apk"))
          if p.name != "base.apk" and not p.name.startswith('.')]
if not splits:
    raise RuntimeError("The supplied base requires companion APKs")
for split in splits:
    destination = output / split.name
    subprocess.run(signer + ["sign", "--ks", str(signing / "instagram-no-reels.jks"),
        "--ks-key-alias", "instagram-no-reels", "--ks-pass", "env:TASK_SIGNING_PASSWORD",
        "--key-pass", "env:TASK_SIGNING_PASSWORD", "--v4-signing-enabled", "false",
        "--out", str(destination), str(split)], env=env, check=True)
    result = subprocess.run(signer + ["verify", "--verbose", "--print-certs", str(destination)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    (ROOT / (split.stem + "-verify.log")).write_text(result.stdout)
    with zipfile.ZipFile(split) as source, zipfile.ZipFile(destination) as patched:
        for name in source.namelist():
            if name.startswith("META-INF/") or name == "stamp-cert-sha256":
                continue
            if source.read(name) != patched.read(name):
                raise RuntimeError(f"Companion APK payload changed: {split.name} / {name}")
    print("Signed and verified companion APK:", split.name, flush=True)
bundle = ROOT / "Instagram-450.0.0.50.77-NoReels-APK-set.zip"
with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_STORED) as archive:
    for apk in sorted(p for p in output.glob("*.apk") if not p.name.startswith('.')):
        archive.write(apk, apk.name)
report["companion_apks"] = [p.name for p in splits]
report["installable_bundle"] = str(bundle)
with bundle.open("rb") as stream:
    report["bundle_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
report_path.write_text(json.dumps(report, indent=2) + "\n")
print("Complete APK set:", bundle, flush=True)
