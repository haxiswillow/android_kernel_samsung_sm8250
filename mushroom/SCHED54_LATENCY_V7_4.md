# Schedutil, UFS latency and memory review — v7.4

Apply after the working v7.3 source. Keep the phone-tested UI Prime hint enabled.
Build with `SCHED_CORE=5.4 SCHED_POLICY=uclamp bash build.sh su`.
The complete kernel is still Linux 4.19.260; this is an incremental integration
update, not a complete Linux 5.10 scheduler/governor replacement.

## Which schedutil is actually linked

`kernel/Makefile` selects `kernel/sched54/` with CONFIG_MUSHROOM_SCHED54.
That directory's Makefile already links its own Qualcomm 5.4 schedutil,
imported with the scheduler in v7, from LineageOS/android_kernel_qcom_sm8350
commit `66d56f9b5a0f3c53807b332cfdc39a722f9633e4` (Linux 5.4.302).
The legacy `kernel/sched/cpufreq_schedutil.c` is used only by SCHED_CORE=legacy.
Replacing the WALT-aware governor with mainline 5.10 wholesale would discard
its WALT/RTG/PL integration; a newer version number alone does not improve it.

This batch adapts the forced-update lifetime from Linux v5.10.250 schedutil
and fixes the interactions with the donor's directional rate limits:

- `need_freq_update` survives raw-frequency resolution and is consumed only
  when a target is committed. New limits and DL reservations bypass both
  directional delays, even if the resolved target equals the cached target.
  This 4.19 CPUFreq core lacks CPUFREQ_NEED_UPDATE_LIMITS, so one forced driver
  update is allowed, without importing a fictitious driver flag.
- The fast-switch limits callback forces its clamped target immediately.
  Slow switching continues through cpufreq_policy_apply_limits. Native
  policy bounds, firmware limits and thermal restrictions remain authoritative.
- Shared-policy DL bandwidth is compared before sugov_get_util overwrites
  the old bandwidth. A CONTINUE aggregation sample no longer consumes a
  pending limits change before the committing sample can process it.
- Saved rate limits are restored in nanoseconds, fixing the donor's missing
  microsecond conversion. An explicit saved hispeed frequency also survives
  governor recreation instead of being overwritten by the default RTG value.
- New policy defaults: upward rate limit 250 us, downward rate limit 8000 us
  (previously 500 / 20000). These limit how often a request can be issued;
  they are not a promise that measured load, hardware clocks or a frame will
  respond in 250 us. The optional one-pass KSU companion uses the same values.

WALT load estimation, I/O-wait boost, hispeed/RTG logic, shared-policy capacity
aggregation and per-runqueue UCLAMP caps remain in place. No permanent maximum
clock, extra input floor, global clamp or new RTG floor is introduced.
Native UI Prime placement, topology initialization and the kthread boot fix
remain byte-for-byte unchanged. The CPU task scheduler policy is not replaced
again after the user's successful v7.3 phone test.

Read `/sys/devices/system/cpu/cpufreq/policy*/schedutil/mushroom_version`:
`qcom-5.4.302+limits-5.10-v7.4`. The scheduler marker becomes
`qcom-5.4.302-port-v7.4`. The uname remains `4.19.260:Mushroom/<hex>`;
ZIP names remain `MushroomKernel-KSU-r8q-<hex>.zip` for su builds.

## UFS I/O

`drivers/scsi/ufs/ufshcd.c:ufshcd_alloc_host` explicitly sets
`host->use_blk_mq = false` for this Samsung runtime-PM implementation.
CONFIG_SCSI_MQ_DEFAULT does not undo that assignment. Consequently the
phone's CFQ queues cannot use mq-deadline/Kyber simply by enabling them.
This batch retains the working UFS runtime-PM/crypto/storage path.

Deadline is now the built-in default for single-queue devices, including all
UFS LUNs sda/sdb/sdc/etc, with read_expire=50 ms, write_expire=500 ms,
fifo_batch=8, writes_starved=2, front_merges=1. These are soft scheduler
dispatch deadlines, not hardware completion guarantees. Smaller batches
allow direction/expiry reconsideration more often; reads are preferred but
write starvation is bounded. The tradeoff can be lower bulk throughput.
CFQ and noop remain selectable for on-device comparison. Existing flush/FUA,
encryption, writeback, queue depth and filesystem integrity are untouched.
Device-mapper/loop/ZRAM virtual devices are not forced into a disk scheduler.
`dm-*` may correctly expose `none` while its UFS backing queue uses Deadline.

These are boot defaults. A ROM init script, kernel manager or an explicit
`elevator=` boot argument can select a different scheduler later; this batch
does not poll or fight those writes. Check the effective queue after boot:

```sh
su -c 'for q in /sys/block/sd*/queue; do echo "$q"; cat "$q/scheduler"; done'
```

If an existing ROM/FKM setting reapplies CFQ, a one-time comparison is:

```sh
su -c 'for q in /sys/block/sd*/queue; do
  [ -w "$q/scheduler" ] || continue
  grep -qw deadline "$q/scheduler" && echo deadline > "$q/scheduler"
done'
```

## Memory integration review

The build had THP enabled for all eligible anonymous mappings. The profile
now chooses CONFIG_TRANSPARENT_HUGEPAGE_MADVISE instead of ALWAYS, retaining
hugepages for applications that request them. This avoids automatic THP
allocation/collapse for ordinary anonymous regions and its potential memory
cost. Explicit MADV_HUGEPAGE regions can still invoke compaction; this does
not claim to eliminate every allocation stall. Existing defrag/shmem controls
are unchanged, and userspace/boot parameters may override the initial mode.

The existing page-based MGLRU stays enabled with its runtime fallback. The
review retains its mm/fork/exec/exit and reclaim integration; no new LRU
implementation is mixed in. ZRAM remains configured through the existing
Android path, swappiness remains 120, page-cluster remains zero when ZRAM is
built in, and OOM/LMKD behavior is not disabled. A low percentage of ZRAM
usage by itself is not a reason to force more reclaim or increase its size.
PSI, MEMCG and swap support remain enabled. EXT4 plus the required built-in
F2FS encrypted userdata support are retained.

## Validation and installation

Host harnesses execute actual governor functions for cache/rate-limit
transitions, immediate caps/floors, forced same targets, shared DL ordering,
CONTINUE batching and saved tunables. They also execute actual Deadline
initialization/dispatch and THP/swap setup with simulated device state.
Existing scheduler/UCLAMP, topology, UI Prime and kthread regressions passed.
The original v7.3 governor fails the new forced-update regression (negative
control). Full Proton Clang Image, DTBs, DTBO and AnyKernel ZIP compilation
passed with the final configuration; ZIP CRCs and embedded version markers
were verified. Protected working source and the Git index remained unchanged.
The applier passed preflight, apply/reapply, guarded restore, edited-context,
local-config preservation and active-build-lock tests. Phone boot, frame
latency, UFS benchmarks and battery measurements are still pending; the host
fixtures and successful compilation do not substitute for those.

`python3 apply.py --check` changes no source. The applier checks every hunk,
backs up only changed files, supports guarded `--restore`, preserves the
Git index, and refuses to run during an active build. Unrelated user config
edits and credentials are preserved; conflicting edited hunks are rejected.
No commit, push or automatic phone flashing occurs.

## Sources

- Pinned Qualcomm 5.4 donor:
  https://github.com/LineageOS/android_kernel_qcom_sm8350/blob/66d56f9b5a0f3c53807b332cfdc39a722f9633e4/kernel/sched/cpufreq_schedutil.c
- Linux v5.10.250 forced-update implementation (adapted to WALT + 4.19 CPUFreq):
  https://github.com/gregkh/linux/blob/v5.10.250/kernel/sched/cpufreq_schedutil.c
- Original limit-change rationale, already partly present in the donor:
  https://github.com/torvalds/linux/commit/600f5badb78c316146d062cfd7af4a2cfb655baa
- Deadline tunables:
  https://www.kernel.org/doc/html/v6.6/block/deadline-iosched.html
- 4.19 THP policy and allocation tradeoffs:
  https://www.kernel.org/doc/html/v4.19/admin-guide/mm/transhuge.html
