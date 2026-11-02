# Mushroom batch 3 — scoped UI hints and bounded bandwidth

Requires batch 2. `python3 apply.py --check`, `python3 apply.py`, then
`bash build.sh su`. `--restore` restores the source to batch 2 without
overwriting subsequent edits. GPU and KCAL are unchanged. No commit/push.

## Evidence from Mushroom-UI-20261101-165659.txt

- CPU7 was online and non-isolated. Across the sampled CPU counters its busy
  fraction was about 5.1%, compared with roughly 63–73% on the little CPUs.
  This disproves a completely unused/offline prime core in that window.
- Several SF threads, including RenderEngine, had allowed CPUs 0–2 and lived
  in system-background. SystemUI RenderThread was in foreground, allowed
  0–2,4–7. Many UI threads were in the SchedTune root, so top-app's boost 30
  was not automatically their effective SchedTune group configuration.
- The recorded WALT group thresholds were 100/85, and all policies' schedutil
  up/down rate limits were 0. Those differ from the prior source defaults:
  userspace applied its own settings. The capture predates the user's boost80
  experiment; it cannot measure that experiment's speed or energy change.
- zram0 had 4GiB swap capacity, LZ4, about 98MiB swapped data occupying about
  20MiB physical storage. MemAvailable was about 1.63GiB; memory PSI full avg10
  was zero. Low swap occupancy is not an OOM defect or a reason to fill swap.

## Kernel behavior

`CONFIG_MUSHROOM_UI` caches the existing cpuset classification when a group
comes online. SchedTune then considers a moderate additional hint for tasks
already in top-app/foreground: defaults 20/10, temporary action hints 35/15.
No task is moved, and no affinity mask is bypassed. Tasks with a negative
explicit SchedTune boost retain that choice. Existing larger positive SchedTune
boosts remain effective; the new policy does not secretly cap a user boost80.
There is no change to task_struct layout and no process-name scan per tick.

The transition into the existing top-app cpuset requests an action pulse.
Physical KEY_BACK/KEY_HOME/KEY_APPSELECT presses can also request it. Repeated
events are coalesced: default 120ms duration, at least 300ms between accepted
requests. Neither a generic fork nor every touch is treated as app launch.
The hot path only queues work; bus operations run on an ordered workqueue.

`/sys/kernel/mushroom_ui/action` accepts `launch`, `back`, `recents`, or `shade`
from an authorized writer. Gesture back/recents and shade opening do not have
a universal semantic kernel input event. Those cases need a ROM-side write
to this interface for explicit action recognition. The kernel does not claim
to detect notification shade semantics from arbitrary touch coordinates.

The pulse uses an independent active-only MSM bus client, released after its
timer. Default bandwidth vote uses the existing 681 entry and the same
4-byte conversion as Samsung's input booster. This is not a newly added
650MHz physical DDR OPP or a guaranteed physical memory clock. Firmware and
other clients still arbitrate the hardware. The source already has DDR votes
from 200 through 2736; the reported FKM 451 is not proof of a whole-DDR ceiling.

The old Samsung touch/multitouch profiles in all eleven r8q EUR overlays are
reduced from 200ms heads and 300/800ms tails to 80/40ms. Generic touch DDR is
451/0 instead of 1017/1017, and its global HMP request is disabled. CPU touch
resource values remain. This removes long generic holds while reserving a
stronger, short vote for recognized transitions/actions.

Controls under `/sys/kernel/mushroom_ui/`:

| Node | Default | Range/meaning |
| --- | --- | --- |
| enabled | 1 | 0 disables hints and releases this driver's vote |
| top_app_boost / foreground_boost | 20 / 10 | 0..40 |
| action_top_app_boost / action_foreground_boost | 35 / 15 | 0..40 |
| boost_ms | 120 | 20..200 |
| cooldown_ms | 300 | 250..2000; always longer than max pulse |
| ddr_vote_mhz | 681 | 0,451,547,681; legacy bandwidth-equivalent units |
| stats | read-only | accepted requests, active lease, bus availability/return |
| action | write-only | launch/back/recents/shade |

## Boot companion profile

Because this ROM overwrites kernel defaults, a small optional KernelSU module
is generated from `mushroom/policy/` by `mushroom/package-policy.py`. SU ZIPs
contain `Mushroom-Policy-KSU.zip` as an extra file; AnyKernel does not install
the module automatically. Install it separately through KernelSU Manager.
It has no system mount or sepolicy modifications. Its service waits for boot
and runs one pass, then exits; it does not keep polling or fight the Power HAL.

The pass sets background and system-background cpusets to **0–3**, preserving
foreground and top-app masks and every thread's group assignment. It clears
root SchedTune boost/prefer_idle to 0, applies top-app 20/idle1 and foreground
10/idle1, keeps background at 0, selects schedutil and sets up/down rates to
500/8000us. Disable an FKM saved global80/performance profile for comparison.
Later userspace writes can still override those one-time values.

Memory defaults/profile use swappiness120 and page-cluster0 for zRAM. They do
not force active pages into swap, inflate RAM readings, change application
oom_score_adj, disable OOM/LMKD, or guarantee fewer application kills. The
profile keeps oom_kill_allocating_task=0 so kernel OOM chooses its normal
badness-based victim; Android lmkd remains a separate userspace policy.

The module records before/after values in its private state.tsv. Its uninstall
script restores matching values and preserves later manual edits. The profile
log records failed writes rather than assuming they succeeded. Removing the
module stops future boot writes; restoring batch2 source and rebuilding also
removes the new kernel policy itself.

The companion format uses KernelSU's documented module.prop/service.sh layout:
https://kernelsu.org/guide/module.html

## Validation limits

Compile/link, patch apply/restore, sysfs bounds/lease state logic, overlay
edits, profile fixture/restore and final packaging are host-verifiable.
Actual UI latency, energy use, physical DDR clocks and firmware acceptance
need a phone comparison. `collect-ui.sh` now includes VM, root SchedTune,
Mushroom statistics, devfreq frequency tables and governor settings.
