# KernelSU provenance

- Source: https://github.com/tiann/KernelSU
- Tag: `v0.9.5`
- Commit: `b766b98513b5a7eb33bc1c4a76b5702bf1288f07`
- Release version code: `11872`
- Manager: https://github.com/tiann/KernelSU/releases/tag/v0.9.5
- Original license retained in `LICENSE` (GPL-2.0).

Only the upstream `kernel/` directory is vendored here, without a nested Git
repository or setup script. This permits one kernel commit and offline builds.

Local changes: Kbuild uses the fixed upstream release version instead of Git
history or network access; Kconfig defaults to disabled; SELinux helpers use
the kernel accessors so perm/permsu have consistent enforcement state.
The build script explicitly enables KPROBES for su/permsu. The parent tree
backports the Linux 5.9 path_umount API for KernelSU's module unmount feature.

The upstream embedded-ksud stub is retained. Install the matching official
v0.9.5 Manager APK and use its Install action to provision the userspace daemon
and module environment. Do not pair this integration with the current Manager
or a Manager from a different KernelSU fork.
