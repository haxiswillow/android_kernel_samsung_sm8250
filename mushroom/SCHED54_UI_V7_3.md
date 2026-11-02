# WALT UI placement preference — v7.3

Apply after the working v7.2 source. This adds an optional UI placement policy;
it does not restore the missing-topology state of v7.1 or lock CPU clocks.

## Behavior being adjusted

Once v7.2 initializes the real three clusters, WALT can select a fitting idle
Big CPU and stop before reaching Prime. The existing native UCLAMP floors
make foreground/top-app tasks latency-sensitive, but the WALT cluster order
does not by itself apply the highest-capacity idle preference found in the
non-WALT UCLAMP placement path. Thus a lower Prime utilization is not proof
of a broken or disabled CPU, and utilization percentages alone do not measure
frame pacing. This policy targets the user's preferred UI response.

For a latency-sensitive task with a positive effective UCLAMP_MIN, the new
hint examines an available idle Prime before the middle cluster. Prime must
be inside the task's allowed mask, active, not isolated/reserved, and not
marked for high IRQ load. Its available capacity, limited by thermal_cap,
must exceed the middle cluster. A UCLAMP_MAX at or below middle capacity
suppresses this extra hint. A distinct highest cluster of one CPU is required.

The native WALT target selector still checks fit and load. If Prime becomes
busy after the hint, end_index=1 lets it examine the middle cluster before
accepting a busy target. Existing per-task max/strict-max and full-throttle boost
paths retain priority over this hint. Busy/unavailable Prime and ordinary
background tasks keep native selection. No task's affinity is changed.

Default is enabled through /proc/sys/kernel/mushroom_ui_prime (0 or 1).
Zero restores the v7.2 cluster-order behavior immediately, allowing a direct
comparison without reflashing. This preference can use more power by waking
Prime for UI bursts; all cpufreq limits, governors, thermal caps and idle
behavior remain in force. It does not guarantee a particular CPU percentage
or an FPS improvement. The result needs a device comparison.

## Core control and CAF CPU Boost

v7.2 correctly queues both core_ctl_init and cpu_boost_init. That makes the
CAF CPU Boost interface visible. Its appearance does not show that boost is
active. In the source, input boost frequencies and sched_boost_on_input default
to zero; the ROM or a manager can configure them after boot. This batch does
not change those values or introduce a touch-frequency floor.

Core_ctl defaults to at least one active CPU per cluster, so the one-CPU
Prime cluster is not disabled by the source default. If userspace later
changes isolation/affinity, the placement hint respects those constraints.

## Apply and compare

```sh
python3 apply.py --check && python3 apply.py &&
SCHED_CORE=5.4 SCHED_POLICY=uclamp bash build.sh su
```

Expected identity: qcom-5.4.302-port-v7.3. Cluster count should remain 3.

```sh
su -c 'cat /proc/sys/kernel/mushroom_scheduler; cat /proc/sys/kernel/mushroom_ui_prime'
# Compare native v7.2 placement:
su -c 'echo 0 > /proc/sys/kernel/mushroom_ui_prime'
# Restore the new preference:
su -c 'echo 1 > /proc/sys/kernel/mushroom_ui_prime'
```

Host regression: python3 mushroom/tests/walt_ui_prime_test.py. Tests compile
the actual hint and WALT index selection with controlled CPU states. They
cover idle/busy Prime, affinity, isolation, thermal/capacity reduction, IRQ
load, reservations, task clamps, boot readiness and explicit boost priority.
They are not a phone frame-pacing or context-switch test.

The source applier keeps a separate guarded backup and build lock, and does
not stage, commit or push. GPU, DDR, I/O, uname/ZIP branding, the v7.1 boot fix
and v7.2 topology initialization are retained.
