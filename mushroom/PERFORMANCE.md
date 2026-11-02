# Mushroom performance batch 1 — r8q / Android 13

For batch 2/current KCAL, scheduler and zRAM behavior, see
[PERFORMANCE_V2.md](PERFORMANCE_V2.md). The description below records batch 1.
Use the current apply.py help for supported options; its --restore now
restores batch 1 from the separate batch 2 snapshot.

Run `python3 apply.py` at the source root to apply the batch. It does not commit,
push, change token.txt/chat_id.txt, or touch phone data. Backups and a manifest
are kept under the ignored `.build/mushroom-perf-v1/` directory.

```
python3 apply.py --check
python3 apply.py
CLEAN=1 bash build.sh su
```

Use `CLEAN=1` for the first build of each previously built variant after this
configuration/layout change, so no old intermediate archives are reused.
Later builds can use the normal incremental command.

To compare with the original GPU table while keeping the performance changes:

```
python3 apply.py --gpu stock
bash build.sh su
```

`python3 apply.py --gpu 740` restores the experimental OC table. The optional
`--restore` mode restores the source snapshot from before this batch, refusing
to overwrite files changed after applying the batch. No Git reset/commit is used.

## Performance profile

- Disable PM_DEBUG (and its -DDEBUG), scheduler statistics, Gator profiling,
  SLUB debugging, DEBUG_LIST, DEBUG_QSPINLOCK_OWNER and selected Samsung
  scheduler/summary/touch debug logging. Error logs, pstore and useful tracing
  remain available. SCHED_DEBUG is kept for scheduler sysctl compatibility.
  Samsung touch-log APIs have proper disabled stubs for their existing callers.
- Remove the vendor writeback diagnostic walk from normal builds. It was
  acquiring list/inode locks and printing even in cases logging a zero pause.
  MUSHROOM_VERBOSE_DEBUG can re-enable the diagnostic for investigation.
- Keep PREEMPT/NO_HZ_IDLE, use HZ=1000 and retain Qualcomm WALT/schedtune.
  This branch makes schedtune exclusive with UCLAMP and has unguarded schedtune
  calls; changing this API would also need a ROM Power HAL compatibility review.
- Default to schedutil, with 500us upward and 20ms downward rate limits;
  hispeed threshold 85 and nonzero related-thread-group boosts for big/prime.
  Android's HAL can still change these settings at runtime.
- Stop multiplying the 6ms CFS latency by log2(CPU count); the eight-CPU default
  becomes 6ms instead of 24ms. Use 0.5ms wakeup granularity and 0.3ms migration cost.
- Sample Adreno TZ decisions after 2ms/0.5ms busy rather than 5ms/1ms. This
  increases governor responsiveness and also increases the possible update rate.
- Provide LZ4 and use it as the default zram compressor. Userspace can override
  it. Compression is faster-oriented, with a possible memory-density tradeoff.
- Cortex-A77 compiler tuning and -O2; no changes to CPU hardware frequency tables.

These are initial tuning choices. They are not measured performance guarantees.
The higher tick rate, frequency retention and OC can increase energy use.

## Experimental Adreno OC

The added maximum is 740MHz, using the regulator's TURBO performance corner.
The normal 587MHz bin gets 740/670MHz steps, and the 670MHz bins gain 740MHz.
Existing stock frequencies, the 0MHz idle entry and low-bin table are retained.
Initial and thermal-throttle indices are shifted to preserve their original
frequencies. Existing bandwidth votes are reused; ACD coefficients are not
invented for added frequencies. The GMU already supports optional ACD levels.
No thermal protections or secure firmware checks are bypassed.

Only v2/v2.1 SM8250 tables are extended. Firmware, silicon binning and power
limits determine whether the additional frequency can actually be used.
This OC requires physical testing for stability, artifacts and temperature.
After boot, inspect `/sys/class/kgsl/kgsl-3d0/gpu_available_frequencies` and
`/sys/class/kgsl/kgsl-3d0/gpuclk`; a compiled OPP alone does not prove runtime OC.

## KCAL RGB and saturation

The classic-compatible nodes are under `/sys/devices/platform/kcal_ctrl.0/`:

| Node | Accepted values | Default |
| --- | --- | --- |
| kcal | R G B, each 0..256 | 256 256 256 |
| kcal_min | 0..256 | 35 |
| kcal_enable | 0 or 1 | 1 |
| kcal_sat | 128..383; 128 = grayscale | 255 (neutral) |

These writes require root and a SELinux domain allowed to access the nodes.
Values are composed with the ROM's existing PCC/CSC matrix, including Night
Light; they do not overwrite the userspace matrix. The neutral configuration
is bypassed. Updates take effect on the next display commit. Fingerprint-layer
CSC bypass is preserved. This implementation provides RGB/minimum/enable/
saturation; it does not expose hue, contrast, inversion or brightness controls.

Example commands on the phone, not the build server:

```
echo '256 245 235' > /sys/devices/platform/kcal_ctrl.0/kcal
echo 275 > /sys/devices/platform/kcal_ctrl.0/kcal_sat
# Restore neutral calibration:
echo '256 256 256' > /sys/devices/platform/kcal_ctrl.0/kcal
echo 255 > /sys/devices/platform/kcal_ctrl.0/kcal_sat
```

## Findings from the supplied logs

The captured dmesg contains no kernel panic, Oops, lockup or GPU reset/fault.
It starts about 15 seconds after boot and cannot rule out earlier events.
There are repeated vendor diagnostics and debug configurations enabled.
The logcat records three Telegram RenderThread SIGSEGVs with the top frame
`android::BlobCache::clean()` in libhwui.so, reached while storing shaders.
That is a userspace crash location, not proof that the kernel is its cause or
proof that the kernel cannot contribute. This batch does not patch libhwui.so.
CPU Power Profile 56-vs-55 warnings are accounting mismatches, not measurements
of a CPU frequency cap. Frame timing, actual clocks and temperature under the
same workload are needed for a reliable before/after comparison.
