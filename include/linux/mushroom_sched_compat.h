/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_MUSHROOM_SCHED_COMPAT_H
#define _LINUX_MUSHROOM_SCHED_COMPAT_H
#include <linux/sched.h>
#ifdef CONFIG_MUSHROOM_SCHED54
#define mushroom_task_walt(p, field) ((p)->wts.field)
#else
#define mushroom_task_walt(p, field) ((p)->field)
#endif
static inline void mushroom_binder_latency(struct task_struct *p, bool enable)
{
#ifdef CONFIG_MUSHROOM_SCHED54
	if (enable)
		p->wts.low_latency |= WALT_LOW_LATENCY_BINDER;
	else
		p->wts.low_latency &= ~WALT_LOW_LATENCY_BINDER;
#else
	p->low_latency = enable;
#endif
}
#endif
