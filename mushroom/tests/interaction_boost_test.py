#!/usr/bin/env python3
"""Execute actual interaction functions under UBSan; not a phone boot/FPS test."""
from pathlib import Path
import subprocess,tempfile,sys
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[2]
cpu=(ROOT/'kernel/sched54/walt/cpu-boost.c').read_text()
ddr=(ROOT/'drivers/devfreq/devfreq.c').read_text()
def function(source,marker):
 pos=0
 while True:
  start=source.index(marker,pos);a=source.index('{',start);semi=source.find(';',start)
  if semi<0 or semi>a:break
  pos=start+len(marker)
 depth=1;b=a+1
 while depth:
  depth+=(source[b]=='{')-(source[b]=='}');b+=1
 return source[start:b]
def run(name,code):
 with tempfile.TemporaryDirectory(prefix='mushroom-interaction-') as td:
  p=Path(td);(p/'test.c').write_text(code)
  subprocess.run(['gcc','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-variable','-fsanitize=undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
  subprocess.run([str(p/'test')],check=True)
 print('PASS:',name,flush=True)
common=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include <sys/types.h>
typedef uint64_t u64;
static unsigned long jiffies;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define MIN min
#define MAX max
#define max_t(t,a,b) max((t)(a),(t)(b))
#define clamp_t(t,a,b,c) min(max((t)(a),(t)(b)),(t)(c))
#define time_before(a,b) ((long)((a)-(b))<0)
#define time_after(a,b) time_before(b,a)
#define msecs_to_jiffies(x) ((unsigned long)(x))
#define spin_lock_irqsave(l,f) do{(void)(l);(f)=0;}while(0)
#define spin_unlock_irqrestore(l,f) do{(void)(l);(void)(f);}while(0)
#define smp_load_acquire(p) (*(p))
#define smp_store_release(p,v) (*(p)=(v))
#define IS_ENABLED(x) 1
#define module_param(a,b,c)
#define MODULE_PARM_DESC(a,b)
#define DEFINE_SPINLOCK(x) int x
struct work_struct{int unused;};
struct delayed_work{int unused;};
struct workqueue_struct{int unused;};
'''
cpu_common=r'''
#define DEFINE_PER_CPU(t,n) t n[8]
#define per_cpu(n,c) n[c]
#define for_each_possible_cpu(c) for((c)=0;(c)<8;(c)++)
#define for_each_cpu(c,m) for((c)=0;(c)<8;(c)++) if((m)->bits&(1U<<(c)))
#define show_one(x)
#define store_one(x)
#define cpu_boost_attr_rw(x)
#define USEC_PER_MSEC 1000
#define nr_cpu_ids 8
#define cpu_possible(c) ((c)<8)
#define GFP_KERNEL 0
#define EV_SYN 0
#define EV_KEY 1
#define EV_ABS 3
#define SYN_REPORT 0
struct input_handle{int unused;};
struct kobject{int unused;};
struct kobj_attribute{int unused;};
struct notifier_block{int unused;};
struct cpumask{unsigned int bits;};
struct cpufreq_policy{unsigned int cpu,min,max;struct cpumask *related_cpus;};
static struct cpumask masks[3]={{15},{112},{128}},online={255};
static struct cpufreq_policy policies[3]={{0,300000,1804800,&masks[0]},{4,710400,2419200,&masks[1]},{7,844800,2841600,&masks[2]}};
#define cpu_online_mask (&online)
#define get_online_cpus() ((void)0)
#define put_online_cpus() ((void)0)
#define cpumask_copy(d,s) (*(d)=*(s))
#define cpumask_andnot(d,a,b) ((d)->bits=(a)->bits&~(b)->bits)
static int policy_updates,queued,sched_calls,ddr_calls;
static bool pending;
static unsigned long cpu_due,ddr_until;
static struct workqueue_struct queue;
static unsigned int user_min[3]={300000,710400,844800};
static unsigned int cap[3]={1804800,2419200,2841600};
static struct cpufreq_policy *cpufreq_cpu_get(unsigned int c){return &policies[c<4?0:c<7?1:2];}
static void cpufreq_cpu_put(struct cpufreq_policy *p){}
static void cpufreq_update_policy(unsigned int c);
static void cpufreq_verify_within_limits(struct cpufreq_policy *p,unsigned int lo,unsigned int hi){
 p->min=max(p->min,lo);p->min=min(p->min,hi);p->max=max(p->max,lo);p->max=min(p->max,hi);p->min=min(p->min,p->max);
}
#define CPUFREQ_ADJUST 1
#define NOTIFY_DONE 0
#define NOTIFY_OK 1
static int sched_set_boost(unsigned int x){sched_calls++;return 0;}
static bool queue_work(struct workqueue_struct *q,struct work_struct *w){if(pending)return false;pending=true;queued++;return true;}
static bool mod_delayed_work(struct workqueue_struct *q,struct delayed_work *w,unsigned long delay){assert(delay>0&&delay<=1000);cpu_due=jiffies+delay;return true;}
static void mushroom_ddr_boost_kick(unsigned int ms){if(ms){ddr_calls++;ddr_until=jiffies+ms;}}
static u64 ktime_get(void){return (u64)jiffies*1000;}
#define ktime_to_us(x) (x)
static char *kstrndup(const char *s,size_t n,int flags){char *p=malloc(n+1);if(p){memcpy(p,s,n);p[n]=0;}return p;}
#define kcalloc(n,s,f) calloc(n,s)
#define kfree free
static char *strim(char *s){char *end;while(*s==' '||*s=='\t'||*s=='\n')s++;end=s+strlen(s);while(end>s&&(end[-1]==' '||end[-1]=='\t'||end[-1]=='\n'))*--end=0;return s;}
static int kstrtouint(const char *s,unsigned int base,unsigned int *v){char *end;unsigned long x;if(!*s||*s=='-')return -EINVAL;errno=0;x=strtoul(s,&end,base);if(errno||*end||x>UINT_MAX)return -EINVAL;*v=x;return 0;}
'''
# Actual declarations and pure helpers; the sysfs display macros are model no-ops.
a=cpu.index('struct cpu_sync {');b=cpu.index('static ssize_t store_input_boost_freq(',a)
declarations=cpu[a:b]
parts=common+cpu_common+declarations+function(cpu,'static int boost_adjust_notify(')+r'''
static void cpufreq_update_policy(unsigned int c){unsigned int i=c<4?0:c<7?1:2;struct cpufreq_policy *p=&policies[i];policy_updates++;p->min=user_min[i];p->max=cap[i];boost_adjust_notify(0,CPUFREQ_ADJUST,p);}
'''
for marker in ['static void update_policy_online(','static void mushroom_apply_boost(','static void do_input_boost_rem(','static void do_input_boost(','static void cpuboost_input_event(','static ssize_t store_input_boost_freq(']:parts+=function(cpu,marker)+'\n'
parts+=r'''
static void drain(void){if(pending){pending=false;do_input_boost(0);}}
int main(void){
 cpu_boost_wq=&queue;jiffies=100;
 mushroom_input_boost_launch();assert(!pending&&ddr_calls==0);
 mushroom_boost_ready=true;
 cpuboost_input_event(0,EV_ABS,1,55);assert(!pending);
 cpuboost_input_event(0,EV_KEY,2,0);assert(!pending);
 cpuboost_input_event(0,EV_KEY,2,1);drain();
 assert(policy_updates==3&&sched_calls==0&&input_boost_until==350&&ddr_until==600);
 assert(policies[0].min==1708800&&policies[1].min==2246400&&policies[2].min==2553600);
 for(unsigned long t=116;t<=404;t+=16){jiffies=t;cpuboost_input_event(0,EV_SYN,SYN_REPORT,0);drain();if(time_before(cpu_due,jiffies)||cpu_due==jiffies)do_input_boost_rem(0);}
 assert(policy_updates==3&&queued==1); /* renewal does not reprogram policies */
 jiffies=input_boost_until;do_input_boost_rem(0);assert(policy_updates==6);
 assert(policies[0].min==user_min[0]&&policies[1].min==user_min[1]&&policies[2].min==user_min[2]);
 jiffies=1000;cap[2]=1305600;mushroom_input_boost_launch();drain();
 assert(policies[2].max==1305600&&policies[2].min==1305600); /* thermal cap wins */
 jiffies=1250;do_input_boost_rem(0);cap[2]=2841600;
 unsigned int old=sync_info[0].input_boost_freq;
 const char *bad="0:900000 99:1";assert(store_input_boost_freq(0,0,bad,strlen(bad))<0);assert(sync_info[0].input_boost_freq==old);
 bad="0:900000 4:invalid";assert(store_input_boost_freq(0,0,bad,strlen(bad))<0);assert(sync_info[0].input_boost_freq==old);
 const char *valid="0:1000000 4:1500000 7:1800000 \n";assert(store_input_boost_freq(0,0,valid,strlen(valid))==(ssize_t)strlen(valid));
 assert(sync_info[0].input_boost_freq==1000000&&sync_info[4].input_boost_freq==1500000);
 mushroom_enabled=false;jiffies=2000;input_boost_ms=40;cpuboost_input_event(0,EV_SYN,SYN_REPORT,0);drain();
 assert(policies[0].min==1000000&&policies[1].min==1500000&&policies[2].min==1800000);
 assert(input_boost_until==2040);jiffies=2040;do_input_boost_rem(0);
 mushroom_enabled=true;mushroom_cpu_ms=UINT_MAX;assert(mushroom_boost_duration()==1000);
 mushroom_cpu_ms=0;assert(mushroom_boost_duration()==40);input_boost_ms=0;assert(mushroom_boost_duration()==16);
 mushroom_cpu_ms=250;jiffies=ULONG_MAX-100;input_boost_until=jiffies-1;mushroom_input_boost_launch();drain();
 assert(cpu_due==149);jiffies=149;do_input_boost_rem(0);assert(sync_info[0].input_boost_min==0);
 return 0;
}
'''
run('CPU floors, expiry/renewal coalescing, capped policies, parser atomicity, legacy fallback and tick wrap',parts)
# Actual devfreq target calculation and actual DDR worker, with two model devices.
ddr_common=r'''
typedef uint32_t u32;
#define DEVFREQ_FLAG_LEAST_UPPER_BOUND 1
#define DEVFREQ_PRECHANGE 0
#define DEVFREQ_POSTCHANGE 1
#define mutex_lock(p) (++*(p))
#define mutex_unlock(p) (--*(p))
#define mutex_is_locked(p) (*(p)>0)
#define WARN(x,...) ((void)0)
#define dev_err(...) ((void)0)
struct device{const char *name;struct device *parent;int idx;};
struct devfreq;
struct governor{int (*get_target_freq)(struct devfreq*,unsigned long*);};
struct profile{int (*target)(struct device*,unsigned long*,u32);int (*get_cur_freq)(struct device*,unsigned long*);};
struct devfreq{int lock,event_lock;struct device dev;bool dev_suspended,stop_polling;struct governor *governor;struct profile *profile;unsigned long max_freq,min_freq,scaling_max_freq,scaling_min_freq,previous_freq;};
struct devfreq_freqs{unsigned long old,new;};
static struct devfreq devices[2];static struct device parents[2];
static int devfreq_list_lock,devfreq_list,ddr_updates[2];
static unsigned long wanted=2000,seen[2],ddr_due;static unsigned int ddr_queued;static bool ddr_pending;
static struct workqueue_struct high;
static struct workqueue_struct *system_highpri_wq=&high;
#define list_for_each_entry(p,h,m) for((p)=devices;(p)<devices+2;(p)++)
static const char *dev_name(struct device *d){return d->name;}
static unsigned long mushroom_native_limit(struct devfreq *d,bool maximum){return 0;}
static int get_target(struct devfreq *d,unsigned long *f){*f=wanted;return 0;}
static int target(struct device *d,unsigned long *f,u32 flags){seen[d->idx]=*f;ddr_updates[d->idx]++;return 0;}
static int devfreq_update_status(struct devfreq *d,unsigned long f){return 0;}
static void devfreq_notify_transition(struct devfreq *d,struct devfreq_freqs *f,int phase){}
static int mushroom_ddr_lock;static unsigned long mushroom_ddr_until;static bool mushroom_ddr_applied;
static struct delayed_work mushroom_ddr_work;
static bool mod_delayed_work(struct workqueue_struct *q,struct delayed_work *w,unsigned long delay){assert(delay<=1000);ddr_due=jiffies+delay;if(!delay){ddr_pending=true;ddr_queued++;}return true;}
'''
parts=common+ddr_common+function(ddr,'static bool mushroom_ddr_active(')+function(ddr,'int update_devfreq(')+function(ddr,'void mushroom_ddr_boost_kick(')+function(ddr,'static void mushroom_ddr_workfn(')+r'''
static struct governor gov={get_target};static struct profile prof={target,0};
static void drain(void){if(ddr_pending){ddr_pending=false;mushroom_ddr_workfn(0);}}
int main(void){
 parents[0]=(struct device){"soc:qcom,cpu-llcc-ddr-bw",0,0};parents[1]=(struct device){"kgsl-3d0",0,1};
 for(int i=0;i<2;i++){devices[i].dev.parent=&parents[i];devices[i].governor=&gov;devices[i].profile=&prof;devices[i].max_freq=10437;devices[i].scaling_max_freq=7980;devices[i].min_freq=1700;}
 jiffies=100;mushroom_ddr_boost_kick(500);drain();assert(seen[0]==7980&&ddr_updates[0]==1&&ddr_updates[1]==0&&ddr_due==600);
 jiffies=500;mushroom_ddr_boost_kick(500);drain();assert(ddr_updates[0]==1&&ddr_queued==1);
 jiffies=600;mushroom_ddr_workfn(0);assert(ddr_updates[0]==1&&ddr_due==1000);
 jiffies=1000;mushroom_ddr_workfn(0);assert(seen[0]==2000&&ddr_updates[0]==2);
 jiffies=1100;devices[0].scaling_max_freq=3590;mushroom_ddr_boost_kick(500);drain();assert(seen[0]==3590);
 jiffies=1600;mushroom_ddr_workfn(0);assert(seen[0]==2000);
 devices[0].dev_suspended=true;jiffies=1700;int count=ddr_updates[0];mushroom_ddr_boost_kick(500);drain();assert(ddr_updates[0]==count);
 devices[0].dev_suspended=false;mutex_lock(&devices[0].lock);update_devfreq(&devices[0]);mutex_unlock(&devices[0].lock);assert(seen[0]==3590);
 jiffies=2200;mushroom_ddr_workfn(0);assert(seen[0]==2000);
 count=ddr_updates[0];mushroom_ddr_boost_kick(0);drain();assert(ddr_updates[0]==count);
 jiffies=ULONG_MAX-100;mushroom_ddr_until=jiffies-1;mushroom_ddr_boost_kick(500);drain();assert(ddr_due==399);jiffies=399;mushroom_ddr_workfn(0);assert(seen[0]==2000);
 assert(!devfreq_list_lock&&!devices[0].event_lock&&!devices[0].lock&&ddr_updates[1]==0);return 0;
}
'''
run('DDR real target/caps, bounded expiry, coalescing, suspend exclusion, wrap and GPU isolation',parts)
