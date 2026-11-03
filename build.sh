#!/usr/bin/env bash
# Mushroom / r8q / AOSP Android 13. Run from any working directory.
set +x
set -Eeuo pipefail
export LC_ALL=C

help() {
    cat <<'EOF'
Mushroom kernel builder - Galaxy S20 FE Snapdragon / AOSP Android 13

Usage: bash build.sh <variant>

  su       SELinux enforcing, with BakaSU / ReSukiSU v4.2.0-rc3
  stock    SELinux enforcing, without KernelSU
  permsu   SELinux permissive, with BakaSU / ReSukiSU v4.2.0-rc3
  perm     SELinux permissive, without KernelSU

No arguments, -h and --help display this help without building.

The first build downloads pinned Proton Clang and upstream AnyKernel3.
Outputs: out/<variant>/ and dist/. No commit or push is performed.
Put the Telegram bot token in token.txt and the destination in chat_id.txt
at the kernel root. Both are read as data, never executed or committed.
Missing/empty credentials skip upload. The Telegram caption is empty.

Optional environment variables:
  JOBS=8                  Parallel build jobs (default: available CPUs)
  MGLRU=0                 Start with classic LRU (default: MGLRU=1)
  SCHED_POLICY=uclamp     uclamp (default) or stune on the legacy scheduler
  SCHED_CORE=legacy       Use the legacy scheduler (default: 5.4 port)
  CLANG_DIR=/path/clang   Use an existing Clang/LLVM toolchain
  TELEGRAM=0              Disable Telegram upload (default: 1)
  CONFIG_PROFILE=none     Skip the published per-variant configuration profile
  CONFIG_ONLY=1           Generate and validate this variant's .config only
  CLEAN=1                 Clean this variant's output before building
  SOURCE_DATE_EPOCH=...    Fixed epoch for build ID and build timestamp
EOF
}

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '\n==> %s\n' "$*"; }

if [[ $# == 0 ]]; then help; exit 0; fi
if [[ $1 == -h || $1 == --help ]]; then help; exit 0; fi
[[ $# == 1 ]] || { help >&2; exit 2; }
VARIANT=$1
case "$VARIANT" in
    su)     WITH_KSU=1; ENFORCING=1; SELINUX=enforcing ;;
    stock)  WITH_KSU=0; ENFORCING=1; SELINUX=enforcing ;;
    permsu) WITH_KSU=1; ENFORCING=0; SELINUX=permissive ;;
    perm)   WITH_KSU=0; ENFORCING=0; SELINUX=permissive ;;
    *) help >&2; exit 2 ;;
esac

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
cd "$ROOT"
# Kbuild does not support source paths containing whitespace.
[[ $ROOT != *[[:space:]]* ]] || die 'Move the kernel to a path without spaces.'
CACHE="$ROOT/.build"
OUT="$ROOT/out/$VARIANT"
DIST="$ROOT/dist"
JOBS=${JOBS:-$(getconf _NPROCESSORS_ONLN)}
[[ $JOBS =~ ^[1-9][0-9]*$ ]] || die 'JOBS must be a positive integer.'
for setting in TELEGRAM CONFIG_ONLY CLEAN MGLRU; do
    value=${!setting:-}
    [[ -z $value || $value == 0 || $value == 1 ]] || die "$setting must be 0 or 1."
done

SCHED_CORE=${SCHED_CORE:-5.4}
case "$SCHED_CORE" in legacy|5.4) ;; *) die 'SCHED_CORE must be legacy or 5.4.' ;; esac
SCHED_POLICY=${SCHED_POLICY:-uclamp}
case "$SCHED_POLICY" in stune|uclamp) ;; *) die 'SCHED_POLICY must be stune or uclamp.' ;; esac
[[ $SCHED_CORE != 5.4 || $SCHED_POLICY == uclamp ]] || \
    die 'The 5.4 scheduler port requires SCHED_POLICY=uclamp.'


for cmd in git make sha256sum curl tar gzip python3 bc bison flex perl openssl zip unzip flock gcc g++ ld; do
    command -v "$cmd" >/dev/null || die "Missing dependency: $cmd. See README.md."
done
[[ $(uname -sm) == 'Linux x86_64' ]] || die 'The bundled tools require Linux x86_64.'
mkdir -p "$CACHE" "$OUT" "$DIST"
exec 9>"$CACHE/build.lock"
flock -n 9 || die 'Another Mushroom build is using this checkout.'
for credential in token.txt chat_id.txt; do
    if [[ ! -e $credential ]]; then (umask 077; : > "$credential"); fi
done

BUILD_EPOCH=${SOURCE_DATE_EPOCH:-$(date +%s)}
[[ $BUILD_EPOCH =~ ^[0-9]{1,10}$ ]] || die 'SOURCE_DATE_EPOCH must be a Unix timestamp.'
printf -v HEX_DATE '%x' "$((10#$BUILD_EPOCH))"
BASE_VERSION=$(sed -n 's/^VERSION = //p' Makefile).$(sed -n 's/^PATCHLEVEL = //p' Makefile).$(sed -n 's/^SUBLEVEL = //p' Makefile)
KERNEL_RELEASE="$BASE_VERSION:Mushroom/$HEX_DATE"
case "$VARIANT" in
    su) ZIP_VARIANT=KSU ;;
    stock) ZIP_VARIANT=Stock ;;
    permsu) ZIP_VARIANT=KSU-Permissive ;;
    perm) ZIP_VARIANT=Permissive ;;
esac
STEM="MushroomKernel-$ZIP_VARIANT-r8q-$HEX_DATE"
LOG="$DIST/$STEM.log"
TEMP=''
cleanup() { if [[ -n $TEMP && -d $TEMP ]]; then rm -rf -- "$TEMP"; fi; }
trap cleanup EXIT
trap 'printf "ERROR: Build stopped at line %s. See %s\n" "$LINENO" "$LOG" >&2' ERR
exec > >(tee "$LOG") 2>&1

setup_clang() {
    local dir archive
    local revision=9fb011b183fe7e69b04b873ef6533b4b077e3c5e
    local checksum=7358f655bd5af997990f208212da2687a9cd4d53cb4f1811d6035487e04076b8
    if [[ -n ${CLANG_DIR:-} ]]; then
        [[ -x $CLANG_DIR/bin/clang ]] || die 'CLANG_DIR must contain executable bin/clang.'
        dir=$(cd "$CLANG_DIR" && pwd -P)
    else
        dir="$CACHE/toolchains/proton-9fb011b1"
        if [[ ! -x $dir/bin/clang ]]; then
            info 'Downloading pinned official Proton Clang 13.0.0 (20210522)'
            mkdir -p "$CACHE/toolchains"
            TEMP=$(mktemp -d "$CACHE/toolchains/download.XXXXXX")
            archive="$TEMP/proton.tar.gz"
            curl --fail --location --silent --show-error --retry 3 \
                --connect-timeout 20 --max-time 1800 \
                "https://codeload.github.com/kdrag0n/proton-clang/tar.gz/$revision" \
                --output "$archive"
            printf '%s  %s\n' "$checksum" "$archive" | sha256sum --check --status || \
                die 'Proton archive checksum mismatch; refusing to use it.'
            mkdir "$TEMP/extract"
            tar -xzf "$archive" --strip-components=1 -C "$TEMP/extract"
            [[ -x $TEMP/extract/bin/clang ]] || die 'Incomplete Proton Clang download.'
            mv "$TEMP/extract" "$dir"
            cleanup; TEMP=''
        fi
    fi
    export PATH="$dir/bin:$PATH"
    for tool in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-strip llvm-readelf; do
        [[ -x $dir/bin/$tool ]] || die "Incomplete LLVM toolchain: $tool"
    done
    CLANG_VERSION=$(clang --version | sed -n '1p')
    info "$CLANG_VERSION"
}

# Proton bundles an old x86 linker. Host tools must use the distribution's
# binutils, which understand the host glibc's RELR sections (Ubuntu 24.04).
HOSTCC_BIN=$(command -v gcc)
HOSTCXX_BIN=$(command -v g++)
HOST_BINUTILS=$(dirname -- "$(command -v ld)")
setup_clang
export KBUILD_BUILD_USER=Mushroom KBUILD_BUILD_HOST=ServerHive
export KBUILD_BUILD_VERSION=1
KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$BUILD_EPOCH" '+%a %b %d %T UTC %Y')
export KBUILD_BUILD_TIMESTAMP
MAKE_ARGS=(O="$OUT" ARCH=arm64 LLVM=1 LLVM_IAS=1 KALLSYMS_EXTRA_PASS=1
    CC=clang LD=ld.lld AR=llvm-ar NM=llvm-nm KCFLAGS=-mtune=cortex-a77
    OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip
    READELF=llvm-readelf HOSTCC="$HOSTCC_BIN -B$HOST_BINUTILS/"
    HOSTCXX="$HOSTCXX_BIN -B$HOST_BINUTILS/"
    CROSS_COMPILE=aarch64-linux-gnu- CROSS_COMPILE_ARM32=arm-linux-gnueabi-
    CROSS_COMPILE_COMPAT=arm-linux-gnueabi- LOCALVERSION=
    DTC_EXT="$ROOT/tools/dtc" DTC_OVERLAY_TEST_EXT="$ROOT/tools/ufdt_apply_overlay")

if [[ ${CLEAN:-0} == 1 ]]; then make "${MAKE_ARGS[@]}" clean; fi
info "Configuring $VARIANT ($KERNEL_RELEASE)"
make "${MAKE_ARGS[@]}" vendor/lineage_r8q_defconfig
bash scripts/kconfig/merge_config.sh -m -O "$OUT" "$OUT/.config" mushroom/release.config mushroom/performance.config
# Replay the last published effective configuration for this variant.
# An explicit profile or "none" can be selected without changing source.
PROFILE=${CONFIG_PROFILE:-"$ROOT/mushroom/configs/$VARIANT.config"}
if [[ $PROFILE != none ]]; then
    if [[ -f $PROFILE ]]; then
        info "Applying validated configuration: $PROFILE"
        bash scripts/kconfig/merge_config.sh -m -O "$OUT" "$OUT/.config" "$PROFILE"
    elif [[ -n ${CONFIG_PROFILE:-} ]]; then
        die "CONFIG_PROFILE does not exist: $PROFILE"
    fi
fi
scripts/config --file "$OUT/.config" --set-str LOCALVERSION ":Mushroom/$HEX_DATE" \
    -e SECURITY_SELINUX -d SECURITY_SELINUX_BOOTPARAM -d SECURITY_SELINUX_DISABLE
if [[ $WITH_KSU == 1 ]]; then
    scripts/config --file "$OUT/.config" -e KSU -e KPROBES -e KPROBE_EVENTS \
        -e OVERLAY_FS -e KALLSYMS -e KALLSYMS_ALL -d KSU_DEBUG \
        -e KSU_MANUAL_HOOK -d KSU_TRACEPOINT_HOOK -d KSU_SUSFS \
        -e KSU_MULTI_MANAGER_SUPPORT -e KSU_MANUAL_HOOK_AUTO_SETUID_HOOK \
        -e KSU_MANUAL_HOOK_AUTO_INITRC_HOOK -e KSU_MANUAL_HOOK_AUTO_INPUT_HOOK \
        -e SECCOMP -e SECCOMP_FILTER
else
    scripts/config --file "$OUT/.config" -d KSU -d KPROBES -d KPROBE_EVENTS
fi
if [[ $ENFORCING == 1 ]]; then
    scripts/config --file "$OUT/.config" -d SECURITY_SELINUX_ALWAYS_PERMISSIVE \
        -e SECURITY_SELINUX_DEVELOP
else
    scripts/config --file "$OUT/.config" -e SECURITY_SELINUX_DEVELOP \
        -e SECURITY_SELINUX_ALWAYS_PERMISSIVE
fi
if [[ ${MGLRU:-1} == 0 ]]; then
    scripts/config --file "$OUT/.config" -d LRU_GEN_ENABLED
fi
if [[ $SCHED_POLICY == stune ]]; then
    scripts/config --file "$OUT/.config" -e SCHED_TUNE -d UCLAMP_TASK \
        -d UCLAMP_TASK_GROUP -e MUSHROOM_UI
fi
if [[ $SCHED_POLICY == uclamp ]]; then
    # Keep cpusets. UCLAMP replaces only the schedtune controller.
    scripts/config --file "$OUT/.config" -d SCHED_TUNE -d MUSHROOM_UI \
        -e UCLAMP_TASK -e UCLAMP_TASK_GROUP
fi
if [[ $SCHED_CORE == 5.4 ]]; then
    scripts/config --file "$OUT/.config" -e MUSHROOM_SCHED54
else
    scripts/config --file "$OUT/.config" -d MUSHROOM_SCHED54
fi
make "${MAKE_ARGS[@]}" olddefconfig

assert_config() {
    local name=$1 expected=$2 actual
    actual=$(scripts/config --file "$OUT/.config" -s "$name")
    [[ $actual == "$expected" || ( $expected == n && $actual == undef ) ]] || \
        die "Configuration dependency rejected $name=$expected (actual: $actual)."
}
if [[ $SCHED_CORE == 5.4 ]]; then
    assert_config MUSHROOM_SCHED54 y
else
    assert_config MUSHROOM_SCHED54 n
fi
assert_config SECURITY_SELINUX y
assert_config CC_IS_CLANG y
assert_config CC_OPTIMIZE_FOR_PERFORMANCE y
assert_config SEC_R8Q_PROJECT y
assert_config BUILD_ARM64_DT_OVERLAY y
assert_config MUSHROOM_KCAL y
assert_config MUSHROOM_BG_CPUSET y
assert_config LRU_GEN y
if [[ ${MGLRU:-1} == 0 ]]; then assert_config LRU_GEN_ENABLED n; else assert_config LRU_GEN_ENABLED y; fi
assert_config EXT4_FS y
# /data is F2FS on the affected r8q; EXT4 system partitions do not imply
# EXT4 userdata. This must be built in before init mounts encrypted data.
assert_config F2FS_FS y
assert_config F2FS_FS_ENCRYPTION y
assert_config FS_ENCRYPTION y
assert_config FS_ENCRYPTION_INLINE_CRYPT y
assert_config CRYPTO_CRC32_ARM64_CE y
assert_config GATOR n
assert_config DEBUG_QSPINLOCK_OWNER n
assert_config DEBUG_LIST n
assert_config SCHEDSTATS n
assert_config CPU_FREQ_DEFAULT_GOV_SCHEDUTIL y
assert_config HZ_1000 y
assert_config IOSCHED_DEADLINE y
assert_config DEFAULT_IOSCHED deadline
assert_config TRANSPARENT_HUGEPAGE_MADVISE y
assert_config TRANSPARENT_HUGEPAGE_ALWAYS n
if [[ $SCHED_POLICY == stune ]]; then
    assert_config SCHED_TUNE y
    assert_config UCLAMP_TASK n
    assert_config MUSHROOM_UI y
else
    assert_config SCHED_TUNE n
    assert_config UCLAMP_TASK y
    assert_config UCLAMP_TASK_GROUP y
fi
if [[ $WITH_KSU == 1 ]]; then
    assert_config KSU y; assert_config KPROBES y; assert_config KPROBE_EVENTS y
    assert_config KSU_MANUAL_HOOK y
    assert_config KSU_MULTI_MANAGER_SUPPORT y
    assert_config KALLSYMS_ALL y
    assert_config SECCOMP y; assert_config SECCOMP_FILTER y
else
    assert_config KSU n
fi
if [[ $ENFORCING == 1 ]]; then
    assert_config SECURITY_SELINUX_DEVELOP y
else
    assert_config SECURITY_SELINUX_ALWAYS_PERMISSIVE y
fi
[[ ${CONFIG_ONLY:-0} == 1 ]] && { info "Configuration ready: $OUT/.config"; exit 0; }

# Download once, then reuse an immutable upstream installer revision.
AK3_COMMIT=41f04bdb4ee30a44e429c2c1131d5e8bb32b15f1
AK3="$CACHE/AnyKernel3"
if [[ ! -d $AK3/.git ]]; then
    info 'Downloading upstream AnyKernel3'
    TEMP=$(mktemp -d "$CACHE/anykernel.XXXXXX")
    git -C "$TEMP" init -q
    git -C "$TEMP" remote add origin https://github.com/osm0sis/AnyKernel3.git
    git -C "$TEMP" fetch -q --depth=1 origin "$AK3_COMMIT"
    git -C "$TEMP" checkout -q --detach FETCH_HEAD
    mv "$TEMP" "$AK3"; TEMP=''
fi
[[ $(git -C "$AK3" rev-parse HEAD) == "$AK3_COMMIT" ]] || die 'Unexpected AnyKernel3 revision.'

info "Building Image and device trees with $JOBS jobs"
START=$SECONDS
make -j"$JOBS" "${MAKE_ARGS[@]}" Image dtbs
BOOT="$OUT/arch/arm64/boot"
[[ -s $BOOT/Image ]] || die 'Image was not produced.'

# Only the three SM8250 base DTBs belong here, in stable filename order.
DTBS=("$BOOT/dts/vendor/qcom/kona-v2.1.dtb"
      "$BOOT/dts/vendor/qcom/kona-v2.dtb" "$BOOT/dts/vendor/qcom/kona.dtb")
for dtb in "${DTBS[@]}"; do [[ -s $dtb ]] || die "Missing DTB: $dtb"; done
cat "${DTBS[@]}" > "$BOOT/dtb"
# Include Samsung's system-update overlay followed by the r8q EUR revisions.
DTBOS=("$BOOT/dts/samsung/common/kona-sec-system-update-overlay.dtbo")
for rev in {00..10}; do
    DTBOS+=("$BOOT/dts/samsung/r8q/kona-sec-r8q-eur-overlay-r$rev.dtbo")
done
for dtbo in "${DTBOS[@]}"; do [[ -s $dtbo ]] || die "Missing DTBO: $dtbo"; done
tools/mkdtimg create "$BOOT/dtbo.img" --page_size=4096 "${DTBOS[@]}"

TEMP=$(mktemp -d "$CACHE/package.XXXXXX")
git -C "$AK3" archive "$AK3_COMMIT" | tar -xf - -C "$TEMP"
rm -rf "$TEMP/.github" "$TEMP/modules" "$TEMP/patch" "$TEMP/ramdisk"
rm -f "$TEMP/README.md" "$TEMP/.gitignore" "$TEMP/.gitattributes"
python3 - mushroom/anykernel.sh "$TEMP/anykernel.sh" "$KERNEL_RELEASE" \
    "$VARIANT" "$SELINUX" "$ENFORCING" <<'PY'
import pathlib, sys
src, dst, release, variant, selinux, enforcing = sys.argv[1:]
text = pathlib.Path(src).read_text()
for key, value in zip(('KERNEL_RELEASE', 'VARIANT', 'SELINUX', 'ENFORCING'),
                      (release, variant, selinux, enforcing)):
    text = text.replace('@' + key + '@', value)
pathlib.Path(dst).write_text(text)
PY
python3 mushroom/prepare-installer.py "$TEMP"
if [[ $WITH_KSU == 1 && $SCHED_POLICY == stune ]]; then
    python3 mushroom/package-policy.py "$TEMP/Mushroom-Policy-KSU.zip"
fi
cp "$BOOT/Image" "$BOOT/dtb" "$BOOT/dtbo.img" "$TEMP/"
ZIP="$DIST/$STEM.zip"
[[ ! -e $ZIP ]] || die "Output already exists: $ZIP. Use a new build timestamp."
(cd "$TEMP" && zip -q -r9 "$ZIP" .)
unzip -tq "$ZIP"
cp "$OUT/.config" "$DIST/$STEM.config"
{
    printf 'release=%s\nvariant=%s\nselinux=%s\nkernelsu=%s\n' \
        "$KERNEL_RELEASE" "$VARIANT" "$SELINUX" "$WITH_KSU"
    printf 'kernelsu_version=BakaSU-v4.2.0-rc3-d7260ca1 (35229; su/permsu only)\n'
    printf 'scheduler_core=%s\nscheduler_policy=%s\nmglru_default=%s\n' \
        "$SCHED_CORE" "$SCHED_POLICY" "${MGLRU:-1}"
    printf 'compiler=%s\nanykernel_commit=%s\n' "$CLANG_VERSION" "$AK3_COMMIT"
    printf 'source_commit=%s\n' "$(git rev-parse HEAD)"
    if [[ -n $(git status --porcelain --untracked-files=normal) ]]; then
        printf 'source_dirty=yes\n'
    else
        printf 'source_dirty=no\n'
    fi
    printf 'epoch=%s\n' "$BUILD_EPOCH"
} > "$DIST/$STEM.txt"
(cd "$DIST" && sha256sum "$STEM.zip" > "$STEM.zip.sha256")
cleanup; TEMP=''
info "Build completed in $((SECONDS - START)) seconds: $ZIP"

read_credential() {
    python3 - "$1" "$2" <<'PY'
import pathlib, sys
s = pathlib.Path(sys.argv[1]).read_text().strip()
key = sys.argv[2]
if s.startswith(key + '='):
    s = s[len(key) + 1:].strip()
if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
    s = s[1:-1]
if any(c.isspace() for c in s):
    raise SystemExit('Credential must contain one value without whitespace.')
print(s, end='')
PY
}

if [[ ${TELEGRAM:-1} == 1 ]]; then
    TOKEN=$(read_credential "$ROOT/token.txt" TOKEN)
    CHAT_ID=$(read_credential "$ROOT/chat_id.txt" CHAT_ID)
    if [[ -z $TOKEN || -z $CHAT_ID ]]; then
        info 'Telegram skipped: token.txt or chat_id.txt is empty.'
    else
        [[ $TOKEN =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || die 'Invalid token.txt format (ZIP preserved).'
        [[ $CHAT_ID =~ ^(-?[0-9]+|@[A-Za-z0-9_]+)$ ]] || die 'Invalid chat_id.txt format (ZIP preserved).'
        TEMP=$(mktemp -d "$CACHE/telegram.XXXXXX")
        info 'Uploading the ZIP to Telegram'
        # URL via stdin keeps the token out of process arguments and logs.
        # No automatic POST retries: avoid duplicate documents on timeouts.
        if ! printf 'url = "https://api.telegram.org/bot%s/sendDocument"\n' "$TOKEN" | \
            curl --config - --silent --show-error --fail --connect-timeout 20 \
                --max-time 600 --form-string "chat_id=$CHAT_ID" \
                --form "document=@$ZIP" --form-string 'caption=' \
                --output "$TEMP/response.json" 2>"$TEMP/curl-error.txt"; then
            die 'Telegram upload failed. The ZIP is preserved in dist/.'
        fi
        python3 - "$TEMP/response.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    response = json.load(f)
if response.get('ok') is not True:
    raise SystemExit('Telegram rejected the upload. ZIP preserved in dist/.')
print('Telegram upload completed.')
PY
        unset TOKEN CHAT_ID
        cleanup; TEMP=''
    fi
fi
