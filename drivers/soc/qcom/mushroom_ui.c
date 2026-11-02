// SPDX-License-Identifier: GPL-2.0-only
/* Bounded Android UI hints and active-only bandwidth votes; no clock OC. */
#include <linux/atomic.h>
#include <linux/init.h>
#include <linux/input.h>
#include <linux/jiffies.h>
#include <linux/kernel.h>
#include <linux/kobject.h>
#include <linux/msm-bus.h>
#include <linux/msm-bus-board.h>
#include <linux/mushroom_ui.h>
#include <linux/slab.h>
#include <linux/spinlock.h>
#include <linux/sysfs.h>
#include <linux/workqueue.h>

static unsigned int enabled = 1;
static unsigned int top_app_boost = 20, foreground_boost = 10;
static unsigned int action_top_app_boost = 35, action_foreground_boost = 15;
static unsigned int boost_ms = 120, cooldown_ms = 300, ddr_vote_mhz = 681;
static unsigned long expires, next_action;
static bool ready;
static DEFINE_SPINLOCK(action_lock);
static atomic_t accepted = ATOMIC_INIT(0);
static int last_start_rc, last_release_rc;
static u32 bus_handle;
static struct workqueue_struct *ui_wq;
static struct work_struct action_work;
static struct delayed_work release_work;

#define UI_BW_VECTOR(mhz) { .src = MSM_BUS_MASTER_AMPSS_M0, \
	.dst = MSM_BUS_SLAVE_EBI_CH0, .ab = 0, .ib = (u64)(mhz) * 4000000 }
static struct msm_bus_vectors vectors[] = {
	UI_BW_VECTOR(0), UI_BW_VECTOR(451), UI_BW_VECTOR(547), UI_BW_VECTOR(681)
};
static struct msm_bus_paths paths[] = {
	{ 1, &vectors[0] }, { 1, &vectors[1] },
	{ 1, &vectors[2] }, { 1, &vectors[3] }
};
static struct msm_bus_scale_pdata bus_data = {
	.name = "mushroom_ui", .usecase = paths,
	.num_usecases = ARRAY_SIZE(paths), .active_only = 1,
};

int mushroom_ui_boost(unsigned int class)
{
	bool active;
	unsigned long end;

	if (!READ_ONCE(enabled))
		return 0;
	end = READ_ONCE(expires);
	active = end && time_before(jiffies, end);
	if (class == MUSHROOM_UI_TOP_APP)
		return active ? READ_ONCE(action_top_app_boost) : READ_ONCE(top_app_boost);
	if (class == MUSHROOM_UI_FOREGROUND)
		return active ? READ_ONCE(action_foreground_boost) : READ_ONCE(foreground_boost);
	return 0;
}

static void release_action(struct work_struct *work)
{
	WRITE_ONCE(expires, 0);
	if (bus_handle)
		WRITE_ONCE(last_release_rc, msm_bus_scale_client_update_request(bus_handle, 0));
}

static void start_action(struct work_struct *work)
{
	unsigned int vote = READ_ONCE(ddr_vote_mhz), index = 0;
	unsigned int duration = READ_ONCE(boost_ms);

	if (!READ_ONCE(enabled))
		return;
	if (vote == 451)
		index = 1;
	else if (vote == 547)
		index = 2;
	else if (vote == 681)
		index = 3;
	WRITE_ONCE(expires, jiffies + msecs_to_jiffies(duration));
	WRITE_ONCE(last_start_rc, bus_handle ?
		msm_bus_scale_client_update_request(bus_handle, index) : -ENODEV);
	mod_delayed_work(ui_wq, &release_work, msecs_to_jiffies(duration));
}

/* May be called under cpuset or input locks: no allocation, sleep or bus call. */
void mushroom_ui_action(void)
{
	unsigned long flags, now = jiffies;

	if (!smp_load_acquire(&ready) || !READ_ONCE(enabled))
		return;
	spin_lock_irqsave(&action_lock, flags);
	if (next_action && time_before(now, next_action)) {
		spin_unlock_irqrestore(&action_lock, flags);
		return;
	}
	next_action = now + msecs_to_jiffies(READ_ONCE(cooldown_ms));
	atomic_inc(&accepted);
	queue_work(ui_wq, &action_work);
	spin_unlock_irqrestore(&action_lock, flags);
}

static unsigned int *setting(const char *name)
{
#define UI_SETTING(n) if (!strcmp(name, #n)) return &n
	UI_SETTING(enabled);
	UI_SETTING(top_app_boost);
	UI_SETTING(foreground_boost);
	UI_SETTING(action_top_app_boost);
	UI_SETTING(action_foreground_boost);
	UI_SETTING(boost_ms);
	UI_SETTING(cooldown_ms);
	UI_SETTING(ddr_vote_mhz);
#undef UI_SETTING
	return NULL;
}

static ssize_t value_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	return scnprintf(buf, PAGE_SIZE, "%u\n", READ_ONCE(*setting(attr->attr.name)));
}

static ssize_t value_store(struct kobject *kobj, struct kobj_attribute *attr,
		const char *buf, size_t count)
{
	unsigned int value, *target = setting(attr->attr.name);
	if (kstrtouint(buf, 10, &value))
		return -EINVAL;
	if ((target == &enabled && value > 1) ||
	    (target == &boost_ms && (value < 20 || value > 200)) ||
	    (target == &cooldown_ms && (value < 250 || value > 2000)) ||
	    (target == &ddr_vote_mhz && value != 0 && value != 451 && value != 547 && value != 681) ||
	    (target != &enabled && target != &boost_ms && target != &cooldown_ms &&
	     target != &ddr_vote_mhz && value > 40))
		return -ERANGE;
	WRITE_ONCE(*target, value);
	if (target == &enabled && !value)
		mod_delayed_work(ui_wq, &release_work, 0);
	return count;
}

static ssize_t action_store(struct kobject *kobj, struct kobj_attribute *attr,
		const char *buf, size_t count)
{
	if (!sysfs_streq(buf, "launch") && !sysfs_streq(buf, "back") &&
	    !sysfs_streq(buf, "recents") && !sysfs_streq(buf, "shade"))
		return -EINVAL;
	mushroom_ui_action();
	return count;
}

static ssize_t stats_show(struct kobject *kobj, struct kobj_attribute *attr, char *buf)
{
	unsigned long end = READ_ONCE(expires);
	return scnprintf(buf, PAGE_SIZE, "accepted=%d active=%d bus_available=%d last_start_rc=%d last_release_rc=%d\n",
		atomic_read(&accepted), end && time_before(jiffies, end), !!bus_handle,
		READ_ONCE(last_start_rc), READ_ONCE(last_release_rc));
}

#define UI_ATTR(n) static struct kobj_attribute n##_attr = __ATTR(n, 0644, value_show, value_store)
UI_ATTR(enabled);
UI_ATTR(top_app_boost);
UI_ATTR(foreground_boost);
UI_ATTR(action_top_app_boost);
UI_ATTR(action_foreground_boost);
UI_ATTR(boost_ms);
UI_ATTR(cooldown_ms);
UI_ATTR(ddr_vote_mhz);
static struct kobj_attribute action_attr = __ATTR(action, 0200, NULL, action_store);
static struct kobj_attribute stats_attr = __ATTR(stats, 0444, stats_show, NULL);
static struct attribute *ui_attrs[] = {
	&enabled_attr.attr, &top_app_boost_attr.attr, &foreground_boost_attr.attr,
	&action_top_app_boost_attr.attr, &action_foreground_boost_attr.attr,
	&boost_ms_attr.attr, &cooldown_ms_attr.attr, &ddr_vote_mhz_attr.attr,
	&action_attr.attr, &stats_attr.attr, NULL
};
static const struct attribute_group ui_group = { .attrs = ui_attrs };

static void key_event(struct input_handle *handle, unsigned int type,
		unsigned int code, int value)
{
	if (type == EV_KEY && value == 1 &&
	    (code == KEY_BACK || code == KEY_HOME || code == KEY_APPSELECT))
		mushroom_ui_action();
}

static int key_connect(struct input_handler *handler, struct input_dev *dev,
		const struct input_device_id *id)
{
	struct input_handle *handle = kzalloc(sizeof(*handle), GFP_KERNEL);
	int ret;
	if (!handle)
		return -ENOMEM;
	handle->dev = dev;
	handle->handler = handler;
	handle->name = "mushroom_ui";
	ret = input_register_handle(handle);
	if (ret)
		goto free;
	ret = input_open_device(handle);
	if (!ret)
		return 0;
	input_unregister_handle(handle);
free:
	kfree(handle);
	return ret;
}

static void key_disconnect(struct input_handle *handle)
{
	input_close_device(handle);
	input_unregister_handle(handle);
	kfree(handle);
}

#define UI_KEY_ID(key) { .flags = INPUT_DEVICE_ID_MATCH_KEYBIT, \
	.keybit = { [BIT_WORD(key)] = BIT_MASK(key) } }
static const struct input_device_id key_ids[] = {
	UI_KEY_ID(KEY_BACK), UI_KEY_ID(KEY_HOME), UI_KEY_ID(KEY_APPSELECT), { }
};
static struct input_handler key_handler = {
	.event = key_event, .connect = key_connect, .disconnect = key_disconnect,
	.name = "mushroom_ui", .id_table = key_ids,
};

static int __init mushroom_ui_init(void)
{
	struct kobject *kobj;
	int ret;
	ui_wq = alloc_ordered_workqueue("mushroom_ui", WQ_HIGHPRI);
	if (!ui_wq) {
		WRITE_ONCE(enabled, 0);
		return -ENOMEM;
	}
	INIT_WORK(&action_work, start_action);
	INIT_DELAYED_WORK(&release_work, release_action);
	bus_handle = msm_bus_scale_register_client(&bus_data);
	kobj = kobject_create_and_add("mushroom_ui", kernel_kobj);
	if (!kobj) {
		ret = -ENOMEM;
		goto free;
	}
	ret = sysfs_create_group(kobj, &ui_group);
	if (ret) {
		kobject_put(kobj);
		goto free;
	}
	smp_store_release(&ready, true);
	ret = input_register_handler(&key_handler);
	if (ret)
		pr_warn("Mushroom: navigation input unavailable (%d); cgroup/action hooks remain\n", ret);
	if (!bus_handle)
		pr_warn("Mushroom: DDR vote unavailable; scheduling hints remain\n");
	return 0;
free:
	if (bus_handle)
		msm_bus_scale_unregister_client(bus_handle);
	destroy_workqueue(ui_wq);
	WRITE_ONCE(enabled, 0);
	return ret;
}
late_initcall(mushroom_ui_init);
