#!/usr/bin/env python3
"""Host regression tests for actual scheduler functions; not a device boot test."""
from pathlib import Path
import tempfile,subprocess
R=Path(__file__).resolve().parents[2]
def function(s,signature):
 start=s.index(signature);a=s.index('{',start);depth=1;b=a+1
 while depth:
  depth+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[start:b]
def run(code):
 with tempfile.TemporaryDirectory() as d:
  p=Path(d);(p/'test.c').write_text(code)
  subprocess.run(['gcc','-O2','-Wall','-Werror','-fsanitize=undefined','-o',str(p/'test'),str(p/'test.c')],check=True)
  subprocess.run([str(p/'test')],check=True)
core=(R/'kernel/sched54/core.c').read_text()
f=function(core,'static inline struct uclamp_se\nuclamp_eff_get(')
run('''#include <stdio.h>
#include <stdbool.h>
#include <assert.h>
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define unlikely(x) (x)
enum uclamp_id { UCLAMP_MIN, UCLAMP_MAX };
struct uclamp_se { unsigned int value, bucket_id; bool user_defined; };
struct task_struct { struct uclamp_se uclamp_req[2]; unsigned int floor; };
static struct uclamp_se uclamp_default[2]={{1024,4,false},{1024,4,false}};
static struct uclamp_se uclamp_tg_restrict(struct task_struct *p, enum uclamp_id id){return p->uclamp_req[id];}
static unsigned int mushroom_cpuset_util_min(struct task_struct *p){return p->floor;}
static void uclamp_se_set(struct uclamp_se *s,unsigned int v,bool u){s->value=v;s->bucket_id=v/205;s->user_defined=u;}
'''+f+'''
int main(void){
 struct task_struct p={{{0,0,false},{1024,4,false}},204};
 struct uclamp_se out=uclamp_eff_get(&p,UCLAMP_MIN);assert(out.value==204);
 p.floor=819;out=uclamp_eff_get(&p,UCLAMP_MIN);assert(out.value==819 && out.bucket_id==3);
 p.uclamp_req[UCLAMP_MAX].value=300;out=uclamp_eff_get(&p,UCLAMP_MIN);assert(out.value==300 && out.bucket_id==1);
 uclamp_default[UCLAMP_MAX].value=64;assert(uclamp_eff_get(&p,UCLAMP_MIN).value==64);
 p.uclamp_req[UCLAMP_MIN].user_defined=true;assert(uclamp_eff_get(&p,UCLAMP_MIN).value==0);
 p.uclamp_req[UCLAMP_MIN].value=40;assert(uclamp_eff_get(&p,UCLAMP_MIN).value==40);
 puts("5.4 UCLAMP: native floors, bucket updates, explicit requests and maximum caps PASS");
}
''')
s=(R/'kernel/sched54/cpufreq_schedutil.c').read_text()
f=function(s,'static unsigned int sugov_next_freq_shared(')
run('''#include <stdio.h>
#include <stdint.h>
#include <assert.h>
typedef uint64_t u64;typedef int64_t s64;
struct cpufreq_policy{int cpus;};
struct sugov_policy{struct cpufreq_policy *policy;u64 last_freq_update_time;};
struct sugov_cpu{struct sugov_policy *sg_policy;u64 last_update;unsigned long util,max;unsigned int cpu;};
static struct sugov_cpu cpus[3];static unsigned int ceilings[3]={1024,200,1024};
static const s64 stale_ns=100;
#define for_each_cpu(j,mask) for(j=0;j<(mask);j++)
#define per_cpu(unused,j) cpus[j]
#define false 0
#define NULL ((void *)0)
static void sugov_iowait_reset(struct sugov_cpu *c,u64 t,int unused){}
static unsigned long sugov_iowait_apply(struct sugov_cpu *c,u64 t,unsigned long util,unsigned long max){return util;}
static void sugov_walt_adjust(struct sugov_cpu *c,unsigned long *util,unsigned long *max){if(c->cpu==1)*util=1024;}
static unsigned int cpu_rq(unsigned int j){return j;}
static unsigned long uclamp_rq_util_with(unsigned int j,unsigned long util,void *p){return util>ceilings[j]?ceilings[j]:util;}
static unsigned int get_next_freq(struct sugov_policy *p,unsigned long util,unsigned long max){assert(max);return util*1000/max;}
'''+f+'''
int main(void){struct cpufreq_policy policy={3};struct sugov_policy p={&policy,1000};
for(int j=0;j<3;j++){cpus[j].sg_policy=&p;cpus[j].last_update=1000;cpus[j].max=1024;cpus[j].cpu=j;}
cpus[0].util=400;cpus[1].util=900;
assert(sugov_next_freq_shared(&cpus[0],1000)==390);
cpus[0].last_update=800;assert(sugov_next_freq_shared(&cpus[0],1000)==195);
for(int j=0;j<3;j++)cpus[j].max=0;
assert(sugov_next_freq_shared(&cpus[0],1000)==0);
puts("5.4 schedutil: shared-policy WALT boosts respect per-CPU caps; stale/uninitialized CPUs skipped PASS");}
''')
f=function(s,'static bool sugov_update_next_freq(')
run('''#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
#define unlikely(x) (x)
typedef uint64_t u64;
struct sugov_policy{unsigned int next_freq,cached_raw_freq;u64 last_freq_update_time;bool need_freq_update;};
static bool blocked;
static bool sugov_up_down_rate_limit(struct sugov_policy *p,u64 t,unsigned int n){return blocked;}
'''+f+'''
int main(void){struct sugov_policy p={300,1000,10,false};blocked=true;
assert(!sugov_update_next_freq(&p,20,700));assert(p.next_freq==300 && p.cached_raw_freq==0 && p.last_freq_update_time==10);
blocked=false;assert(sugov_update_next_freq(&p,30,700));assert(p.next_freq==700 && p.last_freq_update_time==30);
assert(!sugov_update_next_freq(&p,40,700));assert(p.last_freq_update_time==30);
puts("5.4 schedutil: rejected target invalidates raw-frequency cache; accepted target/time retained PASS");}
''')
# Exercise the actual callback adapter against a shared policy and thermal ceiling.
s=(R/'kernel/sched54/walt/cpu-boost.c').read_text();f=function(s,'static int boost_adjust_notify(')
run('''#include <stdio.h>
#include <stdbool.h>
#include <limits.h>
#include <assert.h>
struct cpufreq_policy{int related_cpus;unsigned int min,max;};struct notifier_block{int unused;};
struct cpu_sync{unsigned int input_boost_min;};static struct cpu_sync cpus[3];
#define CPUFREQ_ADJUST 4
#define NOTIFY_DONE 0
#define NOTIFY_OK 1
#define READ_ONCE(x) (x)
#define per_cpu(n,c) cpus[c]
#define max(a,b) ((a)>(b)?(a):(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define for_each_cpu(c,m) for(c=0;c<(m);c++)
static void cpufreq_verify_within_limits(struct cpufreq_policy *p,unsigned int lo,unsigned int hi){if(p->min<lo)p->min=lo;if(p->max>hi)p->max=hi;if(p->min>p->max)p->min=p->max;}
'''+f+'''
int main(void){struct cpufreq_policy p={3,300,1800};cpus[0].input_boost_min=800;cpus[1].input_boost_min=2400;
assert(boost_adjust_notify(0,99,&p)==NOTIFY_DONE && p.min==300);
assert(boost_adjust_notify(0,CPUFREQ_ADJUST,&p)==NOTIFY_OK && p.min==1800 && p.max==1800);
cpus[1].input_boost_min=900;p.min=300;boost_adjust_notify(0,CPUFREQ_ADJUST,&p);assert(p.min==900);
puts("4.19 input-boost adapter: related-policy votes aggregate and thermal maximum wins PASS");}
''')
# Compile the actual all-flavour RCU bridge with instrumentation of IRQ/CPU state.
s=(R/'kernel/rcu/tree.c').read_text();f=function(s,'void rcu_nocb_flush_deferred_wakeup(void)')
run('''#include <stdio.h>
#include <assert.h>
struct rcu_state{int *rda;};static int seen[3],data[3];static struct rcu_state flavours[3]={{data},{data+1},{data+2}};static int irq_disabled;
#define local_irq_save(f) do{f=irq_disabled;irq_disabled=1;}while(0)
#define local_irq_restore(f) do{irq_disabled=f;}while(0)
#define for_each_rcu_flavor(r) for(r=flavours;r<flavours+3;r++)
#define this_cpu_ptr(p) (p)
static void do_nocb_deferred_wakeup(int *p){assert(irq_disabled);seen[p-data]++;}
'''+f+'''
int main(void){rcu_nocb_flush_deferred_wakeup();assert(!irq_disabled);for(int i=0;i<3;i++)assert(seen[i]==1);
irq_disabled=1;rcu_nocb_flush_deferred_wakeup();assert(irq_disabled);for(int i=0;i<3;i++)assert(seen[i]==2);
puts("4.19 RCU bridge: every flavour flushed with IRQ state preserved PASS");}
''')
# Invariants at cross-subsystem boundaries that are otherwise only exercised on hardware.
f=function(core,'static void try_to_wake_up_local(')
assert 'walt_try_to_wake_up(' not in f and 'note_task_waking(p, wallclock)' in f
assert f.index('rq_unlock(rq, rf)') < f.index('raw_spin_lock(&p->pi_lock)') < f.index('rq_relock(rq, rf)')
assert core.count('walt_task_dead(prev);')==1
assert '#ifndef CONFIG_MUSHROOM_SCHED54\n\tsched_exit(tsk);' in (R/'kernel/exit.c').read_text()
assert 'tsk->cpus_ptr = &tsk->cpus_mask;' in (R/'kernel/fork.c').read_text()
assert '&mushroom_task_walt(p, cpus_requested)' in (R/'kernel/cgroup/cpuset.c').read_text()
print('Boundary checks: local wake avoids nested rq lock; WALT freed once; fork/cpuset use active affinity PASS')
