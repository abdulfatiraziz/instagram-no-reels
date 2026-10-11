# Building the version-specific patch

The supplied build targets Instagram 450.0.0.50.77, version code 385611395. The
input base APK SHA-256 must be:

```text
241ef5537888f5931522335891fdb9b9408393e708f1a08fae9440100d8f339c
```

Obtain the complete matching APK set from your own installation. The set used for
this release had `base.apk`, the XXHDPI density split, and the AR segmentation,
executorch, and pytorch feature splits. Keep their original package/version
identities consistent. Do not mix different releases.

## Tools

Use Python 3.11+ and a full JDK 21. Put these JARs in a tools directory:

| Local filename | Version / source |
| --- | --- |
| `jadx-headless-mcp.jar` | [JADX headless MCP 0.7.1](https://github.com/1013503897/jadx-headless-mcp/releases/tag/v0.7.1) |
| `jcommander.jar` | JCommander 1.82 from Maven Central |
| `uber-apk-signer.jar` | [uber-apk-signer 1.3.0](https://github.com/patrickfav/uber-apk-signer/releases/tag/v1.3.0) |
| `APKEditor.jar` | [APKEditor 1.4.9](https://github.com/REAndroid/APKEditor/releases/tag/V1.4.9) |

Analysis used REA 6.4.0. Rebuilding the known patch uses the Java bytecode tools
directly. No tool binaries or upstream app sources are vendored in this repo.

JADX engine SHA-256:

```text
6e5eacf500b64292bfb73c49797c1958f6ee44646e43e868039ae7feb573ff75
```

APKEditor SHA-256:

```text
a9cd40df818845456be6d696de6110c89edf4b0a0580cb83438ed6b25a366e67
```

## Build the base

```sh
python3 build_patch.py --source /path/to/base.apk \
  --tools /path/to/tools --work /path/to/temporary-work \
  --java-home /path/to/jdk
```

The script disassembles `LX/00MT;` from `classes2.dex`, changes three methods,
assembles only that class, and merges it back into the original DEX. It then
repackages and signs the APK with a locally generated key.

`A00` and `A03` omit `CLIPS` from tablet and phone tab lists. `A01` substitutes Feed
for the Reels default. The source APK is never overwritten.

Generated signing keys and their password file live in `.signing/`, which is
ignored by Git. Keep your own key private. A key generated on your machine will
produce a different certificate from the published release.

## Build the complete set and standalone APK

Put the original base and four matching splits in an `original-package/` folder:

```sh
python3 sign_package_set.py --original-set original-package \
  --tools /path/to/tools --java-home /path/to/jdk
python3 merge_standalone.py --tools /path/to/tools --java-home /path/to/jdk
```

The second script merges the APKs in a temporary directory, removes the split
requirement through APKEditor's merge operation, signs the standalone output,
verifies its signature, and checks that all original base DEX payloads survived.

## Validation

- `VerifyDex.java` compares canonical disassembly for every class in the rebuilt
  `classes2.dex`. It also checks effective exception-handler selection where the
  DEX writer normalizes redundant catch tables.
- The original patch deliberately changes only three methods in one class.
  The other 9,878 classes have equivalent instructions, metadata, and exception
  behavior. Sixteen exception tables are normalized by the writer.
- The patched split base retains 10,478 original non-signing APK payloads
  byte-for-byte; `classes2.dex` is its only changed application payload.
- Each companion APK retains its non-signing payloads and uses the same new key.
- Standalone packaging additionally changes the manifest/resource tables to merge
  the splits; it preserves the already-patched base DEX bytecode.
- Check signatures and checksums, then test installation, login, remaining tabs,
  and a cold restart on a device before distributing a build.

There is no unattended upload workflow or private signing key in this repository.
