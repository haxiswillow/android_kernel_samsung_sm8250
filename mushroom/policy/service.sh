#!/system/bin/sh
MODDIR=${0%/*}
n=0
while [ "$(getprop sys.boot_completed)" != 1 ] && [ "$n" -lt 120 ]; do
  sleep 1
  n=$((n + 1))
done
[ "$(getprop sys.boot_completed)" = 1 ] || exit 0
sleep 5
rm -f "$MODDIR/state.tsv"
sh "$MODDIR/profile.sh" > "$MODDIR/profile.log" 2>&1
