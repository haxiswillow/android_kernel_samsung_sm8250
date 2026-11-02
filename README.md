# Mushroom Samsung SM8250 Kernel

# Introduction
- Custom kernel for the Samsung Galaxy S20 FE Snapdragon (`r8q`).
- Based on the LineageOS SM8250 tree, built for LineageOS 20 / AOSP Android 13.
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
- WALT, UCLAMP and Mushroom UI Prime placement, enabled by default.
- Qualcomm schedutil with adapted 5.10 frequency-limit fixes.
- Optional KernelSU v0.9.5 integration.
- Multi-generational LRU, ZRAM tuning and `madvise` THP defaults.
- KCAL display controls.
- Adreno 650 native DVFS, with frequencies up to 740 MHz.
- Native CPU–DDR bandwidth profile.
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

The script downloads Proton Clang and AnyKernel3 into `.build/`, applies the
installer changes and packages the ZIP automatically. KernelSU is vendored.
No separate compiler or KernelSU clone is needed.

| Command | SELinux | KernelSU |
| --- | --- | --- |
| `bash build.sh su` | Enforcing | Yes |
| `bash build.sh stock` | Enforcing | No |
| `bash build.sh permsu` | Permissive | Yes |
| `bash build.sh perm` | Permissive | No |

Run `bash build.sh` for help. Use `JOBS=8 bash build.sh su` to limit build jobs.
The default is the 5.4 scheduler with UCLAMP; `SCHED_CORE=legacy` keeps the old
scheduler available for comparison.

Build output: `out/<variant>/`. Flashable ZIPs: `dist/`.
Example: `MushroomKernel-KSU-r8q-<hex timestamp>.zip`.

For Telegram delivery, put the bot token in `token.txt` and the destination in
`chat_id.txt`, at the source root. Each file contains its value. Missing or
empty values skip delivery; `TELEGRAM=0` disables it explicitly. Credentials,
downloaded tools and build outputs stay outside Git.

## Notes
- This kernel combines contributions from LineageOS, Qualcomm, Linux, KernelSU,
  the MGLRU backport authors and other upstream projects.
- AnyKernel3 by osm0sis. Proton Clang by kdrag0n. Original licenses and credits
  remain in the source.
- The CPU–DDR profile controls bandwidth votes; it is not a DDR PLL overclock.
- Features and defaults can be overridden by the ROM or a kernel manager.

## Engineered to perfection.
