#!/usr/bin/env python3
"""Prepare one source-only commit and optionally publish it to the Mushroom fork.

  python3 mushroom/publish.py --check
  python3 mushroom/publish.py --push

Only --push creates a commit or contacts GitHub. The GitHub token is requested
without echo and is never read from the Telegram token.txt or stored on disk.
"""
import argparse
import fcntl
import getpass
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

REPOSITORY = 'haxiswillow/android_kernel_samsung_sm8250'
BRANCH = 'lineage-20_4.19.260-atakan'
MESSAGE = 'Init Mushroom.'
EXCLUDED_DIRS = {'.build', 'out', 'dist', 'clang', 'proton-clang', 'proton',
                 'toolchains', 'AnyKernel3', 'AnyKernel', 'anykernel',
                 'backup', 'backups', 'logs'}
EXCLUDED_FILES = {'apply.py', 'token.txt', 'chat_id.txt', 'github_token.txt',
                  'github-token.txt', 'pat.txt', '.env'}
SECRET = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|'
                    rb'github_pat_[A-Za-z0-9_]{40,}|'
                    rb'\b[0-9]{8,14}:[A-Za-z0-9_-]{30,}\b|'
                    rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def fail(message):
    raise RuntimeError(message)


def git(root, *args, env=None, data=None, allowed=(0,)):
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=env)
    if result.returncode not in allowed:
        fail(result.stderr.decode(errors='replace').strip() or
             'Git failed: ' + args[0])
    return result


def excluded(name):
    parts = Path(name).parts
    return bool(parts) and (parts[0] in EXCLUDED_DIRS or
                           name in EXCLUDED_FILES or
                           (len(parts) == 1 and
                            (name.endswith(('.zip', '.tar', '.tar.gz', '.log')) or
                             name.startswith(('lastkmsg', 'logcat')))))


def plan(root, directory):
    index = Path(directory) / 'source.index'
    env = os.environ.copy()
    env['GIT_INDEX_FILE'] = str(index)
    git(root, 'read-tree', 'HEAD', env=env)
    git(root, 'add', '-A', '--', '.', env=env)
    tracked = git(root, 'ls-files', '-z', env=env).stdout.split(b'\0')
    denied = [n for n in tracked if n and excluded(os.fsdecode(n))]
    if denied:
        git(root, 'update-index', '--force-remove', '-z', '--stdin', env=env,
            data=b'\0'.join(denied) + b'\0')
    # Never publish an accidental nested clone as a gitlink.
    entries = git(root, 'ls-files', '--stage', '-z', env=env).stdout.split(b'\0')
    links = [os.fsdecode(e.split(b'\t', 1)[1]) for e in entries
             if e.startswith(b'160000 ')]
    if links:
        fail('Nested repository/submodule staged: ' + ', '.join(links) +
             '. Keep downloaded clones under .build/; vendor required source.')
    # Scan only changed/added blobs; print filenames, never matching contents.
    changed = git(root, 'diff', '--cached', '--name-only', '--diff-filter=ACMR',
                  '-z', '--no-renames', env=env).stdout.split(b'\0')
    for name in filter(None, changed):
        path = os.fsdecode(name)
        size = int(git(root, 'cat-file', '-s', ':' + path, env=env).stdout)
        if size > 90 * 1024 * 1024:
            fail('Oversized staged file: ' + path)
        blob = git(root, 'show', ':' + path, env=env).stdout
        if SECRET.search(blob):
            fail('Possible credential/private key in staged source: ' + path)
    tree = git(root, 'write-tree', env=env).stdout.decode().strip()
    stats = git(root, 'diff', '--cached', '--stat', env=env).stdout.decode()
    return env, tree, stats, len(denied)


def remote_tip(root, url, branch, env):
    ref = 'refs/heads/' + branch
    result = git(root, 'ls-remote', '--exit-code', url, ref, env=env,
                 allowed=(0, 2))
    if result.returncode == 2:
        return None
    tip = result.stdout.split()[0].decode()
    # Fetch one branch only; the clone's fetch refspec and other branches stay.
    git(root, 'fetch', '--no-tags', '--depth=1', url, ref, env=env)
    fetched = git(root, 'rev-parse', 'FETCH_HEAD').stdout.decode().strip()
    if fetched != tip:
        fail('The remote changed during preflight. Run the command again.')
    return tip


def publish(root, args, directory, env, tree):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        if not sys.stdin.isatty():
            fail('Run --push in an interactive terminal to enter the GitHub token.')
        token = getpass.getpass('GitHub token (hidden; not the Telegram token): ')
    if not token or any(c.isspace() for c in token):
        fail('Invalid GitHub token.')
    askpass = Path(directory) / 'askpass.py'
    askpass.write_text('''#!/usr/bin/env python3
import os, sys
prompt = sys.argv[1].lower()
if 'username' in prompt:
    print('x-access-token')
elif 'password' in prompt:
    print(os.environ['MUSHROOM_GITHUB_TOKEN'])
else:
    raise SystemExit(1)
''')
    askpass.chmod(0o700)
    network = os.environ.copy()
    for key in list(network):
        if key.startswith(('GIT_TRACE', 'GIT_CURL_VERBOSE')):
            network.pop(key)
    network.update(GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT='0', LC_ALL='C',
                   MUSHROOM_GITHUB_TOKEN=token,
                   GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='credential.helper',
                   GIT_CONFIG_VALUE_0='')
    url = 'https://github.com/' + args.repository + '.git'
    tip = remote_tip(root, url, args.branch, network)
    head = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
    head_tree = git(root, 'rev-parse', 'HEAD^{tree}').stdout.decode().strip()
    subject = git(root, 'log', '-1', '--format=%s').stdout.decode().strip()
    retry = False
    if tip and tip != head:
        parents = git(root, 'rev-list', '--parents', '-1', 'HEAD').stdout.decode().split()
        retry = len(parents) == 2 and parents[1] == tip and subject == MESSAGE and tree == head_tree
        if not retry:
            fail('The destination differs from local HEAD. No commit or push made. '
                 'Send this output; do not force-push or reset the source.')
    if tree == head_tree:
        if not retry and tip == head:
            print('Already published; nothing to commit or push.')
            return
        if not retry and subject != MESSAGE:
            fail('No source changes to aggregate as Init Mushroom.')
    else:
        if retry:
            fail('A pending Init Mushroom. commit has later source edits.')
        owner = args.repository.split('/')[0]
        for key, value in [('user.name', 'Nihil'),
                           ('user.email', owner + '@users.noreply.github.com')]:
            if not git(root, 'config', '--get', key, allowed=(0, 1)).stdout.strip():
                git(root, 'config', '--local', key, value)
        result = git(root, 'commit', '-m', MESSAGE, env=env)
        print(result.stdout.decode().strip())
        # Align the ordinary index with the committed tree; working files stay.
        git(root, 'read-tree', 'HEAD')
        head = git(root, 'rev-parse', 'HEAD').stdout.decode().strip()
    git(root, 'push', url, head + ':refs/heads/' + args.branch, env=network)
    print('Published: ' + url[:-4] + '/tree/' + args.branch)
    print('Commit: ' + head + ' — ' + MESSAGE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--push', action='store_true')
    parser.add_argument('--repository', default=REPOSITORY, metavar='OWNER/REPO')
    parser.add_argument('--branch', default=BRANCH)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repository):
        fail('Use --repository OWNER/REPO, without a token or URL.')
    root = args.root.resolve()
    top = git(root, 'rev-parse', '--show-toplevel').stdout.decode().strip()
    if Path(top).resolve() != root:
        fail('Run from the kernel checkout root.')
    git(root, 'check-ref-format', '--branch', args.branch)
    if git(root, 'symbolic-ref', '-q', 'HEAD', allowed=(0, 1)).returncode:
        fail('Detached HEAD; select the intended source branch first.')
    build = (root / 'build.sh').read_text()
    if 'SCHED_CORE=${SCHED_CORE:-5.4}' not in build:
        fail('Apply the Mushroom publication batch first.')
    if 'qcom-5.4.302-port-v7.4' not in (root / 'kernel/sysctl.c').read_text():
        fail('This publication batch requires the working v7.4 source.')
    for path in ['README.md', 'drivers/kernelsu/Kconfig', 'kernel/sched54/Makefile',
                 'mushroom/performance.config', 'mushroom/release.config']:
        if not (root / path).is_file():
            fail('Required source file is missing: ' + path)
    lockpath = root / '.build/build.lock'
    lockpath.parent.mkdir(exist_ok=True)
    with lockpath.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail('A build or another Mushroom operation is active.')
        with tempfile.TemporaryDirectory(prefix='mushroom-publish-') as directory:
            env, tree, stats, removed = plan(root, directory)
            print('Destination: https://github.com/' + args.repository + '/tree/' + args.branch)
            print('Commit message: ' + MESSAGE)
            if removed:
                print('Local-only tracked files excluded from commit: ' + str(removed))
            print(stats or 'No tree changes.')
            if args.check:
                print('Check passed. No commit, push, source or existing index changes.')
            else:
                publish(root, args, directory, env, tree)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
