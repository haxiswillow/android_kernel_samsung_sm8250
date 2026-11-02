# Mushroom / r8q / AOSP Android 13

This build entry point targets the Snapdragon Galaxy S20 FE (`r8q`), using
`vendor/lineage_r8q_defconfig` from `lineage-20_4.19.260-atakan`.
It does not target Exynos models or One UI ports.

## Host setup

Use Linux x86_64, a source path without spaces, and sufficient free disk/RAM.
For Debian/Ubuntu, install the host tools once:

```sh
sudo apt update
sudo apt install build-essential git curl bc bison flex libssl-dev libelf-dev \
    python3 zip unzip xz-utils gzip tar util-linux
```

The first build downloads the official **Proton Clang 13.0.0, 20210522**
archive at `9fb011b183fe7e69b04b873ef6533b4b077e3c5e`, with SHA-256 verification.
This is the last official Proton build, **older** than the previous Android
Clang 14.0.6. Android 13 does not require a newer compiler to boot; compiler
version alone is not a performance benchmark. LLVM/IAS compile the target;
distribution GCC/G++ and binutils build host tools, including on Ubuntu 24.04.
`CLANG_DIR=/absolute/path` selects another complete LLVM toolchain explicitly.
The script does not silently switch compilers after a download/build failure.

## Build variants

`bash build.sh` displays English help without changing anything.

| Command | SELinux | KernelSU |
| --- | --- | --- |
| `bash build.sh su` | Enforcing | v0.9.5 |
| `bash build.sh stock` | Enforcing | Disabled |
| `bash build.sh permsu` | Always permissive | v0.9.5 |
| `bash build.sh perm` | Always permissive | Disabled |

`stock` means non-root Mushroom, not a Samsung factory kernel. Enforcing builds start permissive for init's SELinux preparation,
then Android enables enforcing after restorecon. Permissive builds retain SELinux
and its policy but prevent userspace from switching enforcement on.

```sh
JOBS=8 bash build.sh su
TELEGRAM=0 bash build.sh stock
CONFIG_ONLY=1 bash build.sh permsu
MGLRU=0 bash build.sh su  # classic-LRU A/B build
CLEAN=1 bash build.sh perm
```

`CONFIG_ONLY=1` generates and verifies configuration without compiling,
packaging, or sending. Clang is still needed for Kconfig probes.
Each variant has a separate `out/<variant>/`. The script regenerates its
configuration every time and locks the checkout against simultaneous builds.
Do not run manual make commands in the same output during a build.

## Naming and release settings

Kernel release: `4.19.260:MushroomKernel/<hex Unix timestamp>`. The version is read
from Makefile; automatic Git suffixes are disabled. The hex timestamp identifies
the build, not the commit. `SOURCE_DATE_EPOCH` can supply a fixed epoch.
ZIP: `MushroomKernel-KSU-r8q-<hex timestamp>.zip` for su; Stock, KSU-Permissive,
and Permissive identify the other variants.

The release fragment keeps `-O2` and disables debug symbols. The separate
`mushroom/performance.config` adds the first performance batch. It is merged
for every variant. CPU tuning uses Cortex-A77 scheduling with the original
Cortex-A55-compatible instruction set. LTO/CFI remain disabled.

See `mushroom/PERFORMANCE_V4.md` for MGLRU, EXT4, kernel background masks
and the optional UCLAMP build. See `mushroom/PERFORMANCE_V3.md` for scoped UI hints, the companion profile
and current VM policy. `mushroom/PERFORMANCE_V2.md` describes KCAL/zRAM setup.
`mushroom/PERFORMANCE.md` records the first batch and experimental
GPU overclock and rollback commands. Booting and benchmarking on r8q remain
necessary; compilation does not validate runtime frequency or latency gains.

## AnyKernel3

The script downloads/caches the traditional upstream installer:
https://github.com/osm0sis/AnyKernel3
Revision: `41f04bdb4ee30a44e429c2c1131d5e8bb32b15f1`.
To update deliberately, review a new revision and change `AK3_COMMIT`.

Each build exports a clean temporary directory from that exact revision and
renders `mushroom/anykernel.sh` with the release and variant. No manual installer
edits or separate fork are needed. LICENSE, tools, and META-INF are retained.
The root payload is `Image`, `dtb`, `dtbo.img`, and `anykernel.sh`, following
the supplied not-kernel example.

DTB includes only `kona-v2.1`, `kona-v2`, and `kona`, in filename order. DTBO
includes Samsung's common system-update overlay then r8q EUR r00-r10, matching
this tree's EUR project configuration. The installer checks the device,
Android 13, both partition paths, and payloads. It preserves the ROM ramdisk,
sets SELinux cmdline values, and uses upstream checked boot/DTBO writers.
The unrelated not-kernel `android.is_aosp`/BPF switches are not copied because
this tree does not consume them. There is no duplicate raw dd of DTBO.

Successful builds write ZIP, SHA-256, effective config, manifest, and log to
`dist/`. Errors stop before upload. Existing ZIPs are never overwritten.

Two existing base-tree build defects are corrected: IKCONFIG uses the selected
Kconfig output instead of hardcoding `out/.config`; CNSS2 reports EOPNOTSUPP
for its optional PCIe hang-register dump because this tree's PCIe controller
has no msm_pcie_reg_dump implementation. That diagnostic cannot produce a
register dump on this base; adding a declaration alone would fail at link time.

## KernelSU

The official non-GKI guide identifies v0.9.5 as the final supported original
release for older kernels:
https://kernelsu.org/guide/how-to-integrate-for-non-gki.html

Sources are vendored in `drivers/kernelsu/`, with the upstream license and
revision in `UPSTREAM.md`. There are no nested repositories/submodules and
no build-time Git/network operations for KSU. Kprobes are enabled only for
su/permsu. Linux 5.9's path_umount API is backported alongside the existing
Samsung syscall implementation for KernelSU's module unmount support.

Install official **KernelSU v0.9.5 (11872) Manager** from
https://github.com/tiann/KernelSU/releases/tag/v0.9.5 and use its Install action
to provision the daemon/module environment. The upstream embedded-daemon stub
is retained. Do not pair this with the current Manager or a different fork.
Root/modules must be checked on r8q; compilation cannot verify boot kprobes.

## Telegram

Put one value each into root `token.txt` and `chat_id.txt`. Missing files are
created empty with mode 0600. Use a local editor to keep tokens out of shell
history:

```sh
nano token.txt
nano chat_id.txt
chmod 600 token.txt chat_id.txt
```

Plain values, matching single/double quotes, and `TOKEN='value'` /
`CHAT_ID='value'` are supported. They are data, never sourced or evaluated.
Destination: numeric chat ID, negative group ID, or public `@channel` name.
The bot needs permission to post to that destination.

After success, the script sends the absolute ZIP path through sendDocument
with an empty caption. The URL/token goes through curl stdin configuration,
not process arguments or verbose logs. Empty credentials skip upload.
A failed upload returns an error but keeps the ZIP. POST requests are not
retried automatically, avoiding duplicates on uncertain timeouts.
`TELEGRAM=0` disables upload. Telegram's own size limits still apply.

## One final Git commit

The script never stages, commits, or pushes. `.build/`, `out/`, `dist/`,
`token.txt`, and `chat_id.txt` are ignored. Check and commit once when ready:

```sh
git status --short
git diff --check
git diff --stat
git add .gitignore BUILDING.md build.sh build_kernel.sh mushroom \
    drivers/Kconfig drivers/Makefile drivers/kernelsu fs/namespace.c \
    drivers/net/wireless/cnss2/pci.c include/linux/mount.h kernel/Makefile \
    security/selinux mushroom/performance.config \
    arch/arm64/boot/dts/vendor/qcom/kona-v2-gpu.dtsi \
    drivers/block/zram/zram_drv.c drivers/devfreq/governor_msm_adreno_tz.c \
    drivers/input/input_booster.c drivers/input/touchscreen/stm/fts5cu56a/fts_ts.c \
    include/linux/input.h include/linux/input/sec_tsp_log.h \
    kernel/sched/cpufreq_schedutil.c kernel/sched/fair.c kernel/sched/walt.c \
    kernel/sched/tune.c kernel/cgroup/cpuset.c mm/vmscan.c mm/swap.c \
    include/linux/mushroom_ui.h drivers/soc/qcom/Makefile \
    drivers/soc/qcom/mushroom_ui.c arch/arm64/boot/dts/samsung/r8q \
    mm/page-writeback.c \
    techpack/display/msm/Makefile techpack/display/msm/sde/sde_plane.c \
    techpack/display/msm/sde/mushroom_kcal.c techpack/display/msm/sde/mushroom_kcal.h \
    apply.py
git diff --cached --stat
git commit -m "r8q: add Mushroom Android 13 build pipeline, KernelSU and performance profile"
git push origin lineage-20_4.19.260-atakan
```

No commit is needed between edits or builds.
