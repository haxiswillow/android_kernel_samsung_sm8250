#!/system/bin/sh
# Bounded diagnosis; --native-ddr requests an existing bandwidth OPP once.
umask 077
[ "$(id -u)" = 0 ] || { echo 'Run on the phone with su'; exit 1; }
# Do not inherit caller errexit; tracing is optional on older builds.
set +e
BASE=/data/local/tmp/mushroom-gpu-ddr
DDR=/sys/class/devfreq/soc:qcom,cpu-llcc-ddr-bw
GPU=/sys/class/kgsl/kgsl-3d0
mkdir -p "$BASE" || exit 1
STATE=$BASE/ddr-before.tsv
case "${1:-}" in
  --restore)
    [ -f "$STATE" ] || { echo 'No DDR ceiling backup'; exit 0; }
    IFS='|' read -r path before after < "$STATE"
    [ "$path" = "$DDR/max_freq" ] || { echo 'Unexpected backup'; exit 1; }
    current=$(cat "$path") || exit 1
    [ "$current" = "$after" ] || { echo 'Later DDR setting preserved'; exit 1; }
    printf '%s\n' "$before" > "$path" || exit 1
    rm -f "$STATE"
    echo 'Previous DDR vote ceiling restored'; exit 0 ;;
  --native-ddr)
    ceiling=$(awk '{for(i=1;i<=NF;i++) if($i>m)m=$i} END{if(m>0)print m}' "$DDR/available_frequencies")
    case "$ceiling" in 7980|10437) ;; *) echo "Unexpected OPP table: $ceiling; unchanged"; exit 1 ;; esac
    before=$(cat "$DDR/max_freq") || exit 1
    if [ ! -f "$STATE" ]; then
      printf '%s|%s|%s\n' "$DDR/max_freq" "$before" "$ceiling" > "$STATE" || exit 1
    fi
    effective=$(cat "$DDR/max_freq") || exit 1
    if [ "$effective" != "$ceiling" ]; then
      if ! printf '%s\n' "$ceiling" > "$DDR/max_freq"; then
        effective=$(cat "$DDR/max_freq")
        [ "$effective" = "$ceiling" ] || {
          echo "DDR max_freq write rejected: effective=$effective target=$ceiling"; exit 1;
        }
        echo 'Write reported an error but the requested ceiling is active.'
      fi
    fi
    effective=$(cat "$DDR/max_freq")
    echo "DDR vote ceiling: requested=$ceiling effective=$effective MiB/s. This is not a PLL overclock." ;;
  --status)
    uname -r
    for node in /sys/kernel/mm/lru_gen/enabled \
      /proc/sys/kernel/mushroom_uclamp_top_app \
      /proc/sys/kernel/mushroom_uclamp_foreground \
      /sys/module/devfreq/parameters/mushroom_gpu_native \
      /sys/module/devfreq/parameters/mushroom_ddr_native \
      "$GPU/mushroom_gpu_status" "$GPU/mushroom_gpu_min_hz" \
      "$GPU/mushroom_gpu_max_hz" "$DDR/max_freq"; do
      [ -r "$node" ] && { echo "$node"; cat "$node"; }
    done
    exit 0 ;;
  '') ;;
  *) echo 'Usage: sh GPU-DDR-Check.sh [--native-ddr|--restore|--status]'; exit 2 ;;
esac
OUT=/sdcard/Download/Mushroom-GPU-DDR-$(date +%Y%m%d-%H%M%S).txt
mkdir -p /sdcard/Download || exit 1
TRACE_STATE=$BASE/trace-before-$$.tsv
: > "$TRACE_STATE" || exit 1
restore_trace() {
  [ -f "$TRACE_STATE" ] || return 0
  while IFS='|' read -r trace_node trace_before; do
    trace_now=$(cat "$trace_node" 2>/dev/null)
    case "$trace_now" in 1|Y)
      printf '%s\n' "$trace_before" > "$trace_node" ||
        echo "Could not restore optional trace: $trace_node" ;;
    esac
  done < "$TRACE_STATE"
  rm -f "$TRACE_STATE"
}
trap restore_trace EXIT
trap 'exit 130' INT TERM
for trace_node in /sys/module/*/parameters/mushroom_trace_limits; do
  [ -f "$trace_node" ] || continue
  trace_before=$(cat "$trace_node") || continue
  printf '%s|%s\n' "$trace_node" "$trace_before" >> "$TRACE_STATE" || exit 1
  if ! printf '1\n' > "$trace_node"; then
    echo "Optional trace unavailable: $trace_node; continuing."
  fi
done
read_node() { [ -r "$1" ] && { echo "--- $1"; cat "$1" 2>/dev/null; }; return 0; }
echo 'For 20 seconds: idle on launcher, then scroll Telegram or play Minecraft.'
{
  date
  uname -a
  echo 'FKM formula: MHz=round(raw_MiB_per_second * 0.065536); 451 display can represent a native 1804-MHz-equivalent vote.'
  for n in gpu_available_frequencies devfreq/available_governors default_pwrlevel max_pwrlevel min_pwrlevel thermal_pwrlevel popp; do read_node "$GPU/$n"; done
  for n in available_frequencies min_freq max_freq governor mushroom_limits; do read_node "$DDR/$n"; done
  read_node /sys/module/governor_msm_adreno_tz/parameters/mushroom_gpu_guard
  i=0
  while [ "$i" -lt 20 ]; do
    echo "=== sample $i"
    read_node /proc/uptime
    for n in mushroom_gpu_status gpubusy gpuclk devfreq/cur_freq devfreq/min_freq devfreq/max_freq devfreq/mushroom_limits; do read_node "$GPU/$n"; done
    for n in cur_freq min_freq max_freq mushroom_limits; do read_node "$DDR/$n"; done
    for policy in /sys/devices/system/cpu/cpufreq/policy*; do read_node "$policy/scaling_cur_freq"; done
    sleep 1
    i=$((i + 1))
  done
  echo '=== Kernel limit-writer trace and GPU errors'
  dmesg | grep -Ei 'mushroom-dvfs:|DCVS update failed|adreno|gmu|gpu fault|iommu.*fault' | tail -160
} > "$OUT" 2>&1
restore_trace
echo "Saved: $OUT"
