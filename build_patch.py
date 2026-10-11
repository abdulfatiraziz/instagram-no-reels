#!/usr/bin/env python3
"""Build the version-specific Instagram navigation patch without modifying the input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import struct
import subprocess
import zipfile

EXPECTED_SHA256 = "241ef5537888f5931522335891fdb9b9408393e708f1a08fae9440100d8f339c"
ROOT = Path(__file__).resolve().parent


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(command, *, env=None, log=None):
    result = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if log:
        (ROOT / log).write_text(result.stdout)
    if result.returncode:
        raise RuntimeError(result.stdout[-6000:])
    if result.stdout.strip():
        print(result.stdout.strip()[-2000:], flush=True)


def patch_method(text, signature, expected, replacement):
    start = text.index(".method " + signature + "\n")
    end = text.index(".end method", start)
    body = text[start:end]
    if body.count(expected) != 1:
        raise RuntimeError(f"Unexpected method body: {signature}")
    return text[:start] + body.replace(expected, replacement, 1) + text[end:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--java-home", type=Path)
    args = parser.parse_args()
    if sha256(args.source) != EXPECTED_SHA256:
        raise RuntimeError("This patch only accepts the inspected original APK SHA-256")
    args.work.mkdir(parents=True, exist_ok=True)
    java_home = args.java_home or (Path(os.environ["JAVA_HOME"]) if os.environ.get("JAVA_HOME") else next(args.tools.glob("jdk*/Contents/Home")))
    java = str(java_home / "bin/java")
    javac = str(java_home / "bin/javac")
    classpath = os.pathsep.join(str(args.tools / name) for name in
                               ("jadx-headless-mcp.jar", "jcommander.jar"))
    original_dex = args.work / "classes2-original.dex"
    with zipfile.ZipFile(args.source) as apk:
        original_dex.write_bytes(apk.read("classes2.dex"))
    smali_root = args.work / "patch-smali"
    run([java, "-cp", classpath, "com.android.tools.smali.baksmali.Main", "disassemble",
         str(original_dex), "--classes", "LX/00MT;", "-o", str(smali_root)])
    smali = smali_root / "X/00MT.smali"
    original = smali.read_text()
    (ROOT / "00MT-original.smali").write_text(original)
    patched = patch_method(
        original,
        "public static final A00(Lcom/instagram/common/session/UserSession;)Ljava/util/List;",
        "    return-object v0",
        """    # Copy the fixed-size tablet tab list, then omit the Reels enum.
    new-instance v1, Ljava/util/ArrayList;
    invoke-direct {v1, v0}, Ljava/util/ArrayList;-><init>(Ljava/util/Collection;)V
    sget-object v0, LX/02xk;->A08:LX/02xk;
    invoke-virtual {v1, v0}, Ljava/util/AbstractCollection;->remove(Ljava/lang/Object;)Z
    return-object v1""")
    patched = patch_method(
        patched,
        "public final A03(Lcom/instagram/common/session/UserSession;Z)Ljava/util/List;",
        "    return-object v3",
        """    # Both phone and tablet configurations use this shared return path.
    new-instance v0, Ljava/util/ArrayList;
    invoke-direct {v0, v3}, Ljava/util/ArrayList;-><init>(Ljava/util/Collection;)V
    sget-object v1, LX/02xk;->A08:LX/02xk;
    invoke-virtual {v0, v1}, Ljava/util/AbstractCollection;->remove(Ljava/lang/Object;)Z
    return-object v0""")
    patched = patch_method(
        patched,
        "public final A01(Lcom/instagram/common/session/UserSession;)LX/02xk;",
        "sget-object v0, LX/02xk;->A08:LX/02xk;",
        "sget-object v0, LX/02xk;->A0C:LX/02xk;")
    smali.write_text(patched)
    (ROOT / "00MT-patched.smali").write_text(patched)
    patch_dex = args.work / "replacement.dex"
    run([java, "-cp", classpath, "com.android.tools.smali.smali.Main", "assemble",
         str(smali_root), "-o", str(patch_dex)])
    run([javac, "-cp", str(args.tools / "jadx-headless-mcp.jar"), "-d", str(args.work),
         str(ROOT / "MergeDex.java")])
    merged_dex = args.work / "classes2-patched.dex"
    run([java, "-Xmx2048m", "-cp", str(args.work) + os.pathsep + classpath, "MergeDex",
         str(original_dex), str(patch_dex), str(merged_dex)], log="dex-merge.log")
    unsigned = args.work / "Instagram-NoReels-unsigned.apk"
    removed = []
    with zipfile.ZipFile(args.source) as src, zipfile.ZipFile(unsigned, "w") as dst:
        for info in src.infolist():
            name = info.filename
            if (re.fullmatch(r"META-INF/[^/]+\.(SF|RSA|DSA|EC)", name, re.I)
                    or name.upper() == "META-INF/MANIFEST.MF"
                    or name in {"META-INF/code_transparency_signed.jwt", "stamp-cert-sha256"}):
                removed.append(name)
                continue
            payload = merged_dex.read_bytes() if name == "classes2.dex" else src.read(name)
            clone = zipfile.ZipInfo(name, info.date_time)
            clone.compress_type = info.compress_type
            clone.external_attr = info.external_attr
            clone.create_system = info.create_system
            clone.comment = info.comment
            # Android requires four-byte alignment for stored entries. Also support
            # 16-KiB alignment if a future input has uncompressed native libraries.
            if clone.compress_type == zipfile.ZIP_STORED:
                alignment = 16384 if name.endswith(".so") else 4
                header_end = dst.fp.tell() + 30 + len(name.encode("utf-8"))
                padding = (-header_end) % alignment
                if padding:
                    if padding < 4:
                        padding += alignment
                    clone.extra = struct.pack("<HH", 0xD935, padding - 4) + bytes(padding - 4)
            dst.writestr(clone, payload, compresslevel=6)
    print("Repacked APK with only classes2.dex payload changed", flush=True)
    signing = ROOT / ".signing"
    signing.mkdir(mode=0o700, exist_ok=True)
    key = signing / "instagram-no-reels.jks"
    password_file = signing / "key-password.txt"
    if not key.exists():
        password_file.write_text(secrets.token_urlsafe(32))
        password_file.chmod(0o600)
        env = os.environ.copy()
        env["TASK_SIGNING_PASSWORD"] = password_file.read_text()
        run([str(java_home / "bin/keytool"), "-genkeypair", "-keystore", str(key),
             "-storetype", "JKS", "-alias", "instagram-no-reels", "-keyalg", "RSA",
             "-keysize", "3072", "-validity", "10000", "-dname", "CN=Instagram No Reels Local Build",
             "-storepass:env", "TASK_SIGNING_PASSWORD", "-keypass:env", "TASK_SIGNING_PASSWORD"], env=env)
        key.chmod(0o600)
    env = os.environ.copy()
    env["TASK_SIGNING_PASSWORD"] = password_file.read_text()
    output = ROOT / "Instagram-450.0.0.50.77-NoReels.apk"
    signer = [java, "-cp", str(args.tools / "uber-apk-signer.jar"),
              "com.android.apksigner.ApkSignerTool"]
    run(signer + ["sign", "--ks", str(key), "--ks-key-alias", "instagram-no-reels",
                  "--ks-pass", "env:TASK_SIGNING_PASSWORD", "--key-pass", "env:TASK_SIGNING_PASSWORD",
                  "--v4-signing-enabled", "false", "--out", str(output), str(unsigned)],
        env=env, log="apk-sign.log")
    run(signer + ["verify", "--verbose", "--print-certs", str(output)], log="apk-verify.log")
    report = {"source": str(args.source), "source_sha256": EXPECTED_SHA256,
              "output": str(output), "output_sha256": sha256(output),
              "version": "450.0.0.50.77", "package": "com.instagram.android",
              "changed_dex": "classes2.dex", "changed_class": "LX/00MT;",
              "changed_methods": ["A00", "A01", "A03"],
              "removed_stale_signing_metadata": removed,
              "on_device_test": "not performed; user will test on their phone"}
    (ROOT / "build-report.json").write_text(json.dumps(report, indent=2) + "\n")
    if sha256(args.source) != EXPECTED_SHA256:
        raise RuntimeError("Original input unexpectedly changed")
    print("Built:", output, flush=True)


if __name__ == "__main__":
    main()
