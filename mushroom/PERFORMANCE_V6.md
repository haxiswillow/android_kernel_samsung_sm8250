# Mushroom performance batch 6

Apply to the working batch 5 source, including the F2FS userdata boot fix.
`python3 apply.py --check` performs preflight; `python3 apply.py` applies it.
`python3 apply.py --restore` restores this batch's source snapshot only, and
refuses to overwrite files edited afterward. No commit/push is performed.

## GPU

The default kernel-owned mode uses measured busy/total time, a 75% occupancy
target, immediate upward response and a 30 ms low-load window before stepping
down by one native OPP. It handles low-busy samples too. No fixed maximum
frequency or new voltage is introduced. The previous TZ decision path remains
available by disabling `/sys/module/devfreq/parameters/mushroom_gpu_native`.
The governor name stays `msm-adreno-tz` for existing driver integration.

While kernel-owned mode is active, legacy user min/max/default power-level
writes, devfreq min/max restrictions and governor changes are rejected with
EBUSY. This is deliberate: a ROM/FKM per-app profile cannot silently replace
the kernel's ordinary user limits. Discretionary POPP clock suppression and
POPP-adjusted busy counters are bypassed in this mode.

Explicit manual bounds are available at:

- `/sys/class/kgsl/kgsl-3d0/mushroom_gpu_min_hz`
- `/sys/class/kgsl/kgsl-3d0/mushroom_gpu_max_hz`

Write a supported frequency in Hz; zero releases that bound. Defaults retain
the full native range, e.g. 305–740 MHz on the patched supported GPU bin.
These controls use the device mutex and reject crossed bounds or unsupported
frequencies. Legacy FKM sliders are intentionally not the manual interface
while kernel-owned mode is active.

The cooling framework, GMU, regulator/OPP masks, thermal power-level minimum
and maximum, and the existing thermal sysfs clients retain authority.
`max_gpuclk`, `max_clock_mhz` and `thermal_pwrlevel` are thermal-limit interfaces
in this KGSL tree and remain functional. A ROM writing a thermal interface
cannot safely be distinguished from actual thermal mitigation from the
current evidence. This patch therefore does not claim that every possible
400 MHz limit in a game has been identified or eliminated.

740 MHz still uses the earlier RPMh TURBO corner, not an arbitrary voltage.
`gpuclk` can report a cached frequency while the GPU is power gated.

## DDR bandwidth ceiling

`/sys/module/devfreq/parameters/mushroom_ddr_native` defaults to Y. The primary
CPU-to-DDR bandwidth client's highest existing supported OPP is used as its
user ceiling, and lower legacy maximum requests are rejected. Only recognized
native tables ending at 7980 or 10437 MiB/s activate this policy; other devices
and tables are untouched. Runtime OPP/scaling thermal maxima still take priority.
The floor is unchanged and the bandwidth governor can scale down when idle.

For the supplied FKM version, `round(10437 * 0.065536) = 684 MHz`. The user's
phone screenshot confirms this requested ceiling is available. It is a
bandwidth-vote conversion, not a measured physical DRAM PLL clock. This batch
does not program a physical DDR overclock.

## UCLAMP, WALT and schedutil

UCLAMP becomes build.sh's default scheduling policy. An explicit
`SCHED_POLICY=stune` override is retained. The existing build selector enables
UCLAMP_TASK and UCLAMP_TASK_GROUP and disables SCHED_TUNE/MUSHROOM_UI for the
UCLAMP variant, as those implementations were mutually exclusive.

The source already contains UCLAMP and UTIL_EST_FASTUP backports; this batch
integrates and enables them rather than replacing the entire Qualcomm
scheduler with a Linux 5.x scheduler.

- Fix the !STUNE WALT schedutil path: directly call cpu_util_freq with the
  WALT output structure. The old stune_util macro discarded that structure
  and substituted CFS utilization, leaving WALT load metadata unset.
- Apply UCLAMP after WALT adjustments for both single and shared policies.
  Clamp each CPU before aggregating a shared policy; skip uninitialized zero
  CPU capacities to avoid an invalid shared-policy denominator.
- Account for UCLAMP in the WALT energy model's frequency estimate; retain
  actual busy utilization for energy's busy-time term. Use WALT utilization
  for the fallback CPU-candidate path, too.
- Add native per-cpuset runnable-task floors: top-app 20%, foreground 10%,
  all other groups zero. Nested app cpusets inherit their parent class.
  Classification happens once at cgroup creation, avoiding hot-path name
  lookup. Existing CPU affinity/cpuset masks and thermal placement checks stay
  authoritative. A 0% reading on CPU7 alone does not prove a scheduler fault.
- The floor is incorporated into effective UCLAMP on enqueue, with a correct
  bucket index. Explicit per-task minimum requests are respected. Floors
  never exceed the task/group or global maximum clamp. No global 80% floor.
- Foreground/top-app floors also supply the latency-sensitive placement hint.
  Tasks do not migrate into different Android groups because of this feature.

Root can tune percentages (0–100) at:
`/proc/sys/kernel/mushroom_uclamp_top_app` and
`/proc/sys/kernel/mushroom_uclamp_foreground`.
Updates take effect on subsequent task enqueues. Idle CPUs have no runnable
task floor. In a ROM built around STune, native cpuset hints provide defaults
without requiring a new ROM cpu-controller task profile.

Background and system-background CPU masks remain the independent batch 4
0–3 policy. No attempt is made to put every game thread on the Prime CPU.

## Memory and helper

MGLRU and the F2FS/EXT4 drivers are unchanged. The previous phone report showed
MGLRU enabled as 0x0003. This batch does not use extra swappiness or disable OOM
to conceal CPU/GPU limitations.

The phone helper now skips an already-active DDR ceiling, checks readback if a
write reports an error, and treats unavailable tracing as optional. A new
`--status` option prints status immediately without collecting a report.
The observed printf EINVAL was not sufficient to identify its failing sysfs
node; the earlier script did not print the path for each failure.

The optional KernelSU companion is updated to v6 and works with either STune
or UCLAMP. GPU ownership, DDR ceiling and native UCLAMP floors are implemented
in the kernel and do not require that companion.

## Validation and limits

The edited devfreq/KGSL, schedutil, scheduler core/fair, cpuset and sysctl
translation units are compiled with Proton Clang 13.0.0 for ARM64 with WALT,
UCLAMP_TASK and UCLAMP_TASK_GROUP. The compatibility STune configuration is
also compiled. Unit harnesses execute the actual demand algorithm and native
limit helpers, check downscale timing/overflow and verify that KGSL thermal
caps still bound requests. The installer is tested for preflight, idempotence,
context rejection, lock handling and guarded restore; scripts are syntax and
ShellCheck checked. No new full Image or phone boot/FPS validation is claimed.

References:

- https://www.kernel.org/doc/html/v5.19/scheduler/schedutil.html
- https://www.kernel.org/doc/html/latest/scheduler/sched-util-clamp.html
- Existing Qualcomm WALT/KGSL and devfreq implementations in this source tree.
