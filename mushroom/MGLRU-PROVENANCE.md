# MGLRU backport provenance

GPL-compatible Linux kernel changes; original author/sign-off notices retained
in the upstream commits linked below. This tree does not replace authorship
with Mushroom authorship. Imported from the public 4.19 backport maintained at
https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845 .

The series is the page-based 2022 implementation, not a relabelled 6.x folio
implementation. The import includes its 16 prerequisites and 13 main/doc/fix
commits. Manual Samsung adaptations: preserve the BUILD_VDSO32_64 page-flags
layout guard; reserve generation/reference bits alongside existing KASAN
bits without repeating their definition; retain existing nodemask/mmdebug
includes; move exec's add_mm after local_irq_enable while holding task_lock;
preserve all Samsung VM/Heimdall logic outside the imported reclaim paths.
No cherry-pick/commit was made in the destination checkout.

- [ae75c1a83c1b — UPSTREAM: mm: Replace list_move_tail() with add_page_to_lru_list_tail()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/ae75c1a83c1b76c33e64c3637fda8505da86d975)
- [83e2f547484a — UPSTREAM: arm64: cpufeature: Introduce helper cpu_has_hw_af()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/83e2f547484ac2d588b3965640e6edf7d4b6c6d7)
- [e13048fe51c1 — UPSTREAM: mm/vmscan.c: Use update_lru_size() in update_lru_sizes()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/e13048fe51c129efddf7576fdd68da7403ac862f)
- [d3e299594873 — BACKPORT: mm/swapcache: Support to handle the shadow entries](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/d3e29959487382c0ab0b8831e070d8315dd83b5e)
- [97be316d37b6 — BACKPORT: mm: Remove superfluous __ClearPageActive()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/97be316d37b66af8f3c856ca870b7b5dd025822a)
- [aba9c57a3ddf — BACKPORT: mm: Use self-explanatory macros rather than "2"](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/aba9c57a3ddfcfab86c25ca3f2f756911fefa61b)
- [3af1140d34f4 — BACKPORT: mm/vmscan.c: Use add_page_to_lru_list()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/3af1140d34f4d882316264727540697f422e3b12)
- [2adcdb2038a3 — BACKPORT: include/linux/mm_inline.h: Shuffle lru list addition and deletion functions](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/2adcdb2038a312d146d112195455b9ca67b2f545)
- [325424277a19 — BACKPORT: mm: Don't pass "enum lru_list" to lru list addition functions](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/325424277a19b6bb12b5765f9da06c7c4b9c60c9)
- [f8532e3c136a — UPSTREAM: mm/swap.c: Don't pass "enum lru_list" to trace_mm_lru_insertion()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/f8532e3c136aea75e9cc2601df14ae09f7a8bcc6)
- [4fa0c5f05a83 — BACKPORT: mm/swap.c: Don't pass "enum lru_list" to del_page_from_lru_list()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/4fa0c5f05a83589daab8069e77db50c6aa67ab39)
- [2e0c5418e419 — BACKPORT: mm: Add __clear_page_lru_flags() to replace page_off_lru()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/2e0c5418e4196427789e691e0a73a212e08f9e20)
- [7e60a1516589 — UPSTREAM: mm: VM_BUG_ON lru page flags](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/7e60a1516589069575f68fde6738dd30f0604666)
- [d6c9c2a13aac — BACKPORT: include/linux/mm_inline.h: Fold page_lru_base_type() into its sole caller](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/d6c9c2a13aac9d4fb797dfff6a21ada742f270a8)
- [842c6e130344 — FROMLIST: mm: x86, arm64: Add arch_has_hw_pte_young()](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/842c6e1303445bd6c036340ef3b255cc23422b4f)
- [b7e59fa3da6b — FROMLIST: mm: x86: Add CONFIG_ARCH_HAS_NONLEAF_PMD_YOUNG](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/b7e59fa3da6b993f2d91d321a60515b3442f9d75)
- [67e9d5c8e0d2 — FROMLIST: mm: multi-gen LRU: Groundwork](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/67e9d5c8e0d28eb521533e0bb42771d12959d026)
- [e9343ee8a22f — FROMLIST: mm: multi-gen LRU: Minimal implementation](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/e9343ee8a22fe2267ac8dfd62a8e46c45d2e65e5)
- [fba9f87f68f3 — FROMLIST: mm: multi-gen LRU: Exploit locality in rmap](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/fba9f87f68f31973557e8ec315b177181324b670)
- [cb7e73b77cef — FROMLIST: mm: multi-gen LRU: Support page table walks](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/cb7e73b77cef509361ea7923b10ecfe836e3d48d)
- [0b8c89d3791e — FROMLIST: mm: multi-gen LRU: Optimize multiple memcgs](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/0b8c89d3791eec2dd6d0ea9a971bf7cc0bb4c177)
- [003eabcd2570 — FROMLIST: mm: multi-gen LRU: Kill switch](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/003eabcd2570febabe7f0466e4c915d5578835c2)
- [fa25f9ac5f19 — FROMLIST: mm: multi-gen LRU: Thrashing prevention](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/fa25f9ac5f191f3de8b64557a5a7bc2573afa33c)
- [b195eeedf84a — FROMLIST: mm: multi-gen LRU: Debugfs interface](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/b195eeedf84a4294b67598153b2f5eae72c9477e)
- [2c33b6536db6 — FROMLIST: mm: multi-gen LRU: Admin guide](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/2c33b6536db6a1d835cc83f1fb312de0ebe6d42d)
- [c0aff1f77c19 — FROMLIST: mm: multi-gen LRU: Design doc](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/c0aff1f77c194400f41b39a451c7b9d78462c7ef)
- [ccdfe894de14 — ANDROID: Make MGLRU aware of speculative faults](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/ccdfe894de1450d146de5268a47e25efa6d28296)
- [59a4952e7940 — mm: MGLRU: Fix on qcom baseline](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/59a4952e7940da5223a5c28ef8c0c348febb6e5c)
- [bbdb283aa6ef — BACKPORT: mm: multi-gen LRU: Move lru_gen_add_mm() out of IRQ-off region](https://github.com/shinichi-c/Dynamic_kernel_4.19_oneplus_sdm845/commit/bbdb283aa6ef69ce5856a1373d4a44b6b00b02f5)
