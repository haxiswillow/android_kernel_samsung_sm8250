### AnyKernel3 installer for Galaxy S20 FE Snapdragon (r8q), AOSP Android 13.
# Generated into a clean upstream AnyKernel3 checkout by build.sh.

properties() { '
kernel.string=Mushroom Kernel by Nihil@donottellmyname
do.devicecheck=1
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=0
device.name1=r8q
device.name2=r8qxx
device.name3=r8qxxx
supported.versions=13
supported.patchlevels=
supported.vendorpatchlevels=
'; }

boot_attributes() {
  set_perm_recursive 0 0 755 644 "$RAMDISK"/*;
  set_perm_recursive 0 0 750 750 "$RAMDISK"/init* "$RAMDISK"/sbin;
}

BLOCK=/dev/block/platform/soc/1d84000.ufshc/by-name/boot;
IS_SLOT_DEVICE=0;
RAMDISK_COMPRESSION=auto;
PATCH_VBMETA_FLAG=auto;

. tools/ak3-core.sh;

# Resolve every required partition before writing either image.
[ -b "$BLOCK" ] || abort "r8q boot partition not found";
dtbo_block=/dev/block/platform/soc/1d84000.ufshc/by-name/dtbo;
[ -b "$dtbo_block" ] || abort "r8q dtbo partition not found";
[ -s "$AKHOME/Image" ] && [ -s "$AKHOME/dtb" ] &&
  [ -s "$AKHOME/dtbo.img" ] || abort "Incomplete Mushroom package";

# Normalize whole parameters; early init must finish restorecon first.
mushroom_selinux_cmdline() {
  local cmdfile header;
  cmdfile="$SPLITIMG/cmdline.txt"; header=0;
  if [ ! -f "$cmdfile" ]; then
    cmdfile="$SPLITIMG/header"; header=1;
  fi;
  [ -f "$cmdfile" ] || abort "Boot command line not found";
  awk -v mode="@SELINUX@" -v header="$header" '
    function normalize(line, a, n, i, out) {
      n=split(line, a, /[ \t]+/); out="";
      for (i=1; i<=n; i++)
        if (a[i]!="" && a[i]!~/^(androidboot[.]selinux|enforcing|selinux|zram[.]mushroom_legacy_2g_mb)=/)
          out=out a[i] " ";
      return out "androidboot.selinux=" mode " enforcing=0 zram.mushroom_legacy_2g_mb=4096";
    }
    !header { print normalize($0); found=1; next }
    /^cmdline=/ {
      sub(/^cmdline=/, ""); print "cmdline=" normalize($0); found=1; next
    }
    { print }
    END { if (!found) exit 1 }
  ' "$cmdfile" > "$cmdfile.mushroom.tmp" || abort "Cannot fix boot command line";
  mv -f "$cmdfile.mushroom.tmp" "$cmdfile" || abort "Cannot save boot command line";
}

split_boot;
mushroom_selinux_cmdline;

# This Lineage 20 tree has no android.is_aosp/is_bpf command-line switches.
# Keep the installed ROM ramdisk and use AK3's checked partition writers.
flash_boot;
flash_generic dtbo;
