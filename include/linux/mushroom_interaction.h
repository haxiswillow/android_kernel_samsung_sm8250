/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_MUSHROOM_INTERACTION_H
#define _LINUX_MUSHROOM_INTERACTION_H
#if defined(CONFIG_MUSHROOM_SCHED54) && defined(CONFIG_SCHED_WALT) &&          \
	defined(CONFIG_CPU_FREQ)
void mushroom_input_boost_launch(void);
#else
static inline void mushroom_input_boost_launch(void)
{
}
#endif
#if defined(CONFIG_MUSHROOM_SCHED54) && defined(CONFIG_PM_DEVFREQ)
void mushroom_ddr_boost_kick(unsigned int duration_ms);
#else
static inline void mushroom_ddr_boost_kick(unsigned int duration_ms)
{
}
#endif
#endif
