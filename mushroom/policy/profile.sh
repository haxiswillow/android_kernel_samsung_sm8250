#!/system/bin/sh
# One pass only. Never move a task, change foreground masks or poll the HAL.
MODDIR=${0%/*}
STATE=$MODDIR/state.tsv
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required'; exit 1; }
if [ "${1:-}" = --restore ]; then
  [ -f "$STATE" ] || exit 0
  errors=0
  while IFS='|' read -r path before after; do
    [ -f "$path" ] || continue
    current=$(cat "$path" 2>/dev/null)
    if [ "$current" != "$after" ]; then
      echo "Preserved later change: $path"
      continue
    fi
    if printf '%s\n' "$before" > "$path"; then
      echo "Restored: $path"
    else
      errors=$((errors + 1))
    fi
  done < "$STATE"
  [ "$errors" = 0 ] && rm -f "$STATE"
  exit "$errors"
fi
if [ ! -f /sys/kernel/mushroom_ui/enabled ] &&
   [ ! -f /proc/sys/kernel/mushroom_uclamp_top_app ]; then
  echo 'Mushroom STune or UCLAMP kernel required; no settings changed.'; exit 1
fi
errors=0
set_node() {
  path=$1 value=$2
  [ -f "$path" ] || { echo "Unavailable: $path"; return 0; }
  before=$(cat "$path" 2>/dev/null) || { errors=$((errors + 1)); echo "Unreadable: $path"; return 1; }
  if ! grep -F "$path|" "$STATE" >/dev/null 2>&1; then
    printf '%s|%s|%s\n' "$path" "$before" "$value" >> "$STATE" || { errors=$((errors + 1)); echo "Backup failed: $path"; return 1; }
  fi
  if printf '%s\n' "$value" > "$path"; then
    echo "$path = $(cat "$path" 2>/dev/null)"
  else
    errors=$((errors + 1))
  fi
}
set_node /dev/cpuset/system-background/cpus 0-3
set_node /dev/cpuset/background/cpus 0-3
# Cancel a global 80 floor; the kernel provides scoped per-task hints instead.
set_node /dev/stune/schedtune.boost 0
set_node /dev/stune/schedtune.prefer_idle 0
set_node /dev/stune/top-app/schedtune.boost 20
set_node /dev/stune/top-app/schedtune.prefer_idle 1
set_node /dev/stune/foreground/schedtune.boost 10
set_node /dev/stune/foreground/schedtune.prefer_idle 1
set_node /dev/stune/background/schedtune.boost 0
set_node /dev/stune/background/schedtune.prefer_idle 0
set_node /sys/kernel/mushroom_ui/enabled 1
set_node /proc/sys/kernel/mushroom_uclamp_top_app 20
set_node /proc/sys/kernel/mushroom_uclamp_foreground 10
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  set_node "$policy/scaling_governor" schedutil
  set_node "$policy/schedutil/up_rate_limit_us" 250
  set_node "$policy/schedutil/down_rate_limit_us" 8000
done
# FKM multiplies this MiB/s vote by 0.065536; it is not a DDR PLL sensor.
# A one-time supported-OPP ceiling request. Thermal/scaling maxima still apply.
ddr=/sys/class/devfreq/soc:qcom,cpu-llcc-ddr-bw
if [ -r "$ddr/available_frequencies" ]; then
  ceiling=$(awk '{for(i=1;i<=NF;i++) if($i>m)m=$i} END{if(m>0)print m}' "$ddr/available_frequencies")
  case "$ceiling" in
    7980|10437)
      effective=$(cat "$ddr/max_freq" 2>/dev/null)
      [ "$effective" = "$ceiling" ] || set_node "$ddr/max_freq" "$ceiling"
      echo "DDR requested=$ceiling effective=$(cat "$ddr/max_freq" 2>/dev/null) MiB/s" ;;
    *) echo "DDR native ceiling left unchanged: $ceiling" ;;
  esac
fi
set_node /proc/sys/vm/swappiness 120
set_node /proc/sys/vm/page-cluster 0
set_node /proc/sys/vm/oom_kill_allocating_task 0
echo "Profile completed; failures=$errors. No resident loop."
exit "$errors"
