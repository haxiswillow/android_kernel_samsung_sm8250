# Scheduler 5.4 topology integration — v7.2

Apply after the booting v7.1 source. This batch connects WALT topology setup
to the existing 4.19 CPU-frequency capacity initialization. It retains the
v7.1 kthread fix and the current scheduler/governor tuning.

## Diagnosis

The screenshots show schedutil selected with all policies at maximum, plus
EINVAL reading sched_upmigrate/downmigrate and EPERM reading group thresholds.
Both handlers reject reads when num_sched_clusters is zero. In the recovered
v7.1 source, walt_update_cluster_topology() has a definition but no caller.
The donor calls it after all policies have supplied their capacities, in
drivers/base/arch_topology.c; that external integration was missing.

Consequently the fallback cluster covers all CPUs, max_possible_freq remains
1 instead of kHz, and cpu_array/core_ctl initialization does not run. With
hardware cycle counters, execution scaling divides real cycles by that dummy
maximum; the demand and frequency decisions can saturate. This is a concrete
integration defect consistent with the screenshots. Runtime cpufreq minima
and userspace profiles can also constrain clocks independently.

## Correction

After the existing CPUFREQ_NOTIFY callback has visited every possible CPU and
normalized capacities, call walt_update_cluster_topology() for the 5.4 core.
This follows the pinned donor's ordering; 4.19 uses CPUFREQ_NOTIFY where the
5.4 donor uses CPUFREQ_CREATE_POLICY. The callback already handles late policy
registration without polling, sleeps or an initcall that could run too early.
The call is gated by CONFIG_MUSHROOM_SCHED54; legacy behavior is unchanged.
The donor topology builds the little/big/prime clusters, publishes cpu_array,
updates thresholds and queues core_ctl/input initialization. Initialize each
new cluster's current frequency from its ready cpufreq policy as well.

Donor: LineageOS/android_kernel_qcom_sm8350,
66d56f9b5a0f3c53807b332cfdc39a722f9633e4, drivers/base/arch_topology.c.

## Names and controls

uname release becomes 4.19.260:Mushroom/<hex timestamp>. ZIPs remain
MushroomKernel-KSU-r8q-<hex timestamp>. The installer branding is unchanged.

/proc/sys/kernel/mushroom_scheduler reports qcom-5.4.302-port-v7.2.
/proc/sys/kernel/mushroom_walt_clusters is a read-only diagnostic of the real
initialized cluster count; r8q should report 3. No synthetic success value or
replacement migration handler hides an initialization failure.

sched_util_clamp_min=1024 is the system ceiling on requested UCLAMP_MIN,
not a global 100% floor. It remains unchanged. The number of scheduler
controls reflects the imported Qualcomm WALT code. CFS values may still be
set by the ROM; this batch does not fight those writes. No I/O scheduler or
thermal configuration changes are included.

## Apply and verify

```sh
python3 apply.py --check && python3 apply.py &&
SCHED_CORE=5.4 SCHED_POLICY=uclamp bash build.sh su
```

After flashing and booting:

```sh
su -c 'cat /proc/sys/kernel/mushroom_scheduler; cat /proc/sys/kernel/mushroom_walt_clusters'
```

Expected identity v7.2 and count 3. The existing up/down migration controls
should now read normally. The exact runtime clock behavior and sustained
performance need device testing. No maximum frequency is lowered by this fix.

Host regression: python3 mushroom/tests/walt_topology_test.py. It compiles
actual production initialization callbacks with mocked policy arrivals and
checks ordering, exactly-once construction, valid per-policy frequencies,
scalar/vector handler reads, and kernel/ZIP naming independently.
The source applier retains strict context checks, a separate backup,
build lock, idempotence and guarded restore. No commit or push is performed.
