/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _MUSHROOM_KCAL_H_
#define _MUSHROOM_KCAL_H_

#include <linux/types.h>
#include <linux/kconfig.h>

#if IS_ENABLED(CONFIG_MUSHROOM_KCAL)
u32 mushroom_kcal_generation(void);
bool mushroom_kcal_apply(u32 coeff[9], u32 *generation);
#else
static inline u32 mushroom_kcal_generation(void) { return 0; }
static inline bool mushroom_kcal_apply(u32 coeff[9], u32 *generation)
{
	*generation = 0;
	return false;
}
#endif
#endif
