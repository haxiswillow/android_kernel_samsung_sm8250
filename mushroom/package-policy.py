#!/usr/bin/env python3
"""Create the optional KernelSU companion profile without installing it."""
from pathlib import Path
import sys
import zipfile

def package(output):
    root = Path(__file__).resolve().parent / 'policy'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ('module.prop', 'service.sh', 'uninstall.sh', 'profile.sh'):
            info = zipfile.ZipInfo(name, (2026, 11, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (root / name).read_bytes())

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: package-policy.py <output.zip>')
    package(Path(sys.argv[1]))
