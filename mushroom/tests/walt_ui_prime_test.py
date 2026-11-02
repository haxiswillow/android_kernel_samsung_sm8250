#!/usr/bin/env python3
"""Compile actual WALT UI hint/index selection with controlled CPU states."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


fair = (ROOT / 'kernel/sched54/fair.c').read_text()
hint = function(fair, 'static bool mushroom_ui_prime_idle(')
indices = function(fair, 'static void walt_get_indicies(')
header = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#define READ_ONCE(x) (x)
#define smp_load_acquire(p) (*(p))
#define min(a,b) ((a)<(b)?(a):(b))
#define UCLAMP_MAX 1
#define TASK_BOOST_ON_MID 1
#define TASK_BOOST_ON_MAX 2
#define TASK_BOOST_STRICT_MAX 3
#define SCHED_BOOST_NONE 0
#define SCHED_BOOST_ON_BIG 1
struct cpumask { unsigned int bits; };
typedef struct cpumask cpumask_t;
static unsigned int cpumask_weight(const cpumask_t *p) { return __builtin_popcount(p->bits); }
static bool cpumask_empty(const cpumask_t *p) {return !p->bits;}
static unsigned int cpumask_first(const cpumask_t *p) { assert(p->bits);return __builtin_ctz(p->bits); }
#define for_each_cpu_and(c,a,b) for(c=0;c<8;c++) if((a)->bits & (b)->bits & (1U<<(c)))
struct task_struct {const cpumask_t *cpus_ptr;unsigned int min,max;bool latency,skip_min;int policy;unsigned int fits;};
static cpumask_t all={255},no_prime={127},little={15};
static cpumask_t rows[3][3]={{{15},{112},{128}},{{112},{128},{15}},{{128},{112},{15}}};
static cpumask_t *row_ptr[3]={rows[0],rows[1],rows[2]};
static cpumask_t **cpu_array=row_ptr;
static int num_sched_clusters=3;
static unsigned int sysctl_mushroom_ui_prime=1;
struct cpu_state {bool active,isolated,idle,reserved,irq;unsigned long original,available,thermal;};
static struct cpu_state cpus[8];
static bool full_throttle;
static unsigned long capacity_orig_of(int c) {return cpus[c].original;}
static unsigned long capacity_of(int c) {return cpus[c].available;}
static unsigned long thermal_cap(int c) {return cpus[c].thermal;}
static bool cpu_active(int c) {return cpus[c].active;}
static bool cpu_isolated(int c) {return cpus[c].isolated;}
static bool idle_cpu(int c) {return cpus[c].idle;}
static bool is_reserved(int c) {return cpus[c].reserved;}
static bool sched_cpu_high_irqload(int c) {return cpus[c].irq;}
static bool uclamp_latency_sensitive(struct task_struct *p) {return p->latency;}
static bool uclamp_boosted(struct task_struct *p) {return p->min>0;}
static unsigned long uclamp_eff_value(struct task_struct *p,int id) {assert(id==UCLAMP_MAX);return p->max;}
static bool is_full_throttle_boost(void) {return full_throttle;}
static int task_boost_policy(struct task_struct *p) {return p->policy;}
static bool walt_task_skip_min_cpu(struct task_struct *p) {return p->skip_min;}
static bool task_demand_fits(struct task_struct *p,int c) {return !!(p->fits & (1U<<c));}
'''
main = r'''
static void reset(struct task_struct *p) {
 *p=(struct task_struct){&all,204,1024,true,false,SCHED_BOOST_NONE,255};
 for(int c=0;c<8;c++){
  unsigned long capacity=c<4?350:c<7?850:1024;
  cpus[c]=(struct cpu_state){true,false,true,false,false,capacity,capacity,capacity};
 }
 sysctl_mushroom_ui_prime=1;num_sched_clusters=3;cpu_array=row_ptr;
 rows[2][0].bits=128;full_throttle=false;
}
static void expect(struct task_struct *p,int boost,int order,int end){
 int got_order=-1,got_end=-1;
 walt_get_indicies(p,&got_order,&got_end,boost,uclamp_boosted(p)||boost>0);
 assert(got_order==order && got_end==end);
}
int main(void){
 struct task_struct p;
 reset(&p);assert(mushroom_ui_prime_idle(&p));expect(&p,0,2,1);
 /* Native recheck must examine Big if Prime becomes busy before selection. */
 assert(rows[2][1].bits==112);
 sysctl_mushroom_ui_prime=0;assert(!mushroom_ui_prime_idle(&p));expect(&p,0,1,0);
 reset(&p);cpus[7].idle=false;expect(&p,0,1,0);
 reset(&p);cpus[7].active=false;expect(&p,0,1,0);
 reset(&p);cpus[7].isolated=true;expect(&p,0,1,0);
 reset(&p);cpus[7].reserved=true;expect(&p,0,1,0);
 reset(&p);cpus[7].irq=true;expect(&p,0,1,0);
 reset(&p);p.cpus_ptr=&no_prime;expect(&p,0,1,0);
 reset(&p);p.cpus_ptr=&little;assert(!mushroom_ui_prime_idle(&p));
 reset(&p);cpus[7].thermal=850;expect(&p,0,1,0);
 reset(&p);cpus[7].available=850;expect(&p,0,1,0);
 reset(&p);cpus[7].thermal=900;expect(&p,0,2,1);
 reset(&p);p.max=850;expect(&p,0,1,0);
 reset(&p);p.max=700;expect(&p,0,1,0);
 reset(&p);p.latency=false;expect(&p,0,1,0);
 reset(&p);p.min=0;expect(&p,0,0,0);
 reset(&p);p.min=0;p.latency=false;expect(&p,0,0,0);
 reset(&p);expect(&p,TASK_BOOST_ON_MAX,2,0);
 reset(&p);cpus[7].idle=false;expect(&p,TASK_BOOST_STRICT_MAX,2,0);
 reset(&p);full_throttle=true;expect(&p,0,2,1);
 reset(&p);full_throttle=true;p.fits=128;expect(&p,0,2,0);
 reset(&p);cpu_array=NULL;assert(!mushroom_ui_prime_idle(&p));
 reset(&p);num_sched_clusters=0;assert(!mushroom_ui_prime_idle(&p));
 reset(&p);num_sched_clusters=2;assert(!mushroom_ui_prime_idle(&p));
 reset(&p);rows[2][0].bits=192;assert(!mushroom_ui_prime_idle(&p));
 puts("PASS: idle Prime checked first only for boosted latency-sensitive tasks; native Big fallback remains");
 puts("PASS: busy/inactive/isolated/reserved/IRQ-loaded Prime, affinity, thermal/capacity and task max clamps respected");
 puts("PASS: toggle-off/native order, no UI hint for background/zero-min tasks; explicit max/strict/global boosts and boot readiness preserved");
 return 0;
}
'''
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    source = directory / 'test.c'
    source.write_text(header + hint + indices + main)
    binary = directory / 'test'
    subprocess.run(['gcc', '-O2', '-Wall', '-Werror', '-fsanitize=undefined',
                    '-o', str(binary), str(source)], check=True)
    subprocess.run([str(binary)], check=True)

# Preserve the frequency policy and native target checks outside the new hint.
selector = function(fair, 'static void walt_find_best_target(')
assert 'if (!cpu_active(i) || cpu_isolated(i))' in selector
assert 'if ((cluster >= end_index) && (target_cpu != -1)' in selector
assert 'if (best_idle_cpu != -1)' in selector
sysctl = (ROOT / 'kernel/sysctl.c').read_text()
assert '.procname = "mushroom_ui_prime"' in sysctl
assert 'qcom-5.4.302-port-v7.' in sysctl
print('PASS: native WALT final candidate checks retained; runtime UI hint and scheduler identity exposed')
