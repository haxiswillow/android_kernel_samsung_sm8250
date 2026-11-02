// SPDX-License-Identifier: GPL-2.0-only
/* KCAL-compatible RGB/saturation control for the Samsung per-plane PCC path. */
#include <linux/atomic.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/math64.h>
#include <linux/platform_device.h>
#include <linux/seqlock.h>
#include <linux/string.h>
#include <linux/sysfs.h>
#include "mushroom_kcal.h"

#define KCAL_ONE 32768
#define KCAL_MASK 0x3ffff

static DEFINE_SEQLOCK(kcal_lock);
static atomic_t kcal_generation = ATOMIC_INIT(1);
static int kcal_rgb[3] = { 256, 256, 256 };
static int kcal_min = 35;
static int kcal_sat = 255;
static int kcal_val = 255;
static int kcal_cont = 255;
static int kcal_hue;
static bool kcal_invert;
static bool kcal_enabled = true;
static bool kcal_active;
static s32 kcal_matrix[9] = {
	KCAL_ONE, 0, 0, 0, KCAL_ONE, 0, 0, 0, KCAL_ONE
};

/* Q15 sine for one quadrant; full hue period is 1536. */
static const s32 kcal_sine_quarter[385] = {
	0, 134, 268, 402, 536, 670, 804, 938, 1072, 1206, 1340, 1474,
	1608, 1742, 1876, 2009, 2143, 2277, 2411, 2544, 2678, 2811, 2945, 3078,
	3212, 3345, 3479, 3612, 3745, 3878, 4011, 4144, 4277, 4410, 4543, 4675,
	4808, 4941, 5073, 5205, 5338, 5470, 5602, 5734, 5866, 5998, 6130, 6261,
	6393, 6524, 6655, 6787, 6918, 7049, 7180, 7310, 7441, 7571, 7702, 7832,
	7962, 8092, 8222, 8351, 8481, 8610, 8740, 8869, 8998, 9127, 9255, 9384,
	9512, 9640, 9768, 9896, 10024, 10151, 10279, 10406, 10533, 10660, 10786, 10913,
	11039, 11165, 11291, 11417, 11543, 11668, 11793, 11918, 12043, 12167, 12292, 12416,
	12540, 12664, 12787, 12910, 13033, 13156, 13279, 13401, 13524, 13646, 13767, 13889,
	14010, 14131, 14252, 14373, 14493, 14613, 14733, 14852, 14972, 15091, 15210, 15328,
	15447, 15565, 15683, 15800, 15917, 16035, 16151, 16268, 16384, 16500, 16616, 16731,
	16846, 16961, 17075, 17190, 17304, 17417, 17531, 17644, 17757, 17869, 17981, 18093,
	18205, 18316, 18427, 18538, 18648, 18758, 18868, 18978, 19087, 19195, 19304, 19412,
	19520, 19627, 19735, 19841, 19948, 20054, 20160, 20265, 20371, 20475, 20580, 20684,
	20788, 20891, 20994, 21097, 21199, 21301, 21403, 21504, 21605, 21706, 21806, 21906,
	22006, 22105, 22204, 22302, 22400, 22498, 22595, 22692, 22788, 22884, 22980, 23075,
	23170, 23265, 23359, 23453, 23546, 23640, 23732, 23824, 23916, 24008, 24099, 24189,
	24279, 24369, 24459, 24548, 24636, 24724, 24812, 24900, 24986, 25073, 25159, 25245,
	25330, 25415, 25499, 25583, 25667, 25750, 25833, 25915, 25997, 26078, 26159, 26239,
	26320, 26399, 26478, 26557, 26635, 26713, 26791, 26868, 26944, 27020, 27096, 27171,
	27246, 27320, 27394, 27467, 27540, 27612, 27684, 27756, 27827, 27897, 27967, 28037,
	28106, 28175, 28243, 28311, 28378, 28445, 28511, 28577, 28642, 28707, 28771, 28835,
	28899, 28962, 29024, 29086, 29148, 29209, 29269, 29329, 29389, 29448, 29506, 29564,
	29622, 29679, 29736, 29792, 29847, 29902, 29957, 30011, 30064, 30118, 30170, 30222,
	30274, 30325, 30375, 30425, 30475, 30524, 30572, 30620, 30668, 30715, 30761, 30807,
	30853, 30897, 30942, 30986, 31029, 31072, 31114, 31156, 31197, 31238, 31278, 31318,
	31357, 31396, 31434, 31471, 31508, 31545, 31581, 31617, 31651, 31686, 31720, 31753,
	31786, 31818, 31850, 31881, 31912, 31942, 31972, 32001, 32029, 32058, 32085, 32112,
	32138, 32164, 32190, 32214, 32239, 32262, 32286, 32308, 32330, 32352, 32373, 32393,
	32413, 32433, 32452, 32470, 32488, 32505, 32522, 32538, 32553, 32568, 32583, 32597,
	32610, 32623, 32635, 32647, 32658, 32669, 32679, 32689, 32698, 32706, 32714, 32722,
	32729, 32735, 32741, 32746, 32750, 32755, 32758, 32761, 32764, 32766, 32767, 32768,
	32768,
};

static s32 kcal_sin(unsigned int angle)
{
	angle %= 1536;
	if (angle <= 384)
		return kcal_sine_quarter[angle];
	if (angle <= 768)
		return kcal_sine_quarter[768 - angle];
	if (angle <= 1152)
		return -kcal_sine_quarter[angle - 768];
	return -kcal_sine_quarter[1536 - angle];
}

/* Writer lock held. HSV controls use a bounded RGB matrix approximation. */
static void kcal_recalculate(void)
{
	static const int luma[3] = { 6966, 23436, 2366 };
	static const int hue_sine[9] = {
		-6966, -23436, 30402, 4686, 4588, -9274,
		-25798, 23436, 2362
	};
	s32 hue[9], saturation[9];
	s32 cosine = kcal_sin(kcal_hue + 384);
	s32 sine = kcal_sin(kcal_hue);
	int sat = kcal_sat - 128;
	int row, col, k;

	kcal_active = kcal_enabled && (kcal_sat != 255 || kcal_val != 255 || (kcal_hue % 1536) ||
		kcal_rgb[0] != 256 || kcal_rgb[1] != 256 || kcal_rgb[2] != 256);
	for (row = 0; row < 3; row++) {
		for (col = 0; col < 3; col++) {
			int index = row * 3 + col;
			s64 identity = row == col ? KCAL_ONE : 0;

			hue[index] = luma[col] + div_s64(
				(s64)cosine * (identity - luma[col]) +
				(s64)sine * hue_sine[index], KCAL_ONE);
			saturation[index] = div_s64(
				(s64)(127 - sat) * luma[col] +
				(s64)sat * identity, 127);
		}
	}
	for (row = 0; row < 3; row++) {
		int gain = max(kcal_rgb[row], kcal_min);
		for (col = 0; col < 3; col++) {
			s64 sum = 0;

			for (k = 0; k < 3; k++)
				sum += (s64)saturation[row * 3 + k] * hue[k * 3 + col];
			sum = div_s64(sum, KCAL_ONE);
			sum = div_s64(sum * kcal_val, 255);
			sum = div_s64(sum * gain, 256);
			kcal_matrix[row * 3 + col] = (s32)sum;
		}
	}
	atomic_inc(&kcal_generation);
}

u32 mushroom_kcal_generation(void)
{
	return (u32)atomic_read(&kcal_generation);
}

bool mushroom_kcal_apply(u32 coeff[9], u32 *generation)
{
	s32 matrix[9];
	u32 original[9];
	unsigned int seq;
	bool active;
	int row, col, k;

	/* No mutex or allocation in the atomic display commit path. */
	do {
		seq = read_seqbegin(&kcal_lock);
		active = kcal_active;
		memcpy(matrix, kcal_matrix, sizeof(matrix));
		*generation = (u32)atomic_read(&kcal_generation);
	} while (read_seqretry(&kcal_lock, seq));
	if (!active)
		return false;

	memcpy(original, coeff, sizeof(original));
	for (row = 0; row < 3; row++) {
		for (col = 0; col < 3; col++) {
			s64 sum = 0;

			for (k = 0; k < 3; k++)
				sum += (s64)matrix[row * 3 + k] *
					sign_extend32(original[k * 3 + col], 17);
			sum = div_s64(sum, KCAL_ONE);
			sum = clamp_t(s64, sum, -131072, 131071);
			coeff[row * 3 + col] = (u32)sum & KCAL_MASK;
		}
	}
	return true;
}

static ssize_t kcal_show(struct device *dev, struct device_attribute *attr,
		char *buf)
{
	unsigned int seq;
	int rgb[3];

	do {
		seq = read_seqbegin(&kcal_lock);
		memcpy(rgb, kcal_rgb, sizeof(rgb));
	} while (read_seqretry(&kcal_lock, seq));
	return scnprintf(buf, PAGE_SIZE, "%d %d %d\n", rgb[0], rgb[1], rgb[2]);
}

static ssize_t kcal_store(struct device *dev, struct device_attribute *attr,
		const char *buf, size_t count)
{
	unsigned long flags;
	int rgb[3];
	char extra;

	if (sscanf(buf, "%d %d %d %c", &rgb[0], &rgb[1], &rgb[2], &extra) != 3)
		return -EINVAL;
	if (rgb[0] < 0 || rgb[0] > 256 || rgb[1] < 0 || rgb[1] > 256 ||
	    rgb[2] < 0 || rgb[2] > 256)
		return -ERANGE;
	write_seqlock_irqsave(&kcal_lock, flags);
	memcpy(kcal_rgb, rgb, sizeof(rgb));
	kcal_recalculate();
	write_sequnlock_irqrestore(&kcal_lock, flags);
	return count;
}

static int *kcal_integer(struct device_attribute *attr)
{
	if (!strcmp(attr->attr.name, "kcal_min"))
		return &kcal_min;
	if (!strcmp(attr->attr.name, "kcal_hue"))
		return &kcal_hue;
	if (!strcmp(attr->attr.name, "kcal_val"))
		return &kcal_val;
	if (!strcmp(attr->attr.name, "kcal_cont"))
		return &kcal_cont;
	return &kcal_sat;
}

static ssize_t kcal_value_show(struct device *dev,
		struct device_attribute *attr, char *buf)
{
	unsigned int seq;
	int value;

	do {
		seq = read_seqbegin(&kcal_lock);
		if (!strcmp(attr->attr.name, "kcal_enable"))
			value = kcal_enabled;
		else if (!strcmp(attr->attr.name, "kcal_invert"))
			value = kcal_invert;
		else
			value = *kcal_integer(attr);
	} while (read_seqretry(&kcal_lock, seq));
	return scnprintf(buf, PAGE_SIZE, "%d\n", value);
}

static ssize_t kcal_value_store(struct device *dev,
		struct device_attribute *attr, const char *buf, size_t count)
{
	unsigned long flags;
	int value, minimum = 128, maximum = 383;
	bool enable = !strcmp(attr->attr.name, "kcal_enable");
	bool invert = !strcmp(attr->attr.name, "kcal_invert");
	int *target = kcal_integer(attr);

	if (kstrtoint(buf, 10, &value))
		return -EINVAL;
	if (enable || invert) {
		minimum = 0;
		maximum = 1;
	} else if (target == &kcal_min || target == &kcal_hue) {
		minimum = 0;
		maximum = target == &kcal_min ? 256 : 1536;
	}
	if (value < minimum || value > maximum)
		return -ERANGE;
	/* DGM CSC is matrix-only: never claim support for missing offsets. */
	if ((invert && value) || (target == &kcal_cont && value != 255))
		return -EOPNOTSUPP;
	write_seqlock_irqsave(&kcal_lock, flags);
	if (enable)
		kcal_enabled = value;
	else if (invert)
		kcal_invert = value;
	else
		*target = value;
	kcal_recalculate();
	write_sequnlock_irqrestore(&kcal_lock, flags);
	return count;
}

static DEVICE_ATTR_RW(kcal);
static DEVICE_ATTR(kcal_enable, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_min, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_sat, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_val, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_cont, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_hue, 0644, kcal_value_show, kcal_value_store);
static DEVICE_ATTR(kcal_invert, 0644, kcal_value_show, kcal_value_store);

static struct attribute *kcal_attrs[] = {
	&dev_attr_kcal.attr, &dev_attr_kcal_enable.attr,
	&dev_attr_kcal_min.attr, &dev_attr_kcal_sat.attr,
	&dev_attr_kcal_val.attr, &dev_attr_kcal_cont.attr,
	&dev_attr_kcal_hue.attr, &dev_attr_kcal_invert.attr, NULL
};
static const struct attribute_group kcal_group = { .attrs = kcal_attrs };

static int __init mushroom_kcal_init(void)
{
	struct platform_device *pdev;
	int ret;

	pdev = platform_device_register_simple("kcal_ctrl", 0, NULL, 0);
	if (IS_ERR(pdev))
		return PTR_ERR(pdev);
	ret = sysfs_create_group(&pdev->dev.kobj, &kcal_group);
	if (ret)
		platform_device_unregister(pdev);
	return ret;
}
late_initcall(mushroom_kcal_init);
