#!/usr/bin/env python3
"""Apply reviewed UI-only edits to the pinned AnyKernel3 package export."""
from pathlib import Path
import sys


def prepare(root):
    path = root / 'META-INF/com/google/android/update-binary'
    text = path.read_text()
    changes = {
        'ui_print " " "AnyKernel3 by osm0sis @ xda-developers" " ";':
            'ui_print "AnyKernel3 by osm0sis @ xda-developers" " ";',
        "grep -oE 'AK_BASE.*' META-INF/com/google/android/updater-script >&2;\nui_print \" \";":
            "grep -oE 'AK_BASE.*' META-INF/com/google/android/updater-script >&2;",
        'debugging;\nui_print " ";\nrestore_env;':
            'debugging;\nrestore_env;',
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise SystemExit('AnyKernel3 UI context changed; review before packaging: ' + old)
        text = text.replace(old, new, 1)
    core = root / 'tools/ak3-core.sh'
    core_text = core.read_text()
    old = 'ui_print " " "$imgblock";'
    if core_text.count(old) != 1:
        raise SystemExit('AnyKernel3 partition display context changed; review before packaging')
    core.write_text(core_text.replace(old, 'ui_print "$imgblock";', 1))
    # Keep ui_print's recovery protocol, credits, error paths and partition writers.
    path.write_text(text)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: prepare-installer.py <exported AnyKernel3 directory>')
    prepare(Path(sys.argv[1]))
