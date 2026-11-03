# Mushroom Samsung SM8250 Kernel

# Introduction
- Custom kernel for the Samsung Galaxy S20 FE Snapdragon (`r8q`).
- Based on the LineageOS SM8250 tree, built for LineageOS 20 / crDroid 9 and AOSP Android 13.
- Maintained by Nihil — [@donottellmyname](https://t.me/donottellmyname).

## Warning
- This source is **always under development** and may cause unexpected problems.
- Keep a working boot image before flashing.
- Credit Nihil and the original authors if you use this source.
- **You have been warned.**

## Warranty
- None. No guarantees.
- You are responsible for what you flash.

## Features
- Linux 4.19.260 with the Qualcomm 5.4.302 scheduler backport.
- WALT, UCLAMP, Mushroom UI Prime placement and scoped compositor/QS scheduling.
- Qualcomm schedutil with adapted 5.10 frequency-limit and latency fixes.
- Optional BakaSU / ReSukiSU v4.2.0-rc3, vendored and pinned.
- Renewable CPU interaction floors: 1708 / 2246 / 2553 MHz for 250 ms.
- Native CPU–DDR bandwidth pulse for 500 ms, triggered by input and top-app promotion.
- Multi-generational LRU with the Android memory-accounting correction.
- LZ4 ZRAM defaults and THP restricted to applications using `madvise`.
- KCAL display controls.
- Adreno 650 native DVFS, with frequencies up to 740 MHz.
- Deadline I/O scheduling for UFS, with latency-oriented defaults.
- EXT4 and encrypted F2FS userdata support.
- Pinned Proton Clang 13 and automatic AnyKernel3 packaging.
- Optional Telegram delivery of completed builds.

## Build — CachyOS

Linux x86_64 is required. Install the host dependencies:

```bash
sudo pacman -Syu --needed base-devel git python bc openssl curl zip unzip cpio
```

Clone the Mushroom branch:

```bash
git clone --single-branch --branch lineage-20_4.19.260-atakan --depth=1 \
  https://github.com/haxiswillow/android_kernel_samsung_sm8250.git
cd android_kernel_samsung_sm8250
bash build.sh su
```

The script downloads the pinned Proton toolchain and AnyKernel3 into `.build/`,
prepares the installer and creates the ZIP. Root sources are included in Git.
Published configuration profiles in `mushroom/configs/` are applied automatically
for their matching variant, followed by the selected root and SELinux settings.

| Command | SELinux | Root |
| --- | --- | --- |
| `bash build.sh su` | Enforcing | BakaSU / ReSukiSU |
| `bash build.sh stock` | Enforcing | No |
| `bash build.sh permsu` | Permissive | BakaSU / ReSukiSU |
| `bash build.sh perm` | Permissive | No |

Run `bash build.sh` for help. Use `JOBS=8 bash build.sh su` to limit build jobs.
The default is the 5.4 scheduler with UCLAMP. `CONFIG_PROFILE=none` skips the
published profile; `SCHED_CORE=legacy SCHED_POLICY=stune` selects the legacy path.

Build output: `out/<variant>/`. Flashable ZIPs: `dist/`.
Example: `MushroomKernel-KSU-r8q-<hex timestamp>.zip`.
The configuration is reproducible; dates and ZIP metadata can differ between builds.
The publication record in `mushroom/build-profile.json` retains the approved build's
variant, configuration fingerprint, compiler description and original epoch.

For Telegram delivery, put the bot token in `token.txt` and the destination in
`chat_id.txt`, at the source root. Missing or empty values skip delivery;
`TELEGRAM=0` disables it. Credentials, downloaded tools, backups and build outputs
stay outside Git.

## Notes
- This kernel combines contributions from LineageOS, Qualcomm, Linux, KernelSU,
  BakaSU/ReSukiSU, the MGLRU backport authors and other upstream projects.
- AnyKernel3 by osm0sis. Proton Clang by kdrag0n. Original licenses and credits
  remain in the source.
- CPU–DDR settings control bandwidth votes; they are not a DDR PLL overclock.
- Interaction pulses expire automatically and obey the existing effective maximum limits.
- Features and defaults can be overridden by the ROM or a kernel manager.

## Engineered to perfection.
