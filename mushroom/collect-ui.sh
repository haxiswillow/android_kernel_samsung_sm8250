#!/system/bin/sh
# Read-only Android UI/CPU/zram collector. Run on the PHONE with root.
umask 077
[ "$(id -u)" = 0 ] || { echo 'Execute com su: su -c "sh /sdcard/Download/Mushroom-UI-Collect.sh"'; exit 1; }
OUT=/sdcard/Download/Mushroom-UI-$(date +%Y%m%d-%H%M%S).txt
mkdir -p /sdcard/Download || exit 1
read_node() {
  [ -r "$1" ] || return 0
  echo "--- $1"
  cat "$1" 2>/dev/null
}
ui_threads() {
  for name in surfaceflinger system_server com.android.systemui; do
    for pid in $(pidof "$name" 2>/dev/null); do
      echo "=== $name pid=$pid"
      for task in /proc/"$pid"/task/*; do
        [ -d "$task" ] || continue
        case "$name" in
          system_server) comm=$(cat "$task/comm" 2>/dev/null); case "$comm" in *Display*|*Anim*|*Surface*|*Input*|android.ui|system_server) ;; *) continue ;; esac ;;
        esac
        echo "--- $task"
        sed -n '/^Name:/p;/^State:/p;/^Cpus_allowed_list:/p' "$task/status" 2>/dev/null
        cat "$task/cgroup" "$task/stat" 2>/dev/null
      done
    done
  done
}
echo 'Durante 12 segundos: puxe a barra e abra/feche aplicativos.'
{
  date
  uname -a
  echo '=== Device/ROM'
  getprop ro.product.device
  getprop ro.build.fingerprint
  for file in /sys/devices/system/cpu/online /sys/devices/system/cpu/offline /sys/devices/system/cpu/isolated /proc/swaps /proc/meminfo /proc/pressure/cpu /proc/pressure/memory /proc/pressure/io; do read_node "$file"; done
  echo '=== MGLRU / filesystems'
  for file in /sys/kernel/mm/lru_gen/enabled /sys/kernel/mm/lru_gen/min_ttl_ms /sys/kernel/debug/lru_gen /proc/mounts /proc/cmdline; do read_node "$file"; done
  echo '=== UCLAMP'
  for group in '' /top-app /foreground /background /system-background; do
    for node in cpu.uclamp.min cpu.uclamp.max cpu.uclamp.latency_sensitive; do read_node "/dev/cpuctl$group/$node"; done
  done
  echo '=== VM and root SchedTune'
  for file in /proc/sys/vm/swappiness /proc/sys/vm/page-cluster /proc/sys/vm/oom_kill_allocating_task /dev/stune/schedtune.boost /dev/stune/schedtune.prefer_idle; do read_node "$file"; done
  echo '=== Mushroom policy and devfreq'
  for file in /sys/kernel/mushroom_ui/*; do [ -r "$file" ] && read_node "$file"; done
  for dev in /sys/class/devfreq/*; do
    echo "=== devfreq device: $dev -> $(readlink -f "$dev")"
    for node in name governor available_frequencies min_freq max_freq cur_freq trans_stat mushroom_limits; do read_node "$dev/$node"; done
    for node in compatible name; do
      if [ -r "$dev/device/of_node/$node" ]; then
        echo "--- $dev/device/of_node/$node"
        tr '\000' '\n' < "$dev/device/of_node/$node"
      fi
    done
  done
  echo '=== GPU power constraints (cached frequency is not a physical clock probe)'
  for node in mushroom_gpu_status gpubusy default_pwrlevel max_pwrlevel min_pwrlevel thermal_pwrlevel popp; do read_node "/sys/class/kgsl/kgsl-3d0/$node"; done
  for file in /sys/module/governor_msm_adreno_tz/parameters/mushroom_gpu_guard /sys/module/devfreq/parameters/mushroom_trace_limits; do read_node "$file"; done
  echo '=== CPU policies'
  for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    for node in related_cpus affected_cpus scaling_governor scaling_min_freq scaling_max_freq cpuinfo_max_freq scaling_cur_freq; do read_node "$policy/$node"; done
    for file in "$policy"/schedutil/*; do [ -f "$file" ] && read_node "$file"; done
  done
  echo '=== Core control'
  for cpu in /sys/devices/system/cpu/cpu[0-9]*; do
    for node in online cpu_capacity thermal_pressure core_ctl/offline_delay_ms core_ctl/min_cpus core_ctl/max_cpus core_ctl/enable core_ctl/global_state core_ctl/busy_up_thres core_ctl/busy_down_thres; do read_node "$cpu/$node"; done
  done
  echo '=== Placement masks and hints'
  for group in top-app foreground system-background background; do
    for node in cpus effective_cpus; do read_node "/dev/cpuset/$group/$node"; done
    for node in schedtune.boost schedtune.prefer_idle schedtune.colocate; do read_node "/dev/stune/$group/$node"; done
  done
  for node in sched_boost sched_upmigrate sched_downmigrate sched_group_upmigrate sched_group_downmigrate sched_init_task_load sched_prefer_spread sched_user_hint sched_use_walt_cpu_util sched_use_walt_task_util; do read_node "/proc/sys/kernel/$node"; done
  echo '=== zRAM and KCAL'
  for node in disksize mem_limit mm_stat comp_algorithm; do read_node "/sys/block/zram0/$node"; done
  read_node /sys/module/zram/parameters/mushroom_legacy_2g_mb
  for file in /sys/devices/platform/kcal_ctrl.0/kcal*; do [ -f "$file" ] && read_node "$file"; done
  echo '=== UI thread masks and 12-second CPU sampling'
  ui_threads
  n=0
  while [ "$n" -lt 6 ]; do
    echo "=== sample $n"
    date
    cat /proc/stat
    read_node /sys/devices/system/cpu/online
    for node in mushroom_gpu_status gpubusy gpuclk devfreq/cur_freq devfreq/min_freq devfreq/max_freq; do read_node "/sys/class/kgsl/kgsl-3d0/$node"; done
    for policy in /sys/devices/system/cpu/cpufreq/policy*; do read_node "$policy/scaling_cur_freq"; done
    sleep 2
    n=$((n + 1))
  done
  ui_threads
  read_node /proc/sched_debug
  echo '=== Crash buffer'
  logcat -d -b crash -v threadtime 2>/dev/null
  echo '=== dmesg'
  dmesg 2>/dev/null
} > "$OUT" 2>&1
echo "Coleta salva: $OUT"
