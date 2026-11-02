# Mushroom scheduler 5.4 port — batch 7

Experimental source port for the working Mushroom v6 r8q / Linux 4.19.260
configuration. This is a scheduler subsystem replacement; the rest of the
kernel and its reported Linux version remain 4.19.260. Boot, frame pacing,
power and sustained performance on the phone still require device testing.
A newer scheduler alone does not guarantee a performance gain.

## Source and scope

Donor: [LineageOS/android_kernel_qcom_sm8350](https://github.com/LineageOS/android_kernel_qcom_sm8350/tree/66d56f9b5a0f3c53807b332cfdc39a722f9633e4),
Linux **5.4.302**, pinned commit
`66d56f9b5a0f3c53807b332cfdc39a722f9633e4` (lineage-20).

Qualcomm 5.4 was chosen for its WALT, heterogeneous CPU placement and mobile
schedutil integration. The SM8350 platform drivers, device trees and clock
limits are NOT imported into SM8250.

`kernel/sched54/` contains the complete donor scheduler directory: the core,
CFS, RT, deadline, idle and stop classes, topology/EAS, PELT, WALT, schedutil,
CPU accounting, load average, PSI, wait queues, completions and isolation.
The original `kernel/sched/` is retained as a separately selectable fallback.
The imported code retains its upstream licenses and copyright notices.

## Apply and build

Run `python3 apply.py --check` and then `python3 apply.py` in the exact exported
v6 source. The embedded source payload needs no network. It checks context,
uses build.sh's lock, backs up changed files and does not stage or commit.

Select the new scheduler explicitly:

```sh
SCHED_CORE=5.4 SCHED_POLICY=uclamp bash build.sh su
```

The existing `su`, `stock`, `permsu` and `perm` modes remain available.
`SCHED_CORE=legacy` remains the default; the 5.4 core requires `uclamp`.
Switching selections reconfigures and rebuilds the same variant directory.
To rebuild the tested v6 scheduler after applying this source batch:

```sh
SCHED_CORE=legacy SCHED_POLICY=uclamp bash build.sh su
```

After booting the new build, check the compiled core without a collector:

```sh
su -c 'cat /proc/sys/kernel/mushroom_scheduler'
```

Expected: `qcom-5.4.302-port-v7`; legacy reports `legacy-4.19-mushroom-v6`.
The existing ZIP name, AnyKernel installer and Telegram upload are retained.
A build timestamp is not proof that the 5.4 scheduler was selected; use this
read-only identity node.

## Integration with the 4.19 kernel

The public task definition keeps the 4.19 signal, timer, memory and task
lifetime interfaces while importing the 5.4 scheduling entities and WALT
state. Fork repairs the child affinity pointer; cpuset, Binder and procfs
access the active WALT fields. Per-task window storage is freed once after
the final switch; failed forks keep the existing cleanup path.

Workqueue sleep/wake accounting follows the real 4.19 locked callback
contract. The new local wake helper updates WALT without recursively locking
the runqueue. RCU deferred wakeups iterate all 4.19 RCU flavours. Tickless
accounting follows the donor PELT/WALT design rather than the removed 4.19
CPU load-history arrays. The 32-bit scheduling syscall keeps the 4.19 ABI.

The optional donor input-boost mechanism uses the real 4.19 CPUFREQ_ADJUST
notifier instead of unavailable frequency-QoS requests. Related-policy votes
are aggregated and thermal maxima are preserved; its input frequency defaults
remain zero. Trace hooks use native 4.19 tracepoints, not GKI vendor-module
hook registration. The Samsung LMKD PSI peak monitor and display refresh
callback retain their working 4.19 behaviour.

Scheduler sysctls come from the donor when selected. Obsolete WALT sysctls
are not aliases to differently shaped data. The native Mushroom UCLAMP
controls remain available. Existing kernel modules that depend on internal
task/runqueue layout must be rebuilt against this configuration.

## Initial response settings and preserved features

The initial comparison keeps the v6 CFS values: 6 ms latency, 750 us minimum
granularity, 500 us wakeup granularity, 300 us migration cost and no scaling
by CPU count. Schedutil uses 500 us upward and 20 ms downward limits, hispeed
load 85, and RTG floors 1 GHz / 1478.4 MHz / 1574.4 MHz by CPU cluster.
WALT initial task load is 25%, group migration thresholds 65/50. Native
UCLAMP floors remain 20% top-app and 10% foreground; explicit task requests
and maximum clamps take precedence. WALT adjustments are followed by a clamp
for each CPU in a shared policy; rejected frequency updates invalidate the
raw-frequency cache. Latency-sensitive tasks may look beyond a previous
idle little CPU when a higher-capacity CPU is available.

GPU policy, voltage/OPP tables, DDR ceiling, KCAL, MGLRU, ZRAM, background
cpuset policy, KernelSU, F2FS userdata, EXT4 and the SELinux boot fix are
preserved. This batch introduces no CPU/GPU voltage or clock overclock.

## Host validation

`python3 mushroom/tests/scheduler54_test.py` compiles extracted production
functions with GCC and undefined-behaviour instrumentation. It exercises
UCLAMP floors/caps, shared-policy frequency selection, rate-limit cache
invalidation, input-boost policy bounds and all-flavour RCU wakeups. Additional
source-boundary assertions check fork ownership and local wake lock ordering.
These checks do not emulate the phone, execute context switches or establish
an FPS/power improvement. Full Image and ZIP compilation are checked separately.

## Source rollback

`python3 apply.py --restore --check` validates the batch backup.
`python3 apply.py --restore` restores only this batch, refusing to overwrite
files edited after application. It does not flash the phone. Keep a working
v6 ZIP available for a device rollback. No commit or push is performed.
