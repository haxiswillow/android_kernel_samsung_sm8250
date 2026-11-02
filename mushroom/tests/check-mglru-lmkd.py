#!/usr/bin/env python3
"""Run the actual MGLRU accounting functions with a small host-side kernel model.

Usage: python3 mushroom/tests/check-mglru-lmkd.py [--root KERNEL] [--cc cc]
This tests accounting and control flow, not phone boot, reclaim latency or FPS.
"""
import argparse
from pathlib import Path
import shlex
import subprocess
import tempfile


def function(source, anchor):
    if source.count(anchor) != 1:
        raise ValueError('Function anchor differs: ' + anchor)
    start = source.index(anchor)
    brace = source.index('{', start)
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == '{':
            depth += 1
        elif source[end] == '}':
            depth -= 1
            if depth == 0:
                return source[start:end + 1]
    raise ValueError('Unclosed function: ' + anchor)


MODEL = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define LRU_GEN_ANON 0
#define LRU_GEN_FILE 1
#define LRU_REFS_WIDTH 2
#define MAX_NR_GENS 4
#define EVICTION_MASK 0xffffUL
#define BIT(x) (1UL << (x))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x) = (v))
#define VM_BUG_ON_PAGE(x,p) assert(!(x))
enum { WORKINGSET_REFAULT, WORKINGSET_RESTORE, WORKINGSET_ACTIVATE };
enum { UNEVICTABLE_PGCULLED };
struct pglist_data { int unused; };
struct mem_cgroup { int unused; };
struct lru_gen_struct {
    unsigned long min_seq[2];
    long refaulted[1][2][4], protected[1][2][4];
    int lists[4][2][1];
};
struct lruvec { struct lru_gen_struct lrugen; long stat[3]; };
struct page {
    int file, nr, gen, tier, zone, lru;
    bool evictable, anon, dirty, locked, writeback, workingset, unevictable;
    bool swapbacked;
    struct pglist_data *node;
};
struct shadow { int id; struct pglist_data *node; unsigned long token; bool ws; };
static struct pglist_data Node, OtherNode;
static struct mem_cgroup Memcg;
static struct lruvec Vec;
static bool Disabled, Missing, InFault;
static int page_is_file_cache(struct page *p) { return p->file; }
static int hpage_nr_pages(struct page *p) { return p->nr; }
static struct pglist_data *page_pgdat(struct page *p) { return p->node; }
static void unpack_shadow(void *s, int *id, struct pglist_data **n,
                          unsigned long *t, bool *w) {
    struct shadow *x=s; *id=x->id; *n=x->node; *t=x->token; *w=x->ws;
}
static void rcu_read_lock(void) {}
static void rcu_read_unlock(void) {}
static struct mem_cgroup *mem_cgroup_from_id(int id) { return Missing ? 0 : &Memcg; }
static bool mem_cgroup_disabled(void) { return Disabled; }
static struct lruvec *mem_cgroup_lruvec(struct pglist_data *n, struct mem_cgroup *m) { return &Vec; }
static int lru_hist_from_seq(unsigned long x) { return 0; }
static int lru_tier_from_refs(int x) { return x ? 1 : 0; }
static void atomic_long_add(int n, long *p) { *p += n; }
static void mod_lruvec_state(struct lruvec *v, int k, int n) { v->stat[k] += n; }
static void __mod_lruvec_state(struct lruvec *v, int k, int n) { v->stat[k] += n; }
static bool lru_gen_in_fault(void) { return InFault; }
static void SetPageWorkingset(struct page *p) { p->workingset=true; }
static int page_lru_gen(struct page *p) { return p->gen; }
static int page_lru_tier(struct page *p) { return p->tier; }
static int page_zonenum(struct page *p) { return p->zone; }
static bool page_evictable(struct page *p) { return p->evictable; }
static bool lru_gen_del_page(struct lruvec *v, struct page *p, bool x) { return true; }
static void SetPageUnevictable(struct page *p) { p->unevictable=true; }
static void SetPageSwapBacked(struct page *p) { p->swapbacked=true; }
static void add_page_to_lru_list(struct page *p, struct lruvec *v) {}
static void add_page_to_lru_list_tail(struct page *p, struct lruvec *v) {}
static void __count_vm_events(int k, int n) {}
static bool PageAnon(struct page *p) { return p->anon; }
static bool PageDirty(struct page *p) { return p->dirty; }
static bool PageLocked(struct page *p) { return p->locked; }
static bool PageWriteback(struct page *p) { return p->writeback; }
static int lru_gen_from_seq(unsigned long s) { return s % MAX_NR_GENS; }
static void list_move(int *p, int *q) {}
static void list_move_tail(int *p, int *q) {}
static int page_inc_gen(struct lruvec *v, struct page *p, bool reclaiming) {
    return p->gen=(p->gen + 1) % MAX_NR_GENS;
}
'''


CASES = r'''
static struct page fresh(int type, int nr) {
    struct page p={0}; p.file=type; p.nr=nr; p.node=&Node; p.evictable=true;
    return p;
}
static void reset(void) {
    memset(&Vec,0,sizeof(Vec)); Disabled=false; Missing=false; InFault=false;
}
int main(void) {
    struct shadow s={.node=&Node};
    /* Both single pages and huge-page accounting; preserve anon feedback. */
    for (int type=0;type<2;type++) for (int n=1;n<=512;n*=512) {
        reset(); InFault=true;
        struct page p=fresh(type,n);
        lru_gen_refault(&p,&s);
        assert(Vec.lrugen.refaulted[0][type][0]==n);
        assert(Vec.stat[WORKINGSET_REFAULT]==(type ? n : 0));
        assert(Vec.stat[WORKINGSET_RESTORE]==(type ? n : 0));
        assert(p.workingset); /* anon promotion/protection is unchanged */
        assert(Vec.stat[WORKINGSET_ACTIVATE]==0);
        reset(); p=fresh(type,n); p.tier=2;
        assert(sort_page(&Vec,&p,0));
        assert(Vec.lrugen.protected[0][type][1]==n && p.gen==1);
        assert(Vec.stat[WORKINGSET_ACTIVATE]==(type ? n : 0));
    }
    /* FD refaults outside a fault don't acquire a new working-set flag. */
    reset(); struct page p=fresh(0,1); lru_gen_refault(&p,&s);
    assert(Vec.lrugen.refaulted[0][0][0]==1 && !p.workingset);
    /* Existing rejection rules must still reject invalid shadows. */
    for (int reason=0;reason<4;reason++) {
        reset(); s=(struct shadow){.node=&Node}; p=fresh(1,1);
        if(reason==0)s.token=1;  /* refs without a workingset marker */
        if(reason==1)p.node=&OtherNode;
        if(reason==2)s.token=BIT(LRU_REFS_WIDTH); /* generation mismatch */
        if(reason==3)Missing=true;
        lru_gen_refault(&p,&s);
        assert(Vec.stat[WORKINGSET_REFAULT]==0 && !p.workingset);
        assert(Vec.lrugen.refaulted[0][1][0]==0);
    }
    /* !MEMCG is valid even when there is no memcg pointer. */
    reset(); Disabled=true; Missing=true; s=(struct shadow){.node=&Node};
    p=fresh(1,1); lru_gen_refault(&p,&s);
    assert(Vec.stat[WORKINGSET_REFAULT]==1);
    /* The native unprotected, unevictable and dirty paths remain intact. */
    reset(); p=fresh(0,1); assert(!sort_page(&Vec,&p,0));
    p=fresh(0,1); p.evictable=false;
    assert(sort_page(&Vec,&p,0) && p.unevictable);
    p=fresh(1,1); p.anon=true; p.dirty=true;
    assert(sort_page(&Vec,&p,0) && p.swapbacked);
    p=fresh(0,1); p.locked=true;
    assert(sort_page(&Vec,&p,0) && p.gen==1);
    puts("PASS: legacy file-only counters; anon feedback/working-set flags, huge pages and rejection paths preserved");
    return 0;
}
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--cc',default='cc')
    args=parser.parse_args()
    refault=function((args.root/'mm/workingset.c').read_text(), 'void lru_gen_refault(')
    sort=function((args.root/'mm/vmscan.c').read_text(), 'static bool sort_page(')
    with tempfile.TemporaryDirectory(prefix='mushroom-mm-check-') as name:
        src=Path(name)/'check.c';exe=Path(name)/'check'
        src.write_text(MODEL+'\n'+refault+'\n'+sort+'\n'+CASES)
        subprocess.run(shlex.split(args.cc)+['-std=gnu11','-O2','-Wall','-Wextra','-Werror',
                       '-Wno-unused-parameter','-Wno-unused-function','-fsanitize=undefined',
                       str(src),'-o',str(exe)],check=True,timeout=30)
        subprocess.run([str(exe)],check=True,timeout=10)


if __name__=='__main__':
    main()
