# Mushroom interaction pulses

The r8q default is a temporary minimum-frequency request, renewed by touch
reports, key presses and promotion of a process into the `top-app` cpuset.
The latter covers existing applications as well as newly started processes
when Android performs that promotion. It does not hook ActivityManager.
Pulling QS uses the touch path; programmatic panel expansion without an input
event or a top-app transition has no dedicated trigger.

| Request | Default | Duration after the last trigger |
| --- | ---: | ---: |
| LITTLE, CPUs 0–3 | 1708800 kHz | 250 ms |
| BIG, CPUs 4–6 | 2246400 kHz | 250 ms |
| PRIME, CPU 7 | 2553600 kHz | 250 ms |
| CPU-to-DDR bandwidth | Effective allowed maximum | 500 ms |

CPU requests use the existing CAF/WALT policy notifier. The floor cannot
raise the policy maximum. Existing user minimums are retained when the pulse
expires; this does not overwrite `scaling_min_freq` or select the performance
governor. A higher legacy CAF request still wins. The effective duration is
the greater of the legacy duration and the Mushroom duration, bounded to
1000 ms. Existing core_ctl, affinity, uclamp and QS placement rules remain.

The DDR request applies only to `cpu-llcc-ddr-bw`, through its existing
devfreq governor and target callback. It respects the current effective
scaling/OPP maximum and does not write persistent min/max values. The normal
governor reevaluates the target on expiry. Bandwidth votes in this node are
not DDR PLL frequencies: this patch does not add an overclock or change
voltages. Suspended/stopped devices are skipped. GPU policy is unchanged.

Touch reports are coalesced to at most one pulse per 16 ms. Renewing a pulse
does not reprogram every CPU policy or DDR target each frame. An ordered CPU
worker applies changed floors; the expiry workers restore governor control.
High floors can cost battery and heat during continuous interaction. This
patch preserves existing caps and does not change thermal configuration.

## Controls

The built-in object's parameters are in `/sys/module/cpu_boost/parameters/`:

- `mushroom_enabled`: `1` by default for r8q; `0` disables these extra pulses.
- `mushroom_little_khz`, `mushroom_big_khz`, `mushroom_prime_khz`: native floors.
- `mushroom_cpu_ms`: 250; consumed within 16–1000 ms.
- `mushroom_ddr_ms`: 500; consumed within 0–1000 ms; 0 disables new DDR pulses.

Changes are consumed by the next pulse. Previously scheduled pulses remain
bounded and expire; changing these controls is not an immediate cancel API.
The legacy `/sys/devices/system/cpu/cpu_boost/` ABI is retained. Its frequency
parser now rejects malformed input before committing any CPU values.

## Validation

The three changed C translation units compiled with the supplied `su`
configuration and pinned Proton clang 13. Host tests execute the actual
function bodies under UBSan: expiry, renewal, legacy fallback, shared policy
aggregation, maximum caps, invalid writes, suspend exclusion and tick wrap.
Existing scheduler, MGLRU, topology, UI Prime, schedutil and memory/I/O
regressions were checked. These checks do not establish a phone boot, frame
latency, battery life, actual DDR sensor readings or sustained game performance.

```sh
python3 mushroom/tests/interaction_boost_test.py
python3 mushroom/tests/scheduler54_test.py
```

The standalone `apply.py` checks exact preimages from the supplied current
source, takes the build script's `.build/build.lock`, and backs up its targets
under `.build/mushroom-interaction-v12/`. It does not commit, push, change the
root implementation, or overwrite unrelated source/configuration files.
Use `python3 apply.py --restore` to reverse only this patch, provided its
target files have not been edited since application.
