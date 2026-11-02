#!/usr/bin/env python3
"""Compile actual kthread helpers; exercise the boot failure and safe queries."""
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


source = (ROOT / 'kernel/kthread.c').read_text()
functions = '\n'.join(function(source, sig) for sig in [
    'static inline struct kthread *to_kthread(',
    'static inline struct kthread *__to_kthread(',
    'bool kthread_is_per_cpu(',
    'void *kthread_probe_data(',
    'void kthread_set_per_cpu(',
    'void kthread_associate_blkcg(',
    'struct cgroup_subsys_state *kthread_blkcg(',
])
header = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#define __force
#define PF_KTHREAD 0x00200000UL
#define PF_NO_SETAFFINITY 0x04000000UL
#define KTHREAD_IS_PER_CPU 0
struct cgroup_subsys_state { int refs; };
struct kthread { unsigned long flags; unsigned int cpu; void *data; struct cgroup_subsys_state *blkcg_css; };
struct task_struct { unsigned long flags; void *set_child_tid; };
static struct task_struct *current, *exec_task;
static unsigned int warnings, pointer_reads, flag_reads;
static bool exec_after_pointer;
#define WARN_ON(x) do { if (x) warnings++; } while (0)
#define WARN_ON_ONCE(x) WARN_ON(x)
static void observe_read(void *address)
{
    if (!exec_task) return;
    if (address == &exec_task->set_child_tid) {
        pointer_reads++;
        if (exec_after_pointer) {
            exec_task->flags &= ~PF_KTHREAD;
            exec_after_pointer = false;
        }
    } else if (address == &exec_task->flags) {
        flag_reads++;
        assert(pointer_reads); /* Pointer must have been captured first. */
    }
}
#define READ_ONCE(x) ({ __typeof__(x) value = (x); observe_read(&(x)); value; })
static bool test_bit(unsigned int bit, const unsigned long *flags) { return !!(*flags & (1UL << bit)); }
static void set_bit(unsigned int bit, unsigned long *flags) { *flags |= 1UL << bit; }
static void clear_bit(unsigned int bit, unsigned long *flags) { *flags &= ~(1UL << bit); }
static int probe_kernel_read(void *out, const void *in, size_t size) { memcpy(out, in, size); return 0; }
static void css_get(struct cgroup_subsys_state *css) { css->refs++; }
static void css_put(struct cgroup_subsys_state *css) { assert(css->refs); css->refs--; }
'''
main = r'''
int main(void)
{
    size_t pagesize = (size_t)sysconf(_SC_PAGESIZE);
    void *user_tid = mmap(NULL, pagesize, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(user_tid != MAP_FAILED);
    struct task_struct user = { .flags = 0, .set_child_tid = user_tid };
    /* Old kthread_is_per_cpu would dereference this inaccessible TID address. */
    assert(!kthread_is_per_cpu(&user));
    assert(kthread_probe_data(&user) == NULL);
    current = &user;
    struct cgroup_subsys_state first = {0}, second = {0};
    kthread_associate_blkcg(&first);
    assert(kthread_blkcg() == NULL && first.refs == 0);

    struct task_struct transient = { .flags = PF_KTHREAD, .set_child_tid = NULL };
    assert(!kthread_is_per_cpu(&transient));
    assert(kthread_probe_data(&transient) == NULL);
    current = &transient;
    kthread_associate_blkcg(&first);
    assert(kthread_blkcg() == NULL);

    int payload = 123;
    struct kthread kt = { .data = &payload };
    struct task_struct kernel = { .flags = PF_KTHREAD | PF_NO_SETAFFINITY, .set_child_tid = &kt };
    assert(!kthread_is_per_cpu(&kernel));
    kthread_set_per_cpu(&kernel, 7);
    assert(kthread_is_per_cpu(&kernel) && kt.cpu == 7);
    assert(kthread_probe_data(&kernel) == &payload);
    kthread_set_per_cpu(&kernel, -1);
    assert(!kthread_is_per_cpu(&kernel));
    current = &kernel;
    kthread_associate_blkcg(&first);
    assert(kthread_blkcg() == &first && first.refs == 1);
    kthread_associate_blkcg(&second);
    assert(first.refs == 0 && second.refs == 1 && kthread_blkcg() == &second);
    kthread_associate_blkcg(NULL);
    assert(second.refs == 0 && kthread_blkcg() == NULL);

    /* Model PF_KTHREAD disappearing after the pointer was captured by exec. */
    transient.flags = PF_KTHREAD;
    transient.set_child_tid = user_tid;
    exec_task = &transient;
    pointer_reads = flag_reads = 0;
    exec_after_pointer = true;
    assert(!kthread_is_per_cpu(&transient));
    assert(pointer_reads == 1 && flag_reads == 1);
    exec_task = NULL;
    assert(!warnings);
    assert(munmap(user_tid, pagesize) == 0);
    puts("PASS: user TID pointer is never dereferenced; NULL kthreads safe; per-CPU identity retained");
    puts("PASS: speculative probe/blkcg queries safe; css references balanced; pointer-before-flags exec transition safe");
    return 0;
}
'''
with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    test_c = directory / 'test.c'
    test_c.write_text(header + functions + main)
    binary = directory / 'test'
    subprocess.run(['gcc', '-O2', '-Wall', '-Werror', '-fsanitize=undefined',
                    '-o', str(binary), str(test_c)], check=True)
    subprocess.run([str(binary)], check=True)
