# Mushroom batch 2 — r8q / Android 13

Batch3 updates the interaction/VM policy; see PERFORMANCE_V3.md. The current
apply.py --restore returns to batch2. The description below records batch2.

This batch requires batch 1. Run `python3 apply.py --check`, then
`python3 apply.py` and `bash build.sh su`. GPU tables, GPU governor and
`Mushroom@ServerHive` compile identity are preserved. No commit or push occurs.
Backups for this batch are under `.build/mushroom-perf-v2/`; `--restore`
restores batch 1, refusing to overwrite subsequent edits.

## KCAL compatibility

The missing `kcal_val` node was an incomplete API in batch 1. All eight common
KCAL nodes can now be read under `/sys/devices/platform/kcal_ctrl.0/`:

| Node | Range | Neutral/default |
| --- | --- | --- |
| kcal | RGB, 0..256 each | 256 256 256 |
| kcal_min | 0..256 | 35 |
| kcal_enable | 0 or 1 | 1 |
| kcal_sat | 128..383; 128 grayscale | 255 |
| kcal_val | 128..383 | 255 |
| kcal_cont | Neutral 255 only | 255 |
| kcal_hue | 0..1536, full circle | 0 |
| kcal_invert | Neutral 0 only | 0 |

RGB, minimum, enable, saturation, value and hue have real processing in the
existing Samsung per-plane signed Q15 matrix path. Value is a linear gain;
hue is a fixed-point matrix approximation, so appearance need not exactly
match another hardware backend. Defaults bypass calibration. The existing
fingerprint-layer bypass remains. Updates appear at the next display commit.

The DGM CSC backend only writes a 3x3 matrix and has no offset path. Centered
contrast and inversion therefore cannot be implemented consistently across
these planes with this backend. Their nodes report the actual neutral state,
accept neutral writes and return EOPNOTSUPP for unsupported changes. They are
not fake working controls. A future implementation needs a properly validated
post-composition backend and fingerprint handling before enabling these two.
FKM access still depends on root and ROM SELinux; no blanket bypass is added.

## Scheduler and schedutil

The WALT previous-CPU fast path used to return an idle mid CPU before scanning
the higher-capacity candidates, even for boosted, latency-sensitive tasks.
That shortcut now defers to the existing candidate search when the previous
CPU has less than the root domain's maximum capacity. Affinity, cpusets,
online/isolated CPU checks, thermal capacity and fallback paths remain intact.
This is a selection-policy correction, not evidence of a broken physical CPU7.

Related-thread-group migration thresholds change from 100/95 to 65/50 percent,
and initial task demand from 15 to 25 percent. These defaults let qualifying
bursts consider higher-capacity clusters earlier. Schedutil's existing hispeed
branch gets the RTG floor (little 1GHz, big 1.4784GHz, prime 1.5744GHz) instead
of zero. Neither frequencies nor all tasks are pinned to maximum; userspace
can still override the tunables. The tradeoff can be additional energy use.

No measurement yet proves why the user's CPU7 or CPU4 showed zero utilization.
Sampling, cpusets, core_ctl/hotplug, thermal limits and the actual workload all
matter. `collect-ui.sh` records these details without changing settings.
Remove FKM's saved performance governor profile to test schedutil fairly.

## zRAM boot policy

The earlier supplied dmesg reports exactly 2147483648 bytes for zram0 and
2097148KiB swap. This is compressed swap capacity, not physical RAM.

The installer explicitly sets `zram.mushroom_legacy_2g_mb=4096` in the boot
command line. The driver translates only zram0's *initial* 2GiB request to
4GiB, and only if the device has at least 5GiB physical RAM. Other sizes,
other devices and initialized swap are unchanged. Capacity/accounting and
the `disksize` sysfs read return the real configured 4GiB value. There is no
hot swapoff, no fake RAM report and no allocation of 4GiB physical RAM at boot.

The policy is off in the driver unless enabled explicitly by the boot argument.
For a future build with the ROM's size unchanged, replace the value 4096 with 0
in `mushroom/anykernel.sh` before building. More swap may retain apps, but it
does not guarantee faster UI and can increase compression work under pressure.

## Installer UI

Title: `Mushroom Kernel BY Nihil@donottellmynam` (nickname as spelled in request).
`mushroom/prepare-installer.py` patches four exact UI contexts in the pinned
AnyKernel3 export, removing redundant explicit blank messages around credits
and Done. It preserves osm0sis credits, the recovery UI protocol, error paths
and all partition writers. A changed upstream context stops packaging.

## Phone collection

Copy `mushroom/collect-ui.sh` to the phone as
`/sdcard/Download/Mushroom-UI-Collect.sh`, then run:

```
su -c 'sh /sdcard/Download/Mushroom-UI-Collect.sh'
```

During its 12-second sample, open/close apps and pull the notification shade.
The resulting `Mushroom-UI-*.txt` in Download includes governor/masks/core_ctl,
per-core CPU counters, UI thread affinity, swap, KCAL, crash logs and dmesg.
It does not alter governors, thermal settings, cpusets, tracing or swap.
