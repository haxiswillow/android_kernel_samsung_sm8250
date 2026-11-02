#!/usr/bin/env python3
"""Exercise actual WALT initialization/handlers; this does not boot a phone."""
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


arch = (ROOT / 'drivers/base/arch_topology.c').read_text()
walt = (ROOT / 'kernel/sched54/walt/walt.c').read_text()
vas = (ROOT / 'kernel/sched54/walt/qc_vas.c').read_text()
callback = function(arch, 'static int\ninit_cpu_capacity_callback(')
constructor = function(walt, 'void walt_update_cluster_topology(')
siblings = function(walt, 'static void walt_get_possible_siblings(')
group_handler = function(walt, 'int walt_proc_group_thresholds_handler(')
migrate_handler = function(vas, 'int sched_updown_migrate_handler(')

header = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define __user
#define CONFIG_PROC_SYSCTL 1
#define CPUFREQ_NOTIFY 7
#define NOTIFY_OTHER 8
#define NR_CPUS 8
#define SCHED_FIXEDPOINT_SCALE 1024
#define GFP_KERNEL 0
#define unlikely(x) (x)
#define DEFINE_MUTEX(x) int x
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
#define raw_spin_lock_irqsave(x,f) do { (void)(x); (f)=0; } while (0)
#define raw_spin_unlock_irqrestore(x,f) do { (void)(x); (void)(f); } while (0)
#define pr_debug(...) ((void)0)
#define WARN(x,...) assert(!(x))
#define SCHED_BUG_ON(x) assert(!(x))
#define BUG_ON(x) assert(!(x))
#define max(a,b) ((a)>(b)?(a):(b))
#define for_each_possible_cpu(i) for((i)=0;(i)<8;(i)++)
#define for_each_cpu(i,m) for((i)=0;(i)<8;(i)++) if ((m)->bits & (1U<<(i)))
struct cpumask { unsigned int bits; };
typedef struct cpumask cpumask_t;
static struct cpumask possible = {255}, visited;
#define cpu_possible_mask (&possible)
#define cpumask_andnot(d,a,b) ((d)->bits=(a)->bits & ~(b)->bits)
#define cpumask_empty(m) (!(m)->bits)
#define cpumask_clear(m) ((m)->bits=0)
#define cpumask_copy(d,s) ((d)->bits=(s)->bits)
#define cpumask_or(d,a,b) ((d)->bits=(a)->bits | (b)->bits)
#define cpumask_set_cpu(c,m) ((m)->bits |= 1U<<(c))
static unsigned int cpumask_first(const struct cpumask *m) { assert(m->bits);return __builtin_ctz(m->bits); }
static unsigned int cpumask_weight(const struct cpumask *m) { return __builtin_popcount(m->bits); }
struct cpu_topology { int package_id; };
static struct cpu_topology cpu_topology[8]={{0},{0},{0},{0},{1},{1},{1},{2}};
struct cpufreq_policy { struct cpumask *related_cpus; struct {unsigned int max_freq;} cpuinfo; unsigned int cur; };
static struct cpumask masks[3]={{15},{112},{128}};
static struct cpufreq_policy policies[3]={{&masks[0],{1804800},691200},{&masks[1],{2419200},825600},{&masks[2],{2841600},844800}};
static bool ready[3], normalized;
static unsigned int initial_capacity[8]={350,350,350,350,800,800,800,1024};
static unsigned int raw_data[8], *raw_capacity, capacity_scale;
static struct cpumask *cpus_to_visit=&visited;
struct notifier_block { int unused; };
struct work_struct {int tag;};
static struct work_struct update_topology_flags_work={1},parsing_done_work={2},walt_work={3};
static int normalize_calls, topology_calls, walt_work_calls, flags_work_calls, cleanup_work_calls;
struct walt_sched_cluster {struct cpumask cpus;unsigned int max_possible_freq,cur_freq;};
struct list_head {struct walt_sched_cluster *nodes[8];int count;};
static struct list_head cluster_head;
static struct walt_sched_cluster clusters[3];
static int num_sched_clusters;
static struct cpumask asym_cap_sibling_cpus,asym_freq_match_cpus;
static bool walt_clusters_parsed;
static struct cpumask *array[3],**cpu_array;
struct rq { int lock; struct {struct cpumask freq_domain_cpumask;} wrq;};
static struct rq runqueues[8];
#define cpu_rq(c) (&runqueues[c])
#define INIT_LIST_HEAD(h) ((h)->count=0)
#define list_for_each_entry(p,h,n) for(int _j=0;_j<(h)->count && (((p)=(h)->nodes[_j]),1);_j++)
#define for_each_sched_cluster(p) list_for_each_entry(p,&cluster_head,list)
#define cluster_first_cpu(c) cpumask_first(&(c)->cpus)
#define is_min_capacity_cluster(c) ((c)==&clusters[0])
#define smp_store_release(p,v) (*(p)=(v))
static struct cpufreq_policy *cpufreq_cpu_get_raw(unsigned int cpu) {int c=cpu_topology[cpu].package_id;return ready[c]?&policies[c]:NULL;}
static void cleanup_clusters(struct list_head *h) { assert(!"unexpected bad topology"); }
static void add_cluster(const struct cpumask *m,struct list_head *h) {assert(h->count<3);struct walt_sched_cluster *c=&clusters[h->count];c->cpus=*m;c->max_possible_freq=1;c->cur_freq=1;h->nodes[h->count++]=c;num_sched_clusters++;}
static void assign_cluster_ids(struct list_head *h) { assert(normalized && h->count==3);topology_calls++; }
static void move_list(struct list_head *d,struct list_head *s,bool sync) { *d=*s; }
static void update_all_clusters_stats(void) { assert(cluster_head.count==3);for(int c=0;c<3;c++){assert(clusters[c].max_possible_freq==policies[c].cpuinfo.max_freq);assert(clusters[c].cur_freq==policies[c].cur);} }
static struct cpumask **build_cpu_array(void) { return array; }
static void schedule_work(struct work_struct *w) {
 if(w->tag==3){assert(walt_clusters_parsed && cpu_array && num_sched_clusters==3);walt_work_calls++;}
 if(w->tag==1){assert(normalized);flags_work_calls++;}
 if(w->tag==2){assert(!raw_capacity);cleanup_work_calls++;}
}
static unsigned int topology_get_cpu_scale(void *unused,int cpu) {return initial_capacity[cpu];}
static void topology_normalize_cpu_scale(void) { normalized=true;normalize_calls++; }
static void free_raw_capacity(void) {raw_capacity=NULL;}
struct ctl_table {void *data;size_t maxlen;};
static unsigned int sysctl_sched_capacity_margin_up[2]={1078,1078},sysctl_sched_capacity_margin_down[2]={1205,1205};
static int vector_reads,group_reads;
static int proc_douintvec_capacity(struct ctl_table *t,int w,void *b,size_t *l,loff_t *p){assert(!w && num_sched_clusters==3 && t->maxlen==8);vector_reads++;return 0;}
static int proc_dointvec_minmax(struct ctl_table *t,int w,void *b,size_t *l,loff_t *p){assert(!w);group_reads++;return 0;}
static void *kzalloc(size_t n,int flags){return calloc(1,n);}
#define kfree(p) free(p)
static void sched_update_updown_migrate_values(bool up){assert(!"not a write test");}
static void walt_update_group_thresholds(void){assert(!"not a write test");}
'''
main = r'''
int main(void) {
 size_t len=64;loff_t pos=0;char buffer[64];unsigned int group=65;
 struct ctl_table vec={sysctl_sched_capacity_margin_up,4},scalar={&group,4};
 assert(sched_updown_migrate_handler(&vec,0,buffer,&len,&pos)==-EINVAL);
 assert(walt_proc_group_thresholds_handler(&scalar,0,buffer,&len,&pos)==-EPERM);
 raw_capacity=raw_data;visited.bits=255;
 init_cpu_capacity_callback(NULL,NOTIFY_OTHER,&policies[0]);assert(visited.bits==255 && !topology_calls);
 ready[0]=true;init_cpu_capacity_callback(NULL,CPUFREQ_NOTIFY,&policies[0]);assert(visited.bits==240 && !normalized && !topology_calls);
 ready[1]=true;init_cpu_capacity_callback(NULL,CPUFREQ_NOTIFY,&policies[1]);assert(visited.bits==128 && !normalized && !topology_calls);
 ready[2]=true;init_cpu_capacity_callback(NULL,CPUFREQ_NOTIFY,&policies[2]);
 assert(!raw_capacity && normalized && normalize_calls==1 && flags_work_calls==1 && cleanup_work_calls==1);
#ifdef CONFIG_MUSHROOM_SCHED54
 assert(topology_calls==1 && num_sched_clusters==3 && walt_clusters_parsed && walt_work_calls==1);
 for(int c=0;c<8;c++)assert(runqueues[c].wrq.freq_domain_cpumask.bits==masks[cpu_topology[c].package_id].bits);
 assert(sched_updown_migrate_handler(&vec,0,buffer,&len,&pos)==0 && vector_reads==1);
 assert(walt_proc_group_thresholds_handler(&scalar,0,buffer,&len,&pos)==0 && group_reads==1);
 assert(vec.maxlen==8);
 puts("PASS: last CPUFREQ policy triggers WALT after normalization; 3 clusters and native frequencies published; migration reads restored");
#else
 assert(!topology_calls && !num_sched_clusters && !walt_work_calls);
 puts("PASS: legacy callback behavior preserved; 5.4 WALT initializer never called");
#endif
 init_cpu_capacity_callback(NULL,CPUFREQ_NOTIFY,&policies[0]);assert(normalize_calls==1 && flags_work_calls==1 && cleanup_work_calls==1);
 return 0;
}
'''
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    path = directory / 'test.c'
    path.write_text(header + siblings + constructor + callback + group_handler + migrate_handler + main)
    for enabled in (True, False):
        binary = directory / ('port' if enabled else 'legacy')
        cmd = ['gcc', '-O2', '-Wall', '-Werror', '-fsanitize=undefined']
        if enabled:
            cmd += ['-DCONFIG_MUSHROOM_SCHED54=1']
        subprocess.run(cmd + ['-o', str(binary), str(path)], check=True)
        subprocess.run([str(binary)], check=True)

build = (ROOT / 'build.sh').read_text()
assert 'KERNEL_RELEASE="$BASE_VERSION:Mushroom/$HEX_DATE"' in build
assert '--set-str LOCALVERSION ":Mushroom/$HEX_DATE"' in build
assert 'STEM="MushroomKernel-$ZIP_VARIANT-r8q-$HEX_DATE"' in build
assert 'mushroom_walt_clusters' in (ROOT / 'kernel/sysctl.c').read_text()
print('PASS: uname Mushroom/<hex>; ZIP MushroomKernel-<variant>-r8q-<hex>; live WALT cluster diagnostic')
