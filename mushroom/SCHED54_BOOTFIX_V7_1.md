# Scheduler 5.4 boot fix v7.1

Apply on top of the installed Mushroom scheduler v7 source. This small batch
changes kernel/kthread.c, the scheduler identity, this note and a host test.
It does not modify thermal/configuration files, scheduler tuning, GPU, DDR,
KernelSU, SELinux, MGLRU or the installer.

## Observed failure

The supplied lastkmsg from 4.19.260:MushroomKernel/6ae803cd shows repeated
warnings in kthread_is_per_cpu+0x38 followed by an invalid user-address read at
kthread_is_per_cpu+0x20. The call chain is can_migrate_task -> load_balance,
including idle/softirq balancing, followed by Fatal exception in interrupt
at approximately 1.5-1.8 seconds of boot. Userspace init had started.

The donor fair.c already contains an unconditional kthread_is_per_cpu(p)
call, but the original 4.19 helper assumes PF_KTHREAD and dereferences
set_child_tid even for userspace tasks. That pointer can hold a user TID
address rather than struct kthread. This missing prerequisite was not caught
by compilation; it fails when CFS starts balancing ordinary tasks.

## Correction and provenance

Adapt upstream 3a7956e25e1d7b3c148569e78895e1f3178122a9,
[kthread: Fix PF_KTHREAD vs to_kthread() race](https://android.googlesource.com/kernel/common/+/56c77c1b522928d86738e0d22d1adba44dc9c64b).
Use __to_kthread() for speculative queries: capture set_child_tid, check
PF_KTHREAD and return NULL for ordinary tasks or uninitialized kthreads.
READ_ONCE keeps the two observations explicit. The 4.19 set_child_tid storage
is retained. kthread_probe_data and blkcg speculative queries use the same
safe conversion. Strict to_kthread() and its diagnostic remain for callers
that require real kernel threads. Per-CPU kthreads remain excluded from
migration; ordinary userspace tasks remain eligible for balancing.

A guard only at the fair.c call site would leave the PF_KTHREAD/exec race
behind, so the helper contract itself is repaired, following upstream.

## Apply, build and verify

```sh
python3 apply.py --check && python3 apply.py &&
SCHED_CORE=5.4 SCHED_POLICY=uclamp bash build.sh su
```

The applying script uses .build/build.lock and a separate guarded backup at
.build/mushroom-sched54-bootfix-v7_1. It does not stage, commit or push.
The first line identifies this applier as boot fix v7.1.

After flashing the rebuilt ZIP, the read-only identity must be:

```sh
su -c 'cat /proc/sys/kernel/mushroom_scheduler'
# qcom-5.4.302-port-v7.1
```

Host regression: python3 mushroom/tests/kthread_bootfix_test.py.
The test compiles actual production helpers and covers userspace pointers,
NULL storage, real per-CPU/non-per-CPU kthreads, a simulated exec transition,
probe-data and blkcg lifetime/accounting. It is not a phone boot test.
This patch addresses the demonstrated panic; a device retest is still needed
to establish whether the full boot now completes.

SCHED_CORE=legacy SCHED_POLICY=uclamp bash build.sh su remains available.
python3 apply.py --restore removes only this corrective batch, restoring the
previous v7 source; it does not remove the backport or flash the phone.
