/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _LINUX_MUSHROOM_UI_H
#define _LINUX_MUSHROOM_UI_H
#include <linux/kconfig.h>
struct task_struct;
enum mushroom_ui_class {
	MUSHROOM_UI_NONE,
	MUSHROOM_UI_FOREGROUND,
	MUSHROOM_UI_TOP_APP,
};
#if IS_ENABLED(CONFIG_MUSHROOM_UI)
unsigned int mushroom_task_ui_class(struct task_struct *p);
int mushroom_ui_boost(unsigned int class);
void mushroom_ui_action(void);
#else
static inline unsigned int mushroom_task_ui_class(struct task_struct *p)
{
	return MUSHROOM_UI_NONE;
}
static inline int mushroom_ui_boost(unsigned int class) { return 0; }
static inline void mushroom_ui_action(void) { }
#endif
#endif
