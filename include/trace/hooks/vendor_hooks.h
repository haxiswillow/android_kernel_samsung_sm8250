/* SPDX-License-Identifier: GPL-2.0 */
/* 4.19 instrumentation adapter: native tracepoints, no vendor module needed. */
#include <linux/tracepoint.h>
#undef DECLARE_HOOK
#undef DECLARE_RESTRICTED_HOOK
#define DECLARE_HOOK(name, proto, args) DECLARE_TRACE(name, PARAMS(proto), PARAMS(args))
#define DECLARE_RESTRICTED_HOOK(name, proto, args, cond) DECLARE_TRACE(name, PARAMS(proto), PARAMS(args))
