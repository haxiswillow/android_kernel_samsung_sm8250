/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_MUSHROOM_UCLAMP_H
#define _LINUX_MUSHROOM_UCLAMP_H
struct task_struct;
#if defined(CONFIG_UCLAMP_TASK) && defined(CONFIG_CPUSETS)
extern unsigned int mushroom_uclamp_top_app;
extern unsigned int mushroom_uclamp_foreground;
unsigned int mushroom_cpuset_util_min(struct task_struct *p);
#else
static inline unsigned int mushroom_cpuset_util_min(struct task_struct *p)
{
	return 0;
}
#endif
#endif
