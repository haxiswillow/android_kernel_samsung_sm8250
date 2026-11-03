// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2013-2015,2017,2019-2021, The Linux Foundation. All rights reserved.
 */
#define pr_fmt(fmt) "cpu-boost: " fmt

#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/cpufreq.h>
#include <linux/cpu.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/input.h>
#include <linux/time.h>
#include <linux/sysfs.h>
#include <linux/pm_qos.h>
#include <linux/jiffies.h>
#include <linux/moduleparam.h>
#include <linux/spinlock.h>
#include <linux/workqueue.h>
#include <linux/mushroom_interaction.h>

#include "qc_vas.h"

#define cpu_boost_attr_rw(_name)                                               \
	static struct kobj_attribute _name##_attr =                            \
		__ATTR(_name, 0644, show_##_name, store_##_name)

#define show_one(file_name)                                                    \
	static ssize_t show_##file_name(                                       \
		struct kobject *kobj, struct kobj_attribute *attr, char *buf)  \
	{                                                                      \
		return scnprintf(buf, PAGE_SIZE, "%u\n", file_name);           \
	}

#define store_one(file_name)                                                   \
	static ssize_t store_##file_name(struct kobject *kobj,                 \
					 struct kobj_attribute *attr,          \
					 const char *buf, size_t count)        \
	{                                                                      \
		sscanf(buf, "%u", &file_name);                                 \
		return count;                                                  \
	}

struct cpu_sync {
	int cpu;
	unsigned int input_boost_min;
	unsigned int input_boost_freq;
};

static DEFINE_PER_CPU(struct cpu_sync, sync_info);
static struct workqueue_struct *cpu_boost_wq;

static struct work_struct input_boost_work;

static bool input_boost_enabled;

static unsigned int input_boost_ms = 40;
show_one(input_boost_ms);
store_one(input_boost_ms);
cpu_boost_attr_rw(input_boost_ms);

static unsigned int sched_boost_on_input;
show_one(sched_boost_on_input);
store_one(sched_boost_on_input);
cpu_boost_attr_rw(sched_boost_on_input);

static bool sched_boost_active;
static unsigned int active_sched_boost;

static struct delayed_work input_boost_rem;
static u64 last_input_time;
#define MIN_INPUT_INTERVAL (16 * USEC_PER_MSEC)
static DEFINE_SPINLOCK(input_boost_lock);
static unsigned long input_boost_until;
static bool mushroom_boost_ready;
/* Independent of the ROM's legacy CAF floor writes; all values are tunable. */
static bool mushroom_enabled = IS_ENABLED(CONFIG_SEC_R8Q_PROJECT);
static unsigned int mushroom_little_khz = 1708800;
static unsigned int mushroom_big_khz = 2246400;
static unsigned int mushroom_prime_khz = 2553600;
static unsigned int mushroom_cpu_ms = 250;
static unsigned int mushroom_ddr_ms = 500;
module_param(mushroom_enabled, bool, 0644);
module_param(mushroom_little_khz, uint, 0644);
module_param(mushroom_big_khz, uint, 0644);
module_param(mushroom_prime_khz, uint, 0644);
module_param(mushroom_cpu_ms, uint, 0644);
module_param(mushroom_ddr_ms, uint, 0644);
MODULE_PARM_DESC(mushroom_enabled, "Renewable r8q interaction CPU/DDR pulses");
MODULE_PARM_DESC(mushroom_cpu_ms, "CPU pulse: bounded to 16..1000 ms");
MODULE_PARM_DESC(mushroom_ddr_ms, "DDR pulse: 0 disables, bounded to 1000 ms");

static unsigned int mushroom_cluster_floor(unsigned int cpu)
{
	unsigned int floor;
	if (!READ_ONCE(mushroom_enabled))
		return 0;
	if (cpu < 4)
		floor = READ_ONCE(mushroom_little_khz);
	else if (cpu < 7)
		floor = READ_ONCE(mushroom_big_khz);
	else if (cpu == 7)
		floor = READ_ONCE(mushroom_prime_khz);
	else
		floor = 0;
	return min(floor, 4000000U);
}

static unsigned int mushroom_boost_duration(void)
{
	unsigned int duration = min(READ_ONCE(input_boost_ms), 1000U);
	if (READ_ONCE(mushroom_enabled))
		duration = max(duration,
			       clamp_t(unsigned int, READ_ONCE(mushroom_cpu_ms),
				       16, 1000));
	return duration;
}

/* IRQ/cpuset context: no sleeping, policy walks or allocation. */
static void mushroom_boost_pulse(void)
{
	unsigned long flags, now, until;
	bool was_active, dirty = false;
	unsigned int cpu;
	if (!smp_load_acquire(&mushroom_boost_ready))
		return;
	for_each_possible_cpu (cpu) {
		struct cpu_sync *info = &per_cpu(sync_info, cpu);
		if (READ_ONCE(info->input_boost_min) !=
		    max(READ_ONCE(info->input_boost_freq),
			mushroom_cluster_floor(cpu))) {
			dirty = true;
			break;
		}
	}
	spin_lock_irqsave(&input_boost_lock, flags);
	now = jiffies;
	until = now + msecs_to_jiffies(mushroom_boost_duration());
	was_active = input_boost_until && time_before(now, input_boost_until);
	if (!was_active || time_after(until, input_boost_until))
		input_boost_until = until;
	if (!was_active || dirty ||
	    READ_ONCE(sched_boost_on_input) != READ_ONCE(active_sched_boost))
		queue_work(cpu_boost_wq, &input_boost_work);
	spin_unlock_irqrestore(&input_boost_lock, flags);
	if (READ_ONCE(mushroom_enabled))
		mushroom_ddr_boost_kick(min(READ_ONCE(mushroom_ddr_ms), 1000U));
}

void mushroom_input_boost_launch(void)
{
	if (READ_ONCE(mushroom_enabled))
		mushroom_boost_pulse();
}

static ssize_t store_input_boost_freq(struct kobject *kobj,
				      struct kobj_attribute *attr,
				      const char *buf, size_t count)
{
	unsigned int *freqs, cpu, val;
	char *copy, *cursor, *token, *colon;
	bool enabled = false;
	int ret = -EINVAL;
	copy = kstrndup(buf, count, GFP_KERNEL);
	if (!copy)
		return -ENOMEM;
	freqs = kcalloc(nr_cpu_ids, sizeof(*freqs), GFP_KERNEL);
	if (!freqs) {
		kfree(copy);
		return -ENOMEM;
	}
	for_each_possible_cpu (cpu)
		freqs[cpu] =
			READ_ONCE(per_cpu(sync_info, cpu).input_boost_freq);
	cursor = strim(copy);
	if (!*cursor)
		goto out;
	if (!strchr(cursor, ':')) {
		if (kstrtouint(cursor, 10, &val) || val > 4000000U)
			goto out;
		for_each_possible_cpu (cpu)
			freqs[cpu] = val;
	} else {
		while ((token = strsep(&cursor, " \t\n"))) {
			if (!*token)
				continue;
			colon = strchr(token, ':');
			if (!colon)
				goto out;
			*colon++ = '\0';
			if (kstrtouint(token, 10, &cpu) || cpu >= nr_cpu_ids ||
			    !cpu_possible(cpu) || kstrtouint(colon, 10, &val) ||
			    val > 4000000U)
				goto out;
			freqs[cpu] = val;
		}
	}
	for_each_possible_cpu (cpu) {
		WRITE_ONCE(per_cpu(sync_info, cpu).input_boost_freq,
			   freqs[cpu]);
		enabled |= !!freqs[cpu];
	}
	WRITE_ONCE(input_boost_enabled, enabled);
	ret = count;
out:
	kfree(freqs);
	kfree(copy);
	return ret;
}

static ssize_t show_input_boost_freq(struct kobject *kobj,
				     struct kobj_attribute *attr, char *buf)
{
	int cnt = 0, cpu;
	struct cpu_sync *s;

	for_each_possible_cpu (cpu) {
		s = &per_cpu(sync_info, cpu);
		cnt += snprintf(buf + cnt, PAGE_SIZE - cnt, "%d:%u ", cpu,
				s->input_boost_freq);
	}
	cnt += snprintf(buf + cnt, PAGE_SIZE - cnt, "\n");
	return cnt;
}

cpu_boost_attr_rw(input_boost_freq);

static int boost_adjust_notify(struct notifier_block *nb, unsigned long event,
			       void *data)
{
	struct cpufreq_policy *policy = data;
	unsigned int cpu, floor = 0;

	if (event != CPUFREQ_ADJUST)
		return NOTIFY_DONE;
	for_each_cpu (cpu, policy->related_cpus)
		floor = max(floor,
			    READ_ONCE(per_cpu(sync_info, cpu).input_boost_min));
	/* A boost cannot raise an already imposed policy/thermal maximum. */
	floor = min(floor, policy->max);
	cpufreq_verify_within_limits(policy, floor, policy->max);
	return NOTIFY_OK;
}
static struct notifier_block boost_cpufreq_nb = {
	.notifier_call = boost_adjust_notify,
};

static void update_policy_online(void)
{
	struct cpumask remaining;
	unsigned int cpu;

	get_online_cpus();
	cpumask_copy(&remaining, cpu_online_mask);
	for_each_cpu (cpu, &remaining) {
		struct cpufreq_policy *policy = cpufreq_cpu_get(cpu);

		if (!policy)
			continue;
		cpumask_andnot(&remaining, &remaining, policy->related_cpus);
		cpufreq_update_policy(cpu);
		cpufreq_cpu_put(policy);
	}
	put_online_cpus();
}

/* Ordered worker: update hardware only when the requested floors change. */
static void mushroom_apply_boost(void)
{
	unsigned long flags, until, delay, now;
	unsigned int cpu, desired_sched;
	bool active, now_active, changed;
	int ret;

	for (;;) {
		spin_lock_irqsave(&input_boost_lock, flags);
		active = input_boost_until &&
			 time_before(jiffies, input_boost_until);
		spin_unlock_irqrestore(&input_boost_lock, flags);
		changed = false;
		for_each_possible_cpu (cpu) {
			struct cpu_sync *info = &per_cpu(sync_info, cpu);
			unsigned int floor =
				active ? max(READ_ONCE(info->input_boost_freq),
					     mushroom_cluster_floor(cpu)) :
					       0;
			if (floor != READ_ONCE(info->input_boost_min)) {
				WRITE_ONCE(info->input_boost_min, floor);
				changed = true;
			}
		}
		if (changed)
			update_policy_online();
		desired_sched = active ? READ_ONCE(sched_boost_on_input) : 0;
		if (desired_sched != active_sched_boost) {
			if (sched_boost_active) {
				sched_set_boost(0);
				sched_boost_active = false;
				active_sched_boost = 0;
			}
			if (desired_sched) {
				ret = sched_set_boost(desired_sched);
				if (!ret) {
					sched_boost_active = true;
					active_sched_boost = desired_sched;
				}
			}
		}
		spin_lock_irqsave(&input_boost_lock, flags);
		until = input_boost_until;
		now = jiffies;
		now_active = until && time_before(now, until);
		if (now_active != active) {
			spin_unlock_irqrestore(&input_boost_lock, flags);
			continue;
		}
		if (now_active) {
			delay = max_t(unsigned long, 1, until - now);
			mod_delayed_work(cpu_boost_wq, &input_boost_rem, delay);
		}
		spin_unlock_irqrestore(&input_boost_lock, flags);
		return;
	}
}

static void do_input_boost_rem(struct work_struct *work)
{
	mushroom_apply_boost();
}

static void do_input_boost(struct work_struct *work)
{
	mushroom_apply_boost();
}

static void cpuboost_input_event(struct input_handle *handle, unsigned int type,
				 unsigned int code, int value)
{
	unsigned long flags;
	u64 now;
	if (!READ_ONCE(input_boost_enabled) && !READ_ONCE(mushroom_enabled))
		return;
	/* One complete touch report or a key press/repeat, never each ABS axis. */
	if (!((type == EV_SYN && code == SYN_REPORT) ||
	      (type == EV_KEY && value > 0)))
		return;
	now = ktime_to_us(ktime_get());
	spin_lock_irqsave(&input_boost_lock, flags);
	if (now - last_input_time < MIN_INPUT_INTERVAL) {
		spin_unlock_irqrestore(&input_boost_lock, flags);
		return;
	}
	last_input_time = now;
	spin_unlock_irqrestore(&input_boost_lock, flags);
	mushroom_boost_pulse();
}

static int cpuboost_input_connect(struct input_handler *handler,
				  struct input_dev *dev,
				  const struct input_device_id *id)
{
	struct input_handle *handle;
	int error;

	handle = kzalloc(sizeof(struct input_handle), GFP_KERNEL);
	if (!handle)
		return -ENOMEM;

	handle->dev = dev;
	handle->handler = handler;
	handle->name = "cpufreq";

	error = input_register_handle(handle);
	if (error)
		goto err2;

	error = input_open_device(handle);
	if (error)
		goto err1;

	return 0;
err1:
	input_unregister_handle(handle);
err2:
	kfree(handle);
	return error;
}

static void cpuboost_input_disconnect(struct input_handle *handle)
{
	input_close_device(handle);
	input_unregister_handle(handle);
	kfree(handle);
}

static const struct input_device_id cpuboost_ids[] = {
	/* multi-touch touchscreen */
	{
		.flags = INPUT_DEVICE_ID_MATCH_EVBIT |
			 INPUT_DEVICE_ID_MATCH_ABSBIT,
		.evbit = { BIT_MASK(EV_ABS) },
		.absbit = { [BIT_WORD(ABS_MT_POSITION_X)] =
				    BIT_MASK(ABS_MT_POSITION_X) |
				    BIT_MASK(ABS_MT_POSITION_Y) },
	},
	/* touchpad */
	{
		.flags = INPUT_DEVICE_ID_MATCH_KEYBIT |
			 INPUT_DEVICE_ID_MATCH_ABSBIT,
		.keybit = { [BIT_WORD(BTN_TOUCH)] = BIT_MASK(BTN_TOUCH) },
		.absbit = { [BIT_WORD(ABS_X)] =
				    BIT_MASK(ABS_X) | BIT_MASK(ABS_Y) },
	},
	/* Keypad */
	{
		.flags = INPUT_DEVICE_ID_MATCH_EVBIT,
		.evbit = { BIT_MASK(EV_KEY) },
	},
	{},
};

static struct input_handler cpuboost_input_handler = {
	.event = cpuboost_input_event,
	.connect = cpuboost_input_connect,
	.disconnect = cpuboost_input_disconnect,
	.name = "cpu-boost",
	.id_table = cpuboost_ids,
};

struct kobject *cpu_boost_kobj;
int cpu_boost_init(void)
{
	int cpu, ret;
	struct cpu_sync *s;

	cpu_boost_wq = alloc_ordered_workqueue("cpuboost_wq", WQ_HIGHPRI);
	if (!cpu_boost_wq)
		return -EFAULT;

	INIT_WORK(&input_boost_work, do_input_boost);
	INIT_DELAYED_WORK(&input_boost_rem, do_input_boost_rem);

	for_each_possible_cpu (cpu) {
		s = &per_cpu(sync_info, cpu);
		s->cpu = cpu;
	}
	ret = cpufreq_register_notifier(&boost_cpufreq_nb,
					CPUFREQ_POLICY_NOTIFIER);
	if (ret) {
		destroy_workqueue(cpu_boost_wq);
		return ret;
	}

	cpu_boost_kobj =
		kobject_create_and_add("cpu_boost", &cpu_subsys.dev_root->kobj);
	if (!cpu_boost_kobj) {
		cpufreq_unregister_notifier(&boost_cpufreq_nb,
					    CPUFREQ_POLICY_NOTIFIER);
		destroy_workqueue(cpu_boost_wq);
		return -ENOMEM;
	}

	ret = sysfs_create_file(cpu_boost_kobj, &input_boost_ms_attr.attr);
	if (ret)
		pr_err("Failed to create input_boost_ms node: %d\n", ret);

	ret = sysfs_create_file(cpu_boost_kobj, &input_boost_freq_attr.attr);
	if (ret)
		pr_err("Failed to create input_boost_freq node: %d\n", ret);

	ret = sysfs_create_file(cpu_boost_kobj,
				&sched_boost_on_input_attr.attr);
	if (ret)
		pr_err("Failed to create sched_boost_on_input node: %d\n", ret);

	ret = input_register_handler(&cpuboost_input_handler);
	if (ret) {
		kobject_put(cpu_boost_kobj);
		cpufreq_unregister_notifier(&boost_cpufreq_nb,
					    CPUFREQ_POLICY_NOTIFIER);
		destroy_workqueue(cpu_boost_wq);
		return ret;
	}
	smp_store_release(&mushroom_boost_ready, true);
	return 0;
}
