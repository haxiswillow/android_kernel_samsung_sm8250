#!/usr/bin/env python3
"""Actual Deadline dispatch / THP / swap setup with host-side device fixtures."""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    pos = source.index('{', start)
    depth, end = 1, pos + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def run(code, *defines):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / 'test.c').write_text(code)
        subprocess.run(['gcc', '-O2', '-Wall', '-Werror',
                        '-fsanitize=undefined', *defines,
                        str(path / 'test.c'), '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)


deadline = (ROOT / 'block/deadline-iosched.c').read_text()
constants = '\n'.join(re.findall(r'^static const int (?:read_expire|write_expire|writes_starved|fifo_batch) = [^;]+;', deadline, re.M))
run(r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define HZ 1000
#define READ 0
#define WRITE 1
#define GFP_KERNEL 0
#define ENOMEM 12
#define BUG_ON(x) assert(!(x))
struct request { int dir; struct request *next; };
struct list_head {struct request *head;};
struct rb_root {int nonempty;};
#define RB_ROOT ((struct rb_root){0})
#define RB_EMPTY_ROOT(r) (!(r)->nonempty)
#define INIT_LIST_HEAD(l) ((l)->head=NULL)
#define list_empty(l) (!(l)->head)
struct deadline_data {
    struct rb_root sort_list[2]; struct list_head fifo_list[2];
    struct request *next_rq[2]; unsigned int batching,starved;
    int fifo_expire[2],fifo_batch,writes_starved,front_merges;
};
struct elevator_queue {void *elevator_data;int kobj;};
struct elevator_type {int unused;};
struct request_queue {struct elevator_queue *elevator;int node,queue_lock;};
static struct elevator_queue *elevator_alloc(struct request_queue *q,struct elevator_type *e){return calloc(1,sizeof(struct elevator_queue));}
static void *kzalloc_node(size_t bytes,int flags,int node){return calloc(1,bytes);}
#define kobject_put(k) ((void)0)
#define spin_lock_irq(l) ((void)0)
#define spin_unlock_irq(l) ((void)0)
static struct request *deadline_next_request(struct deadline_data *dd,int dir){return dd->next_rq[dir];}
static struct request *deadline_fifo_request(struct deadline_data *dd,int dir){return dd->fifo_list[dir].head;}
static int expired[2], dispatch_count, last_dir;
static int deadline_check_fifo(struct deadline_data *dd,int dir){return expired[dir];}
static void deadline_move_request(struct deadline_data *dd,struct request *rq){
    int dir=rq->dir; assert(dd->fifo_list[dir].head==rq);
    dd->next_rq[0]=dd->next_rq[1]=NULL;
    dd->next_rq[dir]=rq->next;dd->fifo_list[dir].head=rq->next;
    dd->sort_list[dir].nonempty=(rq->next!=NULL);
    last_dir=dir; dispatch_count++;
}
''' + constants + function(deadline, 'static int deadline_init_queue(') +
    function(deadline, 'static int deadline_dispatch_requests(') + r'''
int main(void){
    struct request_queue q={0}; struct elevator_type type={0};
    assert(!deadline_init_queue(&q,&type));
    struct deadline_data *dd=q.elevator->elevator_data;
    assert(dd->fifo_expire[READ]==50 && dd->fifo_expire[WRITE]==500);
    assert(dd->fifo_batch==8 && dd->writes_starved==2 && dd->front_merges==1);
    struct request reads[32],write={WRITE,NULL};
    for(int i=0;i<32;i++){reads[i].dir=READ;reads[i].next=i==31?NULL:&reads[i+1];}
    dd->fifo_list[READ].head=reads;dd->fifo_list[WRITE].head=&write;
    dd->sort_list[READ].nonempty=dd->sort_list[WRITE].nonempty=1;
    /* Read preference is bounded: a write batch follows two read batches. */
    for(int i=0;i<16;i++){assert(deadline_dispatch_requests(&q,0));assert(last_dir==READ);}
    assert(deadline_dispatch_requests(&q,0) && last_dir==WRITE);
    while(deadline_dispatch_requests(&q,0)){}
    assert(dispatch_count==33 && list_empty(&dd->fifo_list[READ]) && list_empty(&dd->fifo_list[WRITE]));
    free(dd);free(q.elevator);
    puts("PASS I/O: real Deadline init/dispatch, 50/500 ms defaults, 8-request batches, write starvation bound, drain");
}
''')

huge = (ROOT / 'mm/huge_memory.c').read_text()
start = huge.index('unsigned long transparent_hugepage_flags __read_mostly =')
end = huge.index(';', start) + 1
huge_header = (ROOT / 'include/linux/huge_mm.h').read_text()
run(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#define __read_mostly
enum {TRANSPARENT_HUGEPAGE_FLAG,TRANSPARENT_HUGEPAGE_REQ_MADV_FLAG,
      TRANSPARENT_HUGEPAGE_DEFRAG_REQ_MADV_FLAG,
      TRANSPARENT_HUGEPAGE_DEFRAG_KHUGEPAGED_FLAG,
      TRANSPARENT_HUGEPAGE_USE_ZERO_PAGE_FLAG};
#define VM_NOHUGEPAGE 1
#define VM_HUGEPAGE 2
#define MMF_DISABLE_THP 0
struct mm_struct {unsigned long flags;};
struct vm_area_struct {unsigned long vm_flags;struct mm_struct *vm_mm;bool temporary;};
static bool is_vma_temporary_stack(struct vm_area_struct *v){return v->temporary;}
static bool test_bit(int bit,unsigned long *value){return !!(*value & (1UL<<bit));}
static bool vma_is_dax(struct vm_area_struct *v){return false;}
''' + huge[start:end] + function(huge_header, 'static inline bool __transparent_hugepage_enabled(') + r'''
int main(void){struct mm_struct mm={0};struct vm_area_struct v={0,&mm,false};
    assert(!__transparent_hugepage_enabled(&v));
    v.vm_flags=VM_HUGEPAGE;assert(__transparent_hugepage_enabled(&v));
    v.vm_flags|=VM_NOHUGEPAGE;assert(!__transparent_hugepage_enabled(&v));
    v.vm_flags=VM_HUGEPAGE;mm.flags=1;assert(!__transparent_hugepage_enabled(&v));
    mm.flags=0;v.temporary=true;assert(!__transparent_hugepage_enabled(&v));
    puts("PASS memory: actual THP eligibility limits hugepages to advised regions; opt-outs remain effective");}
''', '-DCONFIG_TRANSPARENT_HUGEPAGE_MADVISE=1')

swap = (ROOT / 'mm/swap.c').read_text()
code = r'''
#include <assert.h>
#include <stdio.h>
#define __init
#define PAGE_SHIFT 12
#define IS_ENABLED(x) (x)
static unsigned long totalram_pages;
static int page_cluster;
''' + function(swap, 'void __init swap_setup(') + r'''
int main(void){totalram_pages=6UL*1024*1024*1024/4096;swap_setup();
    assert(page_cluster==(CONFIG_ZRAM?0:3));
    puts("PASS memory: real swap_setup retains zero read-ahead for ZRAM and disk fallback");}
'''
run(code, '-DCONFIG_ZRAM=1')
run(code, '-DCONFIG_ZRAM=0')

config = (ROOT / 'mushroom/performance.config').read_text()
assert 'CONFIG_DEFAULT_IOSCHED="deadline"' in config
assert 'CONFIG_DEFAULT_DEADLINE=y' in config
assert 'CONFIG_TRANSPARENT_HUGEPAGE_MADVISE=y' in config
assert 'CONFIG_LRU_GEN=y' in config and 'CONFIG_LRU_GEN_ENABLED=y' in config
assert 'int vm_swappiness = 120;' in (ROOT / 'mm/vmscan.c').read_text()
assert 'host->use_blk_mq = false;' in (ROOT / 'drivers/scsi/ufs/ufshcd.c').read_text()
assert 'CONFIG_F2FS_FS=y' in config and 'CONFIG_EXT4_FS=y' in config
print('PASS integration: single-queue UFS default, MGLRU, swappiness, both filesystems retained')
