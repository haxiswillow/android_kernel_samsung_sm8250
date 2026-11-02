# MGLRU / Android 13 LMKD accounting compatibility

The 4.19 `workingset_refault`, `workingset_activate` and `workingset_restore`
counters originally describe file-backed pages. The imported page-based MGLRU
also handles anonymous pages, but updated these same legacy counters for both
types. This changes the meaning of an existing userspace interface.

Android 13 LMKD treats a nonzero legacy `workingset_refault` as the file-cache
refault count, and divides its growth by the file-backed LRU size to estimate
thrashing. Anonymous refaults can therefore inflate that input. Merely adding
a new `workingset_refault_file` counter would not fix Android 13's preference
for a nonzero legacy counter.

This compatibility fix keeps the existing 4.19 counter names and restores their
file-only meaning in MGLRU. Anonymous refault/protection feedback remains in
MGLRU's separate per-type arrays. `SetPageWorkingset()` still runs for anonymous
pages. The eviction algorithm, TTL, swappiness, OOM/LMKD thresholds, ZRAM size,
CPU/GPU settings and thermal policy are unchanged.

This is an accounting fix, not a complete newer-memory-manager backport or a
promise of lower swap traffic. Whether it prevents a specific application exit
depends on that exit's actual cause. The two supplied successful 90-second
captures contain memory stalls but no YouTube exit record; a historical FKM
Java exception is unrelated evidence. `oom_kill=0` does not exclude LMKD kills.

References:

- Android 13 source: https://android.googlesource.com/platform/system/memory/lmkd/+/refs/tags/android-13.0.0_r1/lmkd.cpp
  (`mp_event_psi`, legacy-counter preference and file-cache denominator).
- Upstream separates anonymous/file workingset accounting since Linux 5.9:
  https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=170b04b7ae49634df103810dad67b22cf8a99aa6
  (Joonsoo Kim et al.). This small 4.19 compatibility adaptation does not import
  that full series or claim its authorship.
- Reviewed Mushroom source: `983eb8e90adab5f81c55db8f5bebbaadbc0b74ef`,
  `lineage-20_4.19.260-atakan`.

Validation: `python3 mushroom/tests/check-mglru-lmkd.py` compiles and executes the
actual modified `lru_gen_refault()` and `sort_page()` functions in a bounded
host model under UBSan. It checks file/anonymous and single/huge-page counters,
internal refault/protection feedback, working-set flags and rejection paths.
It is not a whole-kernel build or a phone boot/FPS test.

Build on the server: `bash build.sh su`.
Undo only this batch: `python3 apply.py --restore` (guarded against later edits).
