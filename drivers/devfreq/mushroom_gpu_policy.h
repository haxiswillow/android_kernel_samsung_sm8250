/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _MUSHROOM_GPU_POLICY_H
#define _MUSHROOM_GPU_POLICY_H
#include <linux/kernel.h>
#include <linux/math64.h>

/* KGSL tables descend: index zero is the highest clock. No clock/voltage OPP
 * is invented here. The KGSL target still applies user and thermal limits.
 */
static inline int mushroom_gpu_target(const unsigned long *table, int count,
		int current_level, int proposed, s64 total, s64 busy)
{
	u64 load, target;
	int floor;

	if (count < 1 || current_level < 0 || current_level >= count)
		return proposed;
	proposed = clamp(proposed, 0, count - 1);
	if (total <= 0 || busy < 0)
		return proposed;
	busy = min(busy, total);
	/* Avoid overflow even with corrupted/very long hardware samples. */
	while ((u64)total > 0xffffffffULL) {
		total >>= 1;
		busy >>= 1;
	}
	load = div64_u64((u64)busy * 1000, total);
	if (load >= 850) {
		/* Request 25% headroom only while actually saturated. */
		target = div64_u64((u64)table[current_level] * load, 750);
		for (floor = count - 1; floor > 0; floor--)
			if (table[floor] >= target)
				break;
		return min(proposed, floor);
	}
	/* Prevent a downshift at >=70% use; light workloads retain TZ policy. */
	if (load >= 700)
		return min(proposed, current_level);
	return proposed;
}
/* Demand-based alternative to firmware policy. State is per GPU. Fast up,
 * one step down after 30 ms of low demand; idle samples never pin fmax.
 */
static inline int mushroom_gpu_demand(const unsigned long *table, int count,
		int active_level, s64 total, s64 busy, u32 *down_us)
{
	u64 load, target;
	u32 elapsed;
	int next;

	if (count < 1 || active_level < 0 || active_level >= count || total <= 0 || busy < 0)
		return active_level;
	elapsed = min_t(u64, total, 30000);
	busy = min(busy, total);
	while ((u64)total > 0xffffffffULL) {
		total >>= 1;
		busy >>= 1;
	}
	load = div64_u64((u64)busy * 1000, total);
	target = div64_u64((u64)table[active_level] * load, 750);
	for (next = count - 1; next > 0; next--)
		if (table[next] >= target)
			break;
	if (next < active_level) {
		*down_us = 0;
		return next;
	}
	if (load >= 650 || next == active_level) {
		*down_us = 0;
		return active_level;
	}
	*down_us = min_t(u32, 30000, *down_us) + elapsed;
	if (*down_us < 30000)
		return active_level;
	*down_us = 0;
	return min(active_level + 1, count - 1);
}

#endif
