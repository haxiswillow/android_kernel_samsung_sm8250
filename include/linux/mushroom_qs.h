/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_MUSHROOM_QS_H
#define _LINUX_MUSHROOM_QS_H

#include <linux/types.h>
struct task_struct;

#if defined(CONFIG_MUSHROOM_SCHED54) && defined(CONFIG_SCHED_WALT) && \
	defined(CONFIG_UCLAMP_TASK) && defined(CONFIG_CPUSETS) && \
	defined(CONFIG_MUSHROOM_BG_CPUSET)
#define MUSHROOM_QS_CPUSET 1
bool mushroom_qs_cpuset_task(struct task_struct *p);
bool mushroom_qs_cpuset_enabled(void);
void mushroom_qs_cpuset_kick(struct task_struct *p);
void mushroom_qs_cpuset_refresh(void);
void mushroom_qs_core_ctl_kick(void);
#else
static inline void mushroom_qs_cpuset_kick(struct task_struct *p) { }
static inline void mushroom_qs_cpuset_refresh(void) { }
static inline void mushroom_qs_core_ctl_kick(void) { }
#endif
#endif
