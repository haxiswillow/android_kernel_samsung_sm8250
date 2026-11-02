#!/usr/bin/env python3
"""Execute the governor's real decision functions; not a phone FPS test."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / 'kernel/sched54/cpufreq_schedutil.c').read_text()


def function(signature):
    start = SOURCE.index(signature)
    pos = SOURCE.index('{', start)
    depth, end = 1, pos + 1
    while depth:
        depth += (SOURCE[end] == '{') - (SOURCE[end] == '}')
        end += 1
    return SOURCE[start:end]


def run(code):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / 'test.c').write_text(code)
        subprocess.run(['gcc', '-O2', '-Wall', '-Werror',
                        '-fsanitize=undefined', str(path / 'test.c'),
                        '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)


common = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint64_t u64;
typedef int64_t s64;
#define unlikely(x) (x)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define smp_mb() ((void)0)
#define smp_wmb() ((void)0)
#define NSEC_PER_USEC 1000L
struct cpufreq_policy {
    unsigned int cur, min, max, cpu;
    struct { unsigned int max_freq; } cpuinfo;
    bool fast_switch_enabled;
    void *governor_data;
};
struct sugov_policy {
    struct cpufreq_policy *policy;
    unsigned int next_freq, cached_raw_freq;
    u64 last_freq_update_time;
    s64 min_rate_limit_ns, up_rate_delay_ns, down_rate_delay_ns;
    bool limits_changed, need_freq_update;
    int update_lock, work_lock;
};
static bool can_update = true;
static bool cpufreq_this_cpu_can_update(struct cpufreq_policy *p) {
    return can_update;
}
static bool arch_scale_freq_invariant(void) { return true; }
#define trace_android_vh_map_util_freq(u,f,m,n) ((void)0)
#define trace_sugov_next_freq(c,u,m,f) ((void)0)
static unsigned int map_util_freq(unsigned long u, unsigned int f,
                                 unsigned long m) { return (f + f/4)*u/m; }
static unsigned int cpufreq_driver_resolve_freq(struct cpufreq_policy *p,
                                               unsigned int f) {
    f = ((f + 99)/100)*100;
    if (f < p->min) f = p->min;
    if (f > p->max) f = p->max;
    return f;
}
'''
decisions = '\n'.join(function(signature) for signature in (
    'static bool sugov_should_update_freq(',
    'static bool sugov_up_down_rate_limit(',
    'static bool sugov_update_next_freq(',
    'static unsigned int get_next_freq('))

run(common + decisions + r'''
int main(void) {
    struct cpufreq_policy policy = {.cur=300, .min=300, .max=1800,
                                   .cpuinfo={1800}};
    struct sugov_policy p = {.policy=&policy, .next_freq=300,
        .last_freq_update_time=1000000, .up_rate_delay_ns=250000,
        .down_rate_delay_ns=8000000, .min_rate_limit_ns=250000};
    unsigned int f;
    /* A rate-rejected high target must be retried, even if raw util repeats. */
    f = get_next_freq(&p, 700, 1024);
    assert(f==1600 && !sugov_update_next_freq(&p,1000100,f));
    assert(!p.cached_raw_freq && p.next_freq==300);
    assert(!sugov_should_update_freq(&p,1249999));
    assert(sugov_should_update_freq(&p,1250000));
    f = get_next_freq(&p,700,1024);
    assert(sugov_update_next_freq(&p,1250000,f) && p.next_freq==1600);
    /* Thermal cap must apply inside the 8 ms downward delay. */
    policy.max=600; p.limits_changed=true;
    assert(sugov_should_update_freq(&p,1250100));
    f=get_next_freq(&p,700,1024);
    assert(f==600 && p.need_freq_update);
    assert(sugov_update_next_freq(&p,1250100,f));
    assert(!p.need_freq_update && p.next_freq==600);
    /* A newly raised policy minimum must also bypass the upward delay. */
    policy.max=1800; policy.min=900; p.limits_changed=true;
    assert(sugov_should_update_freq(&p,1250200));
    f=get_next_freq(&p,0,1024);
    assert(f==900 && sugov_update_next_freq(&p,1250200,f));
    /* A forced same target reaches commit once, then resumes rate limiting. */
    p.limits_changed=true;
    assert(sugov_should_update_freq(&p,1250300));
    f=get_next_freq(&p,0,1024);
    assert(p.need_freq_update && sugov_update_next_freq(&p,1250300,f));
    assert(!p.need_freq_update && !sugov_update_next_freq(&p,1250400,f));
    /* Ordinary load can fall: this is not a permanent performance floor. */
    policy.min=300; p.limits_changed=true;
    assert(sugov_should_update_freq(&p,1250400));
    f=get_next_freq(&p,700,1024);
    assert(sugov_update_next_freq(&p,1250400,f) && p.next_freq==1600);
    f=get_next_freq(&p,0,1024);
    assert(!sugov_update_next_freq(&p,9250399,f));
    assert(sugov_update_next_freq(&p,9250400,f) && p.next_freq==300);
    can_update=false; p.limits_changed=true;
    assert(!sugov_should_update_freq(&p,9999999) && p.limits_changed);
    puts("PASS schedutil: repeated-target retry, limit/cache lifetime, immediate caps/floors, dynamic clocks");
}
''')

# Exercise the actual fast-limit callback as well as the following util update.
run(common + decisions + r'''
static unsigned long clock_now=1000100;
static int fast_updates, slow_updates;
#define raw_spin_lock_irqsave(l,f) ((f)=0)
#define raw_spin_unlock_irqrestore(l,f) ((void)(f))
#define mutex_lock(l) ((void)0)
#define mutex_unlock(l) ((void)0)
static unsigned long ktime_get_ns(void) { return clock_now; }
static void sugov_track_cycles(struct sugov_policy *p,unsigned int f,u64 t) {}
static void cpufreq_policy_apply_limits(struct cpufreq_policy *p) { slow_updates++; }
static void sugov_fast_switch(struct sugov_policy *p,u64 t,unsigned int f) {
    if(sugov_update_next_freq(p,t,f)) { p->policy->cur=f; fast_updates++; }
}
''' + function('static void sugov_limits(') + r'''
int main(void) {
    struct cpufreq_policy policy={.cur=1800,.min=300,.max=600,
        .fast_switch_enabled=true,.cpuinfo={1800}};
    struct sugov_policy p={.policy=&policy,.next_freq=1800,
        .last_freq_update_time=1000000,.up_rate_delay_ns=250000,
        .down_rate_delay_ns=8000000};
    policy.governor_data=&p;
    sugov_limits(&policy);
    assert(fast_updates==1 && policy.cur==600 && p.limits_changed);
    assert(sugov_should_update_freq(&p,clock_now));
    unsigned int f=get_next_freq(&p,900,1024);
    assert(f==600 && sugov_update_next_freq(&p,clock_now,f));
    policy.fast_switch_enabled=false; sugov_limits(&policy);
    assert(slow_updates==1 && p.limits_changed);
    puts("PASS schedutil: real fast/slow limits callback and next util refresh");
}
''')

# Shared policies must notice a new DL reservation before overwriting bw_dl.
shared_prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
typedef uint64_t u64;
struct update_util_data {int unused;};
struct cpufreq_policy { bool fast_switch_enabled; unsigned int cur; };
struct sugov_tunables {bool pl;unsigned int hispeed_freq,rtg_boost_freq;};
struct sugov_policy {struct cpufreq_policy *policy;struct sugov_tunables *tunables;
    unsigned long max,hispeed_util,rtg_boost_util,avg_cap;int update_lock;
    bool limits_changed,need_freq_update;};
struct sugov_cpu {struct update_util_data update_util;struct sugov_policy *sg_policy;
    unsigned int cpu,flags;unsigned long util,max,bw_dl;u64 last_update;
    struct {u64 ws;unsigned long nl,pl;bool rtgb_active;} walt_load;};
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define SCHED_CPUFREQ_PL 1
#define SCHED_CPUFREQ_CONTINUE 2
#define WRITE_ONCE(x,v) ((x)=(v))
#define raw_spin_lock(l) ((void)0)
#define raw_spin_unlock(l) ((void)0)
#define trace_sugov_util_update(...) ((void)0)
static unsigned long dl_bw=100;
static int commits;
static int cpu_rq(int cpu){return cpu;}
static unsigned long cpu_bw_dl(int rq){return dl_bw;}
static unsigned long sugov_get_util(struct sugov_cpu *cpu){cpu->bw_dl=dl_bw;cpu->max=1024;return 400;}
static unsigned long target_util(struct sugov_policy *p,unsigned int f){return f;}
static void sugov_iowait_boost(struct sugov_cpu *c,u64 t,unsigned int f){}
static void sugov_calc_avg_cap(struct sugov_policy *p,u64 w,unsigned int f){}
static bool sugov_should_update_freq(struct sugov_policy *p,u64 t){
    if(!p->limits_changed)return false;
    p->limits_changed=false;p->need_freq_update=true;return true;
}
static unsigned int sugov_next_freq_shared(struct sugov_cpu *c,u64 t){return 1000;}
static void sugov_fast_switch(struct sugov_policy *p,u64 t,unsigned int f){commits++;p->need_freq_update=false;}
static void sugov_deferred_update(struct sugov_policy *p,u64 t,unsigned int f){sugov_fast_switch(p,t,f);}
'''
run(shared_prefix + function('static inline void ignore_dl_rate_limit(') +
    function('static void\nsugov_update_shared(') + r'''
int main(void){
    struct cpufreq_policy policy={.fast_switch_enabled=true};
    struct sugov_tunables tunables={0};
    struct sugov_policy p={.policy=&policy,.tunables=&tunables};
    struct sugov_cpu cpu={.sg_policy=&p,.bw_dl=10};
    sugov_update_shared(&cpu.update_util,1000,0);
    assert(commits==1 && cpu.bw_dl==100);
    sugov_update_shared(&cpu.update_util,1100,0);assert(commits==1);
    dl_bw=200;sugov_update_shared(&cpu.update_util,1200,SCHED_CPUFREQ_CONTINUE);
    assert(commits==1 && p.limits_changed);
    sugov_update_shared(&cpu.update_util,1300,0);assert(commits==2);
    puts("PASS schedutil: shared-policy DL increase survives load refresh and CONTINUE batching");
}
''')

run(r'''
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#include <stdio.h>
typedef int64_t s64;
#define NSEC_PER_USEC 1000L
#define min(a,b) ((a)<(b)?(a):(b))
#define mutex_lock(x) ((void)0)
#define mutex_unlock(x) ((void)0)
struct sugov_tunables {bool pl;unsigned int hispeed_load,rtg_boost_freq,hispeed_freq,up_rate_limit_us,down_rate_limit_us;};
struct sugov_policy {struct sugov_tunables *tunables;s64 up_rate_delay_ns,down_rate_delay_ns,min_rate_limit_ns;};
struct cpufreq_policy {struct sugov_policy *governor_data;unsigned int cpu;};
static struct sugov_tunables cached_value={true,87,1000000,1400000,250,8000};
#define per_cpu(n,c) (&cached_value)
''' + function('static void update_min_rate_limit_ns(') +
    function('static void sugov_tunables_restore(') + r'''
int main(void){struct sugov_tunables tunables={0};struct sugov_policy p={.tunables=&tunables};struct cpufreq_policy policy={&p,0};
    sugov_tunables_restore(&policy);
    assert(p.up_rate_delay_ns==250000 && p.down_rate_delay_ns==8000000 && p.min_rate_limit_ns==250000);
    assert(tunables.hispeed_freq==1400000 && tunables.rtg_boost_freq==1000000);
    cached_value.up_rate_limit_us=4294967295U;sugov_tunables_restore(&policy);
    assert(p.up_rate_delay_ns==4294967295000LL);
    puts("PASS schedutil: saved tunables restore microseconds as nanoseconds without truncation");}
''')

init = function('static int sugov_init(')
assert init.index('tunables->hispeed_freq = tunables->rtg_boost_freq;') < init.index('sugov_tunables_restore(policy);')
assert 'tunables->up_rate_limit_us = 250;' in init
assert 'tunables->down_rate_limit_us = 8000;' in init
print('PASS schedutil: custom hispeed survives reinit; 250 us / 8 ms initial defaults')
