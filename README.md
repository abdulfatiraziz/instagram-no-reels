# Instagram No Reels

Keep Instagram's Home, Messages, Search, and Profile tabs. Remove the dedicated
Reels button from the bottom navigation.

This is an independent Android modification of Instagram **450.0.0.50.77**.
Reels can still appear in the feed, profiles, Explore, and messages. The change
removes the navigation shortcut; it does not block every Reel.

## Download

- **[Download the single ARM64 APK](https://github.com/abdulfatiraziz/instagram-no-reels/releases/download/v450.0.0.50.77-1/Instagram-NoReels-450.0.0.50.77-arm64.apk)** — install this file directly.
- [Download the five-APK set](https://github.com/abdulfatiraziz/instagram-no-reels/releases/download/v450.0.0.50.77-1/Instagram-NoReels-450.0.0.50.77-APK-set.zip) — alternate package for a split-APK installer or ADB.
- [Checksums](https://github.com/abdulfatiraziz/instagram-no-reels/releases/download/v450.0.0.50.77-1/SHA256SUMS.txt) · [All releases](https://github.com/abdulfatiraziz/instagram-no-reels/releases)

**Build:** ARM64 (`arm64-v8a`), Android 9+ as declared by the manifest, with XXHDPI
image resources. Tested on a Pixel 8a running Android 17. Other devices and
configurations have not been tested.

## Install

1. Save any local Instagram drafts you want to keep.
2. If you have official Instagram installed, uninstall it first. This build has
   a different signing certificate, and uninstalling clears local app data and
   login state.
3. Download and open the single APK on your phone. Allow installation from your
   browser or file manager when Android requests it.
4. Install, sign in, and look for four bottom tabs: Home, Messages, Search, Profile.

The five-file alternative must be installed together. Extract its ZIP, then run:

```sh
adb install-multiple base.apk split_config.xxhdpi.apk \
  split_arservicesforpersonsegmentation.apk \
  split_executorch.apk split_pytorch.apk
```

Keep all five files from the same release. The base APK in that set cannot be
installed on its own.

## What changed

The shared tab factory excludes Instagram's internal `CLIPS` enum from both phone
and tablet tab lists. Where the default launch tab would be Reels, it selects Feed.
The package retains Instagram's online services and account login flow.

The single APK combines the tested base and four companion APKs using
[APKEditor](https://github.com/REAndroid/APKEditor). Its manifest and resources are
adapted for standalone installation. The alternate set retains split packaging.

The [verification record](docs/verification.json) lists the source hash, signing
certificate fingerprint, and device checks. The original navigation patch was
analyzed with [REA](https://github.com/morluto/rea) and its pinned JADX engine.

## Privacy and signing

Release files contain application packages, not anyone's logged-in session.
This repository excludes private signing keys, passwords, phone pairing keys,
device connection details, personal screenshots, and account data.

The APK uses a project signing certificate rather than Meta's certificate.
Its SHA-256 fingerprint is:

```text
607dfb009763b5cca08f9b40f0c55189d3e67c6149a8e06852f23ec96ae4807f
```

## Build or inspect the patch

See [BUILDING.md](BUILDING.md). The patch is tied to the exact APK SHA-256 recorded
in the verification file. It stops if a different source APK is supplied. A new
Instagram version requires fresh inspection and testing.

For bug reports, include the Instagram version, Android version, phone model, and
the failing screen. Exclude passwords, session tokens, and private account data.

## License and affiliation

This project is not affiliated with or endorsed by Instagram or Meta. The
[MIT license](LICENSE) covers the original helper scripts and documentation in
this repository. It does not grant rights to Instagram's application code,
branding, or assets, which retain their respective ownership and licensing.
