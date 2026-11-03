// SPDX-License-Identifier: GPL-2.0-only
/* r8q display-thread placement and bounded WALT core availability. */
#include "sched.h"
#include "walt/walt.h"
#include <linux/jiffies.h>
#include <linux/moduleparam.h>
#include <linux/cred.h>
#include <linux/mushroom_qs.h>

static bool enabled = true;
static bool display_affinity = true;
static unsigned int hold_ms = 120;
static unsigned long active_until;
static char *version = "mushroom-qs-v9";
static int qs_set_bool(const char *val, const struct kernel_param *kp)
{
	int ret = param_set_bool(val, kp);

	if (!ret) {
		mushroom_qs_cpuset_refresh();
		mushroom_qs_core_ctl_kick();
	}
	return ret;
}
static const struct kernel_param_ops qs_bool_ops = {
	.set = qs_set_bool,
	.get = param_get_bool,
};
module_param_cb(enabled, &qs_bool_ops, &enabled, 0644);
module_param_cb(display_affinity, &qs_bool_ops, &display_affinity, 0644);
module_param(hold_ms, uint, 0644);
module_param(version, charp, 0444);
MODULE_PARM_DESC(enabled, "Enable scoped display-thread capacity preference");
MODULE_PARM_DESC(display_affinity, "Allow scoped display threads beyond system-background");
MODULE_PARM_DESC(hold_ms, "Activity window, internally bounded to 16..250 ms");

static bool qs_comm_is(struct task_struct *p, const char *name)
{
	char comm[TASK_COMM_LEN];
	int i;

	for (i = 0; i < TASK_COMM_LEN; i++)
		comm[i] = READ_ONCE(p->comm[i]);
	comm[TASK_COMM_LEN - 1] = '\0';
	return !strcmp(comm, name);
}

static bool qs_display_task(struct task_struct *p)
{
	struct task_struct *leader;
	char first = READ_ONCE(p->comm[0]);
	bool match = false;

	if (first != 's' && first != 'R')
		return false;
	rcu_read_lock();
	leader = READ_ONCE(p->group_leader);
	if (!leader)
		goto out;
	if (qs_comm_is(leader, "surfaceflinger")) {
		match = (p == leader && qs_comm_is(p, "surfaceflinger")) ||
			qs_comm_is(p, "RenderEngine");
	} else if (qs_comm_is(p, "RenderThread")) {
		/* Android's TASK_COMM_LEN-truncated SystemUI process names. */
		match = qs_comm_is(leader, "ndroid.systemui") ||
			qs_comm_is(leader, "com.android.sys");
	}
out:
	rcu_read_unlock();
	return match;
}

#ifdef MUSHROOM_QS_CPUSET
bool mushroom_qs_cpuset_task(struct task_struct *p)
{
	/* Android compositor and SystemUI run as AID_SYSTEM in the initial ns. */
	return p->mm && !(p->flags & PF_KTHREAD) &&
		uid_eq(task_uid(p), KUIDT_INIT(1000)) && qs_display_task(p);
}

bool mushroom_qs_cpuset_enabled(void)
{
	return READ_ONCE(enabled) && READ_ONCE(display_affinity);
}

static bool qs_needs_affinity(struct task_struct *p)
{
	const struct cpumask *requested = &p->wts.cpus_requested;
	int cpu;

	if (!mushroom_qs_cpuset_enabled() || !mushroom_qs_cpuset_task(p))
		return false;
	for_each_cpu(cpu, p->cpus_ptr)
		if (capacity_orig_of(cpu) > capacity_orig_of(0))
			return false;
	/* Preserve successful explicit userspace affinity restrictions. */
	if (cpumask_empty(requested))
		requested = cpu_possible_mask;
	for_each_cpu(cpu, requested)
		if (capacity_orig_of(cpu) > capacity_orig_of(0))
			return true;
	return false;
}
#else
static bool qs_needs_affinity(struct task_struct *p) { return false; }
#endif

bool mushroom_qs_active(void)
{
	unsigned long until = READ_ONCE(active_until);

	return READ_ONCE(enabled) && until && time_before(jiffies, until);
}

bool mushroom_qs_note_task(struct task_struct *p)
{
	unsigned int duration;
	bool cold;

	if (!READ_ONCE(enabled) || !qs_display_task(p))
		return false;
	cold = !mushroom_qs_active();
	duration = clamp_t(unsigned int, READ_ONCE(hold_ms), 16, 250);
	WRITE_ONCE(active_until, jiffies + msecs_to_jiffies(duration));
	if (cold)
		mushroom_qs_core_ctl_kick();
	if (qs_needs_affinity(p))
		mushroom_qs_cpuset_kick(p);
	return true;
}

bool mushroom_qs_keep_cluster(int first_cpu)
{
	/* CPU0 is a Little on the r8q. Do not change cluster max/thermal limits. */
	return mushroom_qs_active() &&
		capacity_orig_of(first_cpu) > capacity_orig_of(0);
}

int mushroom_qs_pick_cpu(struct task_struct *p, const struct cpumask *eligible,
			 bool idle_only)
{
	unsigned long little = capacity_orig_of(0);
	unsigned long best_cap = little, ceiling;
	int cpu, best = -1;

	if (!mushroom_qs_active() || !qs_display_task(p))
		return -1;
	ceiling = uclamp_eff_value(p, UCLAMP_MAX);
	if (ceiling <= little)
		return -1;

	for_each_cpu_and(cpu, eligible, p->cpus_ptr) {
		unsigned long cap;

		if (!cpu_active(cpu) || cpu_isolated(cpu) ||
		    is_reserved(cpu) || sched_cpu_high_irqload(cpu))
			continue;
		if (idle_only && !idle_cpu(cpu))
			continue;
		cap = min(capacity_of(cpu), thermal_cap(cpu));
		cap = min(cap, ceiling);
		if (cap <= little)
			continue;
		if (cap > best_cap ||
		    (cap == best_cap && cpu == task_cpu(p))) {
			best_cap = cap;
			best = cpu;
		}
	}
	return best;
}
