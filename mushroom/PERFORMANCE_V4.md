# Batch 4: MGLRU, Proton and EXT4 / r8q

## Build and rollout

Apply this delta to the working batch-3 tree with `python3 apply.py --check`,
then `python3 apply.py`. Run `bash build.sh su`. `--restore` restores this
batch's snapshot only, refusing to overwrite later source edits. No Git
staging/commit/push or credential reads occur in apply.py.

The default continues to expose `/dev/stune` for this ROM and preserves batch
3's bounded UI policy. `SCHED_POLICY=uclamp bash build.sh su` instead enables
`CONFIG_UCLAMP_TASK` and `CONFIG_UCLAMP_TASK_GROUP`, disables SchedTune and its
Mushroom UI boost driver, and retains the independent kernel cpuset rule.
Use that opt-in only with ROM task profiles and a power HAL supporting the CPU
controller's uclamp interface. Android 13 alone does not identify which
controller a particular ROM uses. UCLAMP does not replace cpusets. Existing
schedutil frequency aggregation and EAS use the branch's real clamp support;
the formerly unguarded schedtune task-margin call now has an UCLAMP path.

## Multi-gen LRU

This is a real page-based 4.19 backport of Yu Zhao's 2022 MGLRU series,
including the swap-shadow and LRU-accounting prerequisites, page-table walks,
rmap locality, memcg iteration, speculative-fault integration, Qualcomm
reclaim fixes, sysfs kill switch and debugfs interface. Upstream attribution
and exact imported revisions are in `MGLRU-PROVENANCE.md`.

`CONFIG_LRU_GEN=y`, `CONFIG_LRU_GEN_ENABLED=y`, historical stats off.
For an A/B build starting with classic LRU use `MGLRU=0 bash build.sh su`.
The same MGLRU code and runtime switch remain available. The older
active/inactive LRU is also available at runtime:

```sh
su -c 'cat /sys/kernel/mm/lru_gen/enabled'
su -c 'echo 0 > /sys/kernel/mm/lru_gen/enabled'  # fallback to classic LRU
su -c 'echo y > /sys/kernel/mm/lru_gen/enabled'  # restore MGLRU
```

Supported capability bits depend on hardware. On ARM64, unsupported x86
non-leaf PMD tracking is not advertised. `min_ttl_ms` remains 0; imposing a
large protection window can cause premature OOM. VM swappiness stays 120,
page-cluster 0 and the real 4 GiB zRAM setup is preserved. No OOM kill disable,
forced swap occupancy, journaling disable or thermal bypass is introduced.

Compilation/linking and host-side invariant checks cannot validate device
boot, reclaim stability under memory pressure, suspend or module ABI on r8q.
Keep the known booting ZIP available. Test MGLRU under app switching, swapping,
suspend/resume and sustained load before treating this as a stable release.

## Background cpusets

`CONFIG_MUSHROOM_BG_CPUSET` normalizes each valid non-empty CPU-mask write to
root `background` and `system-background` groups on the legacy hierarchy to
CPUs 0-3, intersected with present CPUs and the parent's requested mask.
Normal cpuset validation, CPU hotplug and empty-group teardown remain in
force. V2 hierarchies, nested groups and all foreground/top-app masks retain
their normal behavior. There is no task migration between cgroups, task-name
heuristic or new per-process affinity rule. The optional root companion is
no longer necessary for these two masks.

## EXT4

The build explicitly targets EXT4, with ACLs, SELinux labels, Android fscrypt,
quotas, JBD2 and metadata checksums retained. ARMv8 CRC32/CRC32C acceleration
is built in, selected at runtime only on CPUs with the instruction support.
EXT4/JBD2 debug stay off. F2FS is also built in, including encryption, ACLs
and security labels: the boot log confirms this device uses F2FS for /data
even though system/vendor are EXT4. The build asserts F2FS and encryption
support to prevent shipping a kernel unable to mount userdata.
EROFS/squashfs/recovery support is not arbitrarily removed. Mount options,
barriers, fsync, journaling, encryption and disk format are not changed.
This is configuration specialization, not a claim of measured I/O speedup.

## Names and installer

ZIP: `MushroomKernel-KSU-r8q-<hex>.zip`, with analogous Stock/Permissive labels.
Release: `4.19.260:MushroomKernel/<hex>`. Build user/host stay Mushroom@ServerHive.
Installer UI:

```text
Mushroom Kernel by Nihil@donottellmyname
AnyKernel3 by osm0sis @ xda-developers

Checking device...
...
Installing...
<resolved boot partition>
<resolved dtbo partition>

Done!
```

The script applies exact UI-only replacements to the pinned original AK3;
its partition writers, error checks and recovery output protocol stay intact.

## DDR / GPU

GPU tables are unchanged in this batch. No physical DDR overclock is claimed.
Kona already defines DDR bandwidth OPPs for 200, 451, 547, 681, 768, 1017,
1353, 1555, 1804, 2092 and LPDDR5-only 2736 MHz equivalents, converted to
MiB/s for devfreq. These votes are not direct DDR PLL programming. FKM's
50..451 display cannot identify its source node or conversion formula.
A possible width/unit conversion would map 200..1804 to 50..451, but that is
only an inference until raw devfreq values are captured. Raising an app's
number or inventing an OPP cannot prove physical 650 MHz or firmware support.
The updated read-only collector records node paths, units/raw tables, limits,
OF identity, MGLRU state, mounts and uclamp controls for diagnosis.

## Compiler diagnostic fixed

Proton diagnosed a pre-existing CNSS2 sysfs stack overflow: a two-byte
`antbuffer` received two characters, a newline and NUL. The handler now
formats directly into its PAGE_SIZE sysfs output buffer with `scnprintf`,
retaining the output and eliminating the undersized temporary array.

## Boot fix: F2FS userdata

The submitted failed boot identifies release MushroomKernel/6ae7ab8b and
reports at 6.491097 seconds:

```text
__mount(source=/dev/block/bootdevice/by-name/userdata,target=/data,type=f2fs)=-1: No such device
```

The preceding successful boot used F2FS mount options on /data. The fsck.f2fs
checks in the failed boot pass, but the kernel lacks CONFIG_F2FS_FS. Android
then cannot create /data directories or open keystore databases, which explains
the repeated service crashes and incomplete boot. This fix restores built-in
F2FS and its original encryption/security support, with build assertions.
It leaves MGLRU, Proton, cpusets, EXT4 and disk contents unchanged. No format,
filesystem conversion, cache wipe or SELinux change is needed for this fix.
Device boot must be verified after flashing the rebuilt ZIP.
