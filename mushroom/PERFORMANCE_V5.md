# Batch 5 — GPU demand response, DVFS correctness and DDR interpretation

Requires the working batch-4 tree with its F2FS userdata boot fix. Apply with
`python3 apply.py --check`, `python3 apply.py`, then `bash build.sh su`.
The script creates a scoped backup in `.build/mushroom-perf-v5/`. It does not
stage, commit, push, read credentials or modify a partition. `--restore` refuses
to overwrite later edits and restores only this batch's changed source files.

## Findings from the supplied phone log and FKM APK

The booted release is `4.19.260:MushroomKernel/6ae7af24`. MGLRU reports 0x0003;
4 GiB zRAM is active, using about 1.62 GiB of swap. The snapshot has about
1.20 GiB MemAvailable and memory full PSI avg10=0.00. Those data do not identify
memory starvation as the cause of the reported game/UI behavior.

The GPU snapshot uses msm-adreno-tz with min=305 MHz, max=740 MHz. It records
transitions through every listed level, including 670 and 587 MHz. This does
not show a permanent 400 MHz cap during the whole capture, and it does not
associate a particular transition with Minecraft or Telegram. The old collector
did not capture simultaneous gpubusy, KGSL limits and clock state.

`default_pwrlevel=0` means resume at the highest indexed power level: 740 MHz
in this build. After resume, the governor selects a clock for demand. The FKM
GPU display reads cached devfreq frequency and gpubusy. A high cached clock
with zero load while idle is not evidence that the GPU is physically running
at that clock throughout idle. The ordinary frequency ABI is preserved.

The busmon `cur_freq` value in this log is 18446743804437637008. Its callback
in the base source returns success without assigning *freq. This is a real
uninitialized-output bug in the busmon telemetry. The primary GPU frequency
callback is separate; fixing busmon alone cannot establish that game DVFS is
fixed.

APK SHA-256: b5250885b8205682cb89b952122b61937439d044de4e8d67c0ba7c1890f3cb38

FKM discovery in `com.franco.kernel.utils.health.c` searches cpubw, then
cpu-llcc-ddr-bw. Its DDR monitor (`b3.b`, case 0) calculates:

```
display_MHz = round(raw_MiB_per_second * 0.065536)
display_usage_percent = (current_MHz - min_MHz) * 100 / (max_MHz - min_MHz)
```

That usage percentage is position inside the frequency range, not a hardware
measurement of bus occupancy. This tree's DDR bandwidth table uses a 4-byte
conversion; FKM's fixed coefficient assumes 16 bytes. The resulting display
is approximately one quarter of the DTS frequency-equivalent vote:

| Raw vote, MiB/s | FKM display, MHz | DTS MHz equivalent |
| ---: | ---: | ---: |
| 762 | 50 | 200 |
| 2597 | 170 | 681 |
| 6881 | 451 | 1804 |
| 7980 | 523 | 2092 |
| 10437 | 684 | 2736 |

The supplied CPU-DDR bwmon max is 6881. Other existing DDR clients advertise
10437 and have transition history at that vote. These are bandwidth votes to
RPMh, not DDR PLL measurements. Native OPP advertisement, accepted votes and
physical DRAM clock are different observations. This batch does not invent a
650 MHz OPP, bypass supported-hardware masks or claim physical DDR overclock.

## Kernel changes

- Return the GPU frequency through the busmon callback instead of leaving its
  output uninitialized, retaining existing mutex and pointer validation.
- Initialize the TZ delta and handle failed SCM DCVS calls. Bound firmware
  deltas before index arithmetic to avoid overflow or invalid table indices.
- Add a saturation guard to msm-adreno-tz: at >=85% measured busy, request a
  native GPU level targeting 75% occupancy; at >=70%, prevent a downshift.
  Below that, retain TZ behavior. The existing KGSL user ceilings, thermal
  limits, POPP and constraints still gate the final request. No permanent
  CPU/GPU maximum, new voltage corner or fabricated frequency is added.
- Use a 5 ms active GPU governor interval and profile interval, below the
  8.33 ms frame period at 120 Hz. Sleep/suspend and idle gating stay active.
  Increased active sampling has a cost; power/performance must be measured.
- Restore the common/Qualcomm schedutil invariant that a rate-rejected target
  invalidates cached_raw_freq. Otherwise unchanged utilization can keep the
  previous frequency after the rate window expires. This preserves WALT and
  the ROM's SchedTune interface. The captured up/down delays are both zero,
  so this fix is not claimed to explain the current screenshot's stutter.
- Add read-only `mushroom_gpu_status` under KGSL, showing driver clock/state,
  cached frequency and user/thermal limits. `mushroom_limits` on devfreq
  separates user min/max from OPP/scaling min/max. Driver flags are not a
  hardware PLL frequency measurement; neither diagnostic wakes the GPU.
- Add optional, rate-limited limit-writer tracing. It is off by default and
  identifies PID/comm writing GPU or CPU-DDR devfreq min/max nodes,
  plus KGSL max/min/default power levels and max_gpuclk when enabled.

A/B toggle for the saturation guard:

```sh
su -c 'echo 0 > /sys/module/governor_msm_adreno_tz/parameters/mushroom_gpu_guard'
su -c 'echo 1 > /sys/module/governor_msm_adreno_tz/parameters/mushroom_gpu_guard'
```

The pre-existing 740 MHz patch selected RPMH_REGULATOR_LEVEL_TURBO (384), above
the stock 670 MHz NOM_L1 (320) corner in this tree. These values are voltage
levels interpreted by firmware, not literal microvolts. This batch does not
increase them further or assume that a new corner is supported by the GMU.
740 MHz stability remains a device-validation question.

## Optional native DDR ceiling and diagnosis

The updated KernelSU companion requests the highest advertised native CPU-DDR
bwmon ceiling once after boot (only recognized 7980/10437 tables). It keeps
normal OPP/scaling limits, the bandwidth governor, thermal policy and idle
scaling. It does not poll or fight HAL writes. If already installed, update the
module in KernelSU; kernel ZIP packaging still includes this optional module.
The companion also resets a global SchedTune boost (40 in this capture) to zero
and applies the scoped UI and CPU-rate profile from batch 3. Disable conflicting
FKM boot/per-app profiles during comparisons. The module is optional and is not
automatically installed by flashing the kernel.

The separate phone script can make the native ceiling request and record
20 seconds of load, limits and limit-writer trace:

```sh
su -c 'sh /sdcard/Download/Mushroom-GPU-DDR-Check.sh --native-ddr'
```

It prints the requested AND effective ceiling. If effective max stays lower,
the OPP/scaling restriction still applies. If it rises and drops when an app
opens, the trace and per-sample limits identify a policy overwrite. It records
in `/sdcard/Download/Mushroom-GPU-DDR-*.txt`. Run without flags to capture
without changing the DDR ceiling; tracing is enabled only for the capture and
restored on exit. `--restore` reverts the recorded ceiling only if it still
matches this script's request, preserving subsequent edits. No filesystem
format, voltage write, thermal disable or foreground affinity change occurs.

## Validation and scope

The five affected GPU/devfreq/schedutil objects compile with official Proton
13 on the original a49b92e1f85d kernel branch. This check covers the modified
translation units; it is not a complete rebuilt Image with the user's current
MGLRU/UI tree. Full kernel/ZIP generation is performed by build.sh on ServerHive.
The guard and actual TZ callback were tested with UBSan, including invalid
samples, saturation, SCM failures, extreme deltas and the final KGSL thermal/
user constraint gate. The actual schedutil functions were tested for rejected
up/down transitions and retry after the rate window. Source patch preflight,
reapply, backup/restore and conflict/lock safeguards were checked separately.
Phone boot, voltage stability, battery use and game FPS are not validated here.

Primary source for the schedutil invariant:
https://android.googlesource.com/kernel/msm/+/7741f55e789d1775d9b34dbe17ba4618b748ab9b/kernel/sched/cpufreq_schedutil.c

GPU/devfreq base source:
https://github.com/haxiswillow/android_kernel_samsung_sm8250/tree/a49b92e1f85d6fafe7c5f5b359c599737c53c416
