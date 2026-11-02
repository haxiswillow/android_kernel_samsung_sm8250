// SPDX-License-Identifier: GPL-2.0
/* Instantiate the 4.19 native tracepoint adapters in their own unit. */
#include "sched.h"
#define CREATE_TRACE_POINTS
#include <trace/hooks/sched.h>
