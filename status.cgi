#!/bin/ash

echo "Content-type: text/html; charset=utf-8"
echo ""

if [ "$QUERY_STRING" = "data" ]; then
    #=========================================================================
    #  基础状态 (无需延迟)
    #=========================================================================
    CPU_TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "0")
    WIFI24G=$(cat /sys/class/net/wifi1/thermal/temp 2>/dev/null || echo "0")
    WIFI5G=$(cat /sys/class/net/wifi0/thermal/temp 2>/dev/null || echo "0")
    WIFI_GAME=$(cat /sys/class/net/wifi2/thermal/temp 2>/dev/null || echo "0")
    UPTIME=$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)

    MEM_INFO=$(awk '
        /^MemTotal:/     { total=$2 }
        /^MemAvailable:/ { avail=$2 }
        END {
            if (total > 0) {
                used = total - avail
                pct  = int(used * 100 / total)
                printf "%d|%d|%d", used, total, pct
            } else {
                printf "0|0|0"
            }
        }
    ' /proc/meminfo 2>/dev/null)

    #=========================================================================
    #  ECM / NSS 加速统计
    #=========================================================================
    DS=/sys/kernel/debug/ecm/ecm_db/connection_count_simple
    DT=/sys/kernel/debug/ecm/ecm_db/connection_count

    _get() {
        _k="$1"; _f="$2"
        awk -v k="$_k" '{ for(i=1;i<=NF;i++) if($i==k) { print $(i+1); exit } }' "$_f" 2>/dev/null || echo "0"
    }
    _cat() { cat "$1" 2>/dev/null || echo "0"; }

    if [ -d /sys/kernel/debug/ecm ]; then
        ECM_AVAIL=1
        db_tcp=$(_get tcp "$DS");  db_udp=$(_get udp "$DS");  db_other=$(_get other "$DS")
        db_total=$(_cat "$DT")
        [ "$db_total" = "0" ] && db_total=$(( db_tcp + db_udp + db_other ))

        v4_acc=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv4/accelerated_count)
        v4_tcp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv4/tcp_accelerated_count)
        v4_udp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv4/udp_accelerated_count)
        v4_icmp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv4/non_ported_accelerated_count)

        v6_acc=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv6/accelerated_count)
        v6_tcp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv6/tcp_accelerated_count)
        v6_udp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv6/udp_accelerated_count)
        v6_icmp=$(_cat /sys/kernel/debug/ecm/ecm_nss_ipv6/non_ported_accelerated_count)

        ECM_DATA="${ECM_AVAIL}|${v4_acc}|${v6_acc}|${db_total}|${v4_tcp}|${v4_udp}|${v6_tcp}|${v6_udp}|${v4_icmp}|${v6_icmp}|${db_tcp}|${db_udp}|${db_other}"
    else
        ECM_AVAIL=0
        ECM_DATA="0||||||||||||"
    fi

    #=========================================================================
    #  CPU 占用率 + 网络速率 (采样间隔 1 秒)
    #=========================================================================
    read_cpu_stat() {
        awk '/^cpu /{
            total=$2+$3+$4+$5+$6+$7+$8;
            idle=$5+$6;
            printf "%d %d", total, idle
        }' /proc/stat
    }

    WAN_IF=$(awk '$2=="00000000" && $1!="Iface"{print $1; exit}' /proc/net/route 2>/dev/null)

    if [ -z "$WAN_IF" ] || [ ! -d "/sys/class/net/${WAN_IF}" ]; then
        for iface in pppoe-wan eth0 eth1; do
            if [ -d "/sys/class/net/${iface}" ]; then
                WAN_IF="$iface"
                break
            fi
        done
    fi
    [ -z "$WAN_IF" ] && WAN_IF="eth0"

    read_net_sysfs() {
        local rx=0 tx=0
        rx=$(cat /sys/class/net/${WAN_IF}/statistics/rx_bytes 2>/dev/null || echo 0)
        tx=$(cat /sys/class/net/${WAN_IF}/statistics/tx_bytes 2>/dev/null || echo 0)
        printf "%d %d" "$rx" "$tx"
    }

    CPU1=$(read_cpu_stat)
    NET1=$(read_net_sysfs)
    sleep 1
    CPU2=$(read_cpu_stat)
    NET2=$(read_net_sysfs)

    cpu1_total=${CPU1% *};  cpu1_idle=${CPU1#* }
    cpu2_total=${CPU2% *};  cpu2_idle=${CPU2#* }
    cpu_delta=$(( cpu2_total - cpu1_total ))
    idle_delta=$(( cpu2_idle - cpu1_idle ))
    if [ "$cpu_delta" -gt 0 ]; then
        CPU_PCT=$(( 100 - idle_delta * 100 / cpu_delta ))
        [ "$CPU_PCT" -lt 0 ] && CPU_PCT=0
        [ "$CPU_PCT" -gt 100 ] && CPU_PCT=100
    else
        CPU_PCT=0
    fi

    net1_rx=${NET1% *};  net1_tx=${NET1#* }
    net2_rx=${NET2% *};  net2_tx=${NET2#* }
    RX_SPEED=$(( net2_rx - net1_rx ))
    TX_SPEED=$(( net2_tx - net1_tx ))
    [ "$RX_SPEED" -lt 0 ] && RX_SPEED=0
    [ "$TX_SPEED" -lt 0 ] && TX_SPEED=0

    echo "${CPU_TEMP}|${WIFI24G}|${WIFI5G}|${WIFI_GAME}|${MEM_INFO}|${UPTIME}|${ECM_DATA}|${CPU_PCT}|${RX_SPEED}|${TX_SPEED}|${net2_rx}|${net2_tx}|${WAN_IF}"
    exit 0
fi

cat <<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>路由器实时状态监控</title>
    <style>
        /* ================================================================
           CSS 变量 —— 浅色 / 深色
           ================================================================ */
        :root {
            --bg:            #f0f2f5;
            --card-bg:       #ffffff;
            --card-shadow:   0 4px 24px rgba(0,0,0,0.07);
            --text-title:    #1e293b;
            --text-label:    #475569;
            --text-value:    #2563eb;
            --text-uptime:   #16a34a;
            --text-muted:    #94a3b8;
            --text-detail:   #64748b;
            --item-bg:       #f8fafc;
            --item-hover:    #f1f5f9;
            --border:        #e2e8f0;
            --progress-bg:   #e2e8f0;
            --progress-mem:  linear-gradient(90deg, #4ecdc4, #44b7a8);
            --progress-cpu:  linear-gradient(90deg, #667eea, #5a67d8);
            --progress-cov:  linear-gradient(90deg, #f59e0b, #d97706);
            --toggle-bg:     #e2e8f0;
            --toggle-icon:   #fbbf24;
            --wifi-card-bg:  #f8fafc;
        }

        .dark {
            --bg:            #0f172a;
            --card-bg:       #1e293b;
            --card-shadow:   0 4px 32px rgba(0,0,0,0.35);
            --text-title:    #e2e8f0;
            --text-label:    #cbd5e1;
            --text-value:    #60a5fa;
            --text-uptime:   #4ade80;
            --text-muted:    #64748b;
            --text-detail:   #94a3b8;
            --item-bg:       #263348;
            --item-hover:    #2d3d56;
            --border:        #334155;
            --progress-bg:   #334155;
            --progress-mem:  linear-gradient(90deg, #4ecdc4, #44b7a8);
            --progress-cpu:  linear-gradient(90deg, #818cf8, #6366f1);
            --progress-cov:  linear-gradient(90deg, #fbbf24, #f59e0b);
            --toggle-bg:     #334155;
            --toggle-icon:   #cbd5e1;
            --wifi-card-bg:  #263348;
        }

        @media (prefers-color-scheme: dark) {
            :root:not(.light) {
                --bg:            #0f172a;
                --card-bg:       #1e293b;
                --card-shadow:   0 4px 32px rgba(0,0,0,0.35);
                --text-title:    #e2e8f0;
                --text-label:    #cbd5e1;
                --text-value:    #60a5fa;
                --text-uptime:   #4ade80;
                --text-muted:    #64748b;
                --text-detail:   #94a3b8;
                --item-bg:       #263348;
                --item-hover:    #2d3d56;
                --border:        #334155;
                --progress-bg:   #334155;
                --progress-mem:  linear-gradient(90deg, #4ecdc4, #44b7a8);
                --progress-cpu:  linear-gradient(90deg, #818cf8, #6366f1);
                --progress-cov:  linear-gradient(90deg, #fbbf24, #f59e0b);
                --toggle-bg:     #334155;
                --toggle-icon:   #cbd5e1;
                --wifi-card-bg:  #263348;
            }
        }

        /* ================================================================
           全局
           ================================================================ */
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
            background: var(--bg);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 16px;
            transition: background 0.3s ease;
        }

        .card {
            background: var(--card-bg);
            padding: 28px 22px 22px;
            border-radius: 18px;
            box-shadow: var(--card-shadow);
            width: 100%;
            max-width: 480px;
            transition: background 0.3s ease, box-shadow 0.3s ease;
            position: relative;
        }

        /* ---- 标题行 ---- */
        .header-row {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
            position: relative;
        }
        .header-row h2 {
            color: var(--text-title);
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        /* ---- 暗色模式按钮 ---- */
        .theme-toggle {
            position: absolute;
            right: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 40px; height: 40px;
            border-radius: 50%;
            border: none;
            background: var(--toggle-bg);
            cursor: pointer;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.3s ease, transform 0.15s ease;
            color: var(--toggle-icon);
            line-height: 1;
        }
        .theme-toggle:active { transform: translateY(-50%) scale(0.92); }
        .theme-toggle:hover  { filter: brightness(0.95); }

        /* ---- 分段标题 ---- */
        .section-label {
            margin: 16px 0 6px 4px;
            font-weight: 700;
            color: var(--text-muted);
            font-size: 11px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            border-top: 1px solid var(--border);
            padding-top: 14px;
        }

        /* ---- 数据行 ---- */
        .item {
            margin: 7px 0;
            padding: 13px 16px;
            background: var(--item-bg);
            border-radius: 11px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            transition: background 0.2s ease;
        }
        .item:hover { background: var(--item-hover); }

        .item-wrap {
            flex-wrap: wrap;
        }

        .label {
            font-weight: 600;
            color: var(--text-label);
            font-size: 14px;
            white-space: nowrap;
            flex-shrink: 0;
            display: flex;
            align-items: center;
            gap: 7px;
        }
        .label .ico { font-size: 17px; flex-shrink: 0; }

        .value {
            color: var(--text-value);
            font-weight: 700;
            font-size: 15px;
            text-align: right;
            white-space: nowrap;
        }
        .value-uptime {
            color: var(--text-uptime);
            font-weight: 700;
            font-size: 14px;
        }

        /* ================================================================
           WiFi 三卡横排
           ================================================================ */
        .wifi-row {
            display: flex;
            gap: 9px;
            margin: 7px 0;
        }
        .wifi-card {
            flex: 1;
            background: var(--wifi-card-bg);
            border-radius: 12px;
            padding: 14px 6px 12px;
            text-align: center;
            transition: background 0.2s ease;
        }
        .wifi-card:hover { background: var(--item-hover); }
        .wifi-card-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-label);
            margin-bottom: 5px;
            white-space: nowrap;
        }
        .wifi-card-temp {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-value);
        }

        /* ================================================================
           网络双列布局
           ================================================================ */
        .item.dual-col {
            display: block;
            padding: 10px 14px;
        }
        .dual-inner {
            display: flex;
            width: 100%;
            gap: 16px;
        }
        .dual-half {
            flex: 1;
            text-align: center;
        }
        .dual-label {
            font-size: 12px;
            font-weight: 600;
            color: var(--text-label);
            margin-bottom: 3px;
        }
        .dual-value {
            font-size: 16px;
            font-weight: 700;
            color: var(--text-value);
        }
        .dual-value.sub {
            font-size: 13px;
            color: var(--text-detail);
            font-weight: 600;
        }

        /* ================================================================
           网络标题 + WAN 徽章
           ================================================================ */
        .net-title {
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: nowrap;
        }
        .wan-badge {
            font-size: 10px;
            background: var(--progress-bg);
            padding: 3px 10px;
            border-radius: 20px;
            color: var(--text-muted);
            font-weight: 500;
            letter-spacing: 0;
            text-transform: none;
            white-space: nowrap;
            flex-shrink: 0;
        }

        /* ================================================================
           详细子文本
           ================================================================ */
        .detail-row {
            width: 100%;
            font-size: 11px;
            color: var(--text-detail);
            padding: 0 0 0 30px;
            margin: -3px 0 6px 0;
            white-space: nowrap;
        }

        /* ================================================================
           进度条
           ================================================================ */
        .progress-wrap {
            width: 100%;
            margin-top: 6px;
        }
        .progress-bar {
            width: 100%;
            height: 7px;
            background: var(--progress-bg);
            border-radius: 10px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 10px;
            transition: width 0.55s ease;
            min-width: 0;
        }
        .progress-fill.mem    { background: var(--progress-mem); }
        .progress-fill.cpu    { background: var(--progress-cpu); }
        .progress-fill.cov    { background: var(--progress-cov); }
        .progress-fill.warn   { background: linear-gradient(90deg, #f0ad4e, #ec971f); }
        .progress-fill.danger { background: linear-gradient(90deg, #ef4444, #dc2626); }

        /* ---- 页脚 ---- */
        .footer {
            margin-top: 20px;
            font-size: 12px;
            color: var(--text-muted);
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="card">

        <!-- ========================================== 标题 + 主题 ========== -->
        <div class="header-row">
            <h2>📡 路由器状态监控</h2>
            <button class="theme-toggle" id="themeBtn" title="切换深色/浅色模式" aria-label="切换主题">🌙</button>
        </div>

        <!-- ========================================== 系统状态 ============= -->
        <div class="item">
            <span class="label"><span class="ico">⏱️</span>运行时间</span>
            <span class="value value-uptime" id="uptime">加载中...</span>
        </div>

        <div class="item">
            <span class="label"><span class="ico">🌡️</span>CPU 核心</span>
            <span class="value" id="cpu">加载中...</span>
        </div>

        <!-- ==== CPU 占用率 (紧接 CPU 温度) ==== -->
        <div class="item item-wrap">
            <div style="display:flex;justify-content:space-between;align-items:center;width:100%;gap:10px;">
                <span class="label"><span class="ico">🧠</span>CPU 占用</span>
                <span class="value" id="cpuPct">--%</span>
            </div>
            <div class="progress-wrap">
                <div class="progress-bar">
                    <div class="progress-fill cpu" id="cpuBar" style="width:0%"></div>
                </div>
            </div>
        </div>

        <!-- ==== WiFi 三频段横排 ==== -->
        <div class="wifi-row">
            <div class="wifi-card">
                <div class="wifi-card-label">📶 2.4G</div>
                <div class="wifi-card-temp" id="wifi24g">--°C</div>
            </div>
            <div class="wifi-card">
                <div class="wifi-card-label">📶 5.2G</div>
                <div class="wifi-card-temp" id="wifi5g">--°C</div>
            </div>
            <div class="wifi-card">
                <div class="wifi-card-label">📶 5.8G</div>
                <div class="wifi-card-temp" id="wifigame">--°C</div>
            </div>
        </div>

        <!-- ==== 内存 ==== -->
        <div class="item item-wrap">
            <div style="display:flex;justify-content:space-between;align-items:center;width:100%;gap:10px;">
                <span class="label"><span class="ico">💾</span>内存使用</span>
                <span class="value" id="memory">加载中...</span>
            </div>
            <div class="progress-wrap">
                <div class="progress-bar">
                    <div class="progress-fill mem" id="memBar" style="width:0%"></div>
                </div>
            </div>
        </div>

        <!-- ========================================== 网络使用 ============= -->
        <div class="section-label net-title">
            <span>🌐 网络使用</span>
            <span class="wan-badge" id="wanIface"></span>
        </div>

        <!-- 下载 / 上传速度 一行 -->
        <div class="item dual-col">
            <div class="dual-inner">
                <div class="dual-half">
                    <div class="dual-label">📥 下载速度</div>
                    <div class="dual-value" id="rxSpeed">--</div>
                </div>
                <div class="dual-half">
                    <div class="dual-label">📤 上传速度</div>
                    <div class="dual-value" id="txSpeed">--</div>
                </div>
            </div>
        </div>

        <!-- 累计下载 / 累计上传 一行 -->
        <div class="item dual-col">
            <div class="dual-inner">
                <div class="dual-half">
                    <div class="dual-label">📊 累计下载</div>
                    <div class="dual-value sub" id="rxBytes">--</div>
                </div>
                <div class="dual-half">
                    <div class="dual-label">📊 累计上传</div>
                    <div class="dual-value sub" id="txBytes">--</div>
                </div>
            </div>
        </div>

        <!-- ========================================== NSS 加速引擎 ========= -->
        <div class="section-label" id="ecmSectionLabel" style="display:none;">⚡ NSS 硬件加速</div>

        <div class="item" id="ecmV4Row" style="display:none;">
            <span class="label"><span class="ico">🔵</span>IPv4 加速</span>
            <span class="value" id="ecmV4Acc">-</span>
        </div>
        <div class="detail-row" id="ecmV4Detail" style="display:none;"></div>

        <div class="item" id="ecmV6Row" style="display:none;">
            <span class="label"><span class="ico">🟣</span>IPv6 加速</span>
            <span class="value" id="ecmV6Acc">-</span>
        </div>
        <div class="detail-row" id="ecmV6Detail" style="display:none;"></div>

        <div class="item" id="ecmDbRow" style="display:none;">
            <span class="label"><span class="ico">🗄️</span>连接总数</span>
            <span class="value" id="ecmDbTotal">-</span>
        </div>
        <div class="detail-row" id="ecmDbDetail" style="display:none;"></div>

        <div class="item item-wrap" id="ecmCovRow" style="display:none;">
            <div style="display:flex;justify-content:space-between;align-items:center;width:100%;gap:10px;">
                <span class="label"><span class="ico">📊</span>加速覆盖率</span>
                <span class="value" id="ecmCoverage">-</span>
            </div>
            <div class="progress-wrap">
                <div class="progress-bar">
                    <div class="progress-fill cov" id="covBar" style="width:0%"></div>
                </div>
            </div>
        </div>

        <div class="footer">实时刷新 · 温度 · 网络 · NSS 加速</div>
    </div>

<script>
/* ===================================================================
   全局变量
   =================================================================== */
var uptime = 0;
var timer = null;
var stopped = false;
var lastRender = {};
var BUF = 4;
var tempBufs = { cpu:[], w24:[], w5:[], wg:[] };

/* ===================================================================
   暗色模式
   =================================================================== */
var STORAGE_KEY = 'router-monitor-theme';

function getSavedTheme() {
    try { return localStorage.getItem(STORAGE_KEY); } catch(e) { return null; }
}
function saveTheme(mode) {
    try { localStorage.setItem(STORAGE_KEY, mode); } catch(e) {}
}

function applyTheme(mode) {
    var html = document.documentElement;
    html.classList.remove('dark', 'light');
    if (mode === 'dark') html.classList.add('dark');
    else if (mode === 'light') html.classList.add('light');
    updateThemeIcon(mode);
}

function updateThemeIcon(mode) {
    var btn = document.getElementById('themeBtn');
    if (mode === 'dark')       { btn.textContent = '☀️'; btn.title = '切换浅色模式'; }
    else if (mode === 'light') { btn.textContent = '🌙'; btn.title = '切换深色模式'; }
    else {
        var sysDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        btn.textContent = sysDark ? '☀️' : '🌙';
        btn.title = sysDark ? '切换浅色模式' : '切换深色模式';
    }
}

function cycleTheme() {
    var cur = getSavedTheme() || 'auto';
    var next = (cur === 'auto') ? 'dark' : (cur === 'dark' ? 'light' : 'auto');
    saveTheme(next);
    applyTheme(next);
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function() {
    if ((getSavedTheme() || 'auto') === 'auto') updateThemeIcon('auto');
});

document.getElementById('themeBtn').addEventListener('click', cycleTheme);

(function initTheme() {
    var saved = getSavedTheme();
    applyTheme(saved === 'dark' || saved === 'light' ? saved : 'auto');
})();

/* ===================================================================
   工具函数
   =================================================================== */
function fmt(n) { return (parseInt(n) || 0).toLocaleString(); }

function formatTime(s) {
    s = parseInt(s) || 0;
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    return d + '天 ' + h + '时 ' + m + '分 ' + sec + '秒';
}

function formatBytes(b) {
    b = parseInt(b) || 0;
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
    return (b / 1073741824).toFixed(2) + ' GB';
}

function formatSpeed(bps) {
    bps = parseInt(bps) || 0;
    if (bps < 1024) return bps + ' B/s';
    if (bps < 1048576) return (bps / 1024).toFixed(1) + ' KB/s';
    if (bps < 1073741824) return (bps / 1048576).toFixed(1) + ' MB/s';
    return (bps / 1073741824).toFixed(2) + ' GB/s';
}

function setIf(id, text) {
    if (lastRender[id] !== text) {
        document.getElementById(id).innerText = text;
        lastRender[id] = text;
    }
}

function setProgress(id, pct, classes) {
    var bar = document.getElementById(id);
    bar.style.width = pct + '%';
    bar.className = bar.className.replace(/\b(warn|danger)\b/g, '').trim();
    if (classes) bar.classList.add(classes);
}

function startTimer() {
    if (timer) clearInterval(timer);
    stopped = false;
    timer = setInterval(function() {
        uptime++;
        document.getElementById('uptime').innerText = formatTime(uptime);
    }, 1000);
}

function stopTimer() {
    clearInterval(timer);
    stopped = true;
    uptime = 0;
    document.getElementById('uptime').innerText = formatTime(0);
}

/* ===================================================================
   温度更新
   =================================================================== */
function updateTemp(id, raw, buf) {
    raw = parseInt(raw);
    if (!isNaN(raw) && raw > 0) {
        buf.push(raw);
        if (buf.length > BUF) buf.shift();
        setIf(id, Math.round(buf.reduce(function(a,b){return a+b;},0) / buf.length) + '°C');
    }
}

/* ===================================================================
   内存更新
   =================================================================== */
function updateMemory(usedKb, totalKb, pct) {
    usedKb = parseInt(usedKb) || 0;
    totalKb = parseInt(totalKb) || 0;
    pct = parseInt(pct) || 0;

    var text = totalKb > 0
        ? Math.round(usedKb/1024) + ' MB / ' + Math.round(totalKb/1024) + ' MB (' + pct + '%)'
        : '读取异常';
    setIf('memory', text);

    var cls = '';
    if (pct >= 90) cls = 'danger';
    else if (pct >= 70) cls = 'warn';
    setProgress('memBar', pct, cls);
}

/* ===================================================================
   CPU 占用率更新
   =================================================================== */
function updateCpu(pct) {
    pct = parseInt(pct) || 0;
    setIf('cpuPct', pct + '%');

    var cls = '';
    if (pct >= 85) cls = 'danger';
    else if (pct >= 60) cls = 'warn';
    setProgress('cpuBar', pct, cls);
}

/* ===================================================================
   网络更新
   =================================================================== */
function updateNetwork(rxSpeed, txSpeed, rxBytes, txBytes, wanIf) {
    setIf('rxSpeed',  formatSpeed(rxSpeed));
    setIf('txSpeed',  formatSpeed(txSpeed));
    setIf('rxBytes',  formatBytes(rxBytes));
    setIf('txBytes',  formatBytes(txBytes));
    if (wanIf) setIf('wanIface', wanIf);
}

/* ===================================================================
   ECM 更新
   =================================================================== */
var ecmWasAvail = false;

function updateEcm(data, off) {
    var avail = parseInt(data[off]) === 1;

    if (!avail) {
        if (ecmWasAvail) {
            document.getElementById('ecmSectionLabel').style.display = 'none';
            ['ecmV4Row','ecmV6Row','ecmDbRow','ecmCovRow'].forEach(function(id) {
                document.getElementById(id).style.display = 'none';
            });
            ['ecmV4Detail','ecmV6Detail','ecmDbDetail'].forEach(function(id) {
                document.getElementById(id).style.display = 'none';
            });
            ecmWasAvail = false;
        }
        return;
    }

    if (!ecmWasAvail) {
        document.getElementById('ecmSectionLabel').style.display = '';
        ['ecmV4Row','ecmV6Row','ecmDbRow','ecmCovRow'].forEach(function(id) {
            document.getElementById(id).style.display = '';
        });
        ['ecmV4Detail','ecmV6Detail','ecmDbDetail'].forEach(function(id) {
            document.getElementById(id).style.display = '';
        });
    }
    ecmWasAvail = true;

    var v4_acc   = parseInt(data[off+1]) || 0;
    var v6_acc   = parseInt(data[off+2]) || 0;
    var db_total = parseInt(data[off+3]) || 0;
    var v4_tcp   = parseInt(data[off+4]) || 0;
    var v4_udp   = parseInt(data[off+5]) || 0;
    var v6_tcp   = parseInt(data[off+6]) || 0;
    var v6_udp   = parseInt(data[off+7]) || 0;
    var v4_icmp  = parseInt(data[off+8]) || 0;
    var v6_icmp  = parseInt(data[off+9]) || 0;
    var db_tcp   = parseInt(data[off+10]) || 0;
    var db_udp   = parseInt(data[off+11]) || 0;
    var db_other = parseInt(data[off+12]) || 0;

    setIf('ecmV4Acc', fmt(v4_acc));
    document.getElementById('ecmV4Detail').innerText =
        'TCP ' + fmt(v4_tcp) + '  ·  UDP ' + fmt(v4_udp) + '  ·  ICMP ' + fmt(v4_icmp);

    setIf('ecmV6Acc', fmt(v6_acc));
    document.getElementById('ecmV6Detail').innerText =
        'TCP ' + fmt(v6_tcp) + '  ·  UDP ' + fmt(v6_udp) + '  ·  ICMP ' + fmt(v6_icmp);

    setIf('ecmDbTotal', fmt(db_total));
    document.getElementById('ecmDbDetail').innerText =
        'TCP ' + fmt(db_tcp) + '  ·  UDP ' + fmt(db_udp) + '  ·  Other ' + fmt(db_other);

    var totalAcc = v4_acc + v6_acc;
    var covPct = db_total > 0 ? Math.round(totalAcc * 100 / db_total) : 0;
    setIf('ecmCoverage', covPct + '%  (' + fmt(totalAcc) + ' / ' + fmt(db_total) + ')');

    var cls = '';
    if (covPct < 50) cls = 'danger';
    else if (covPct < 80) cls = 'warn';
    setProgress('covBar', covPct, cls);
}

/* ===================================================================
   数据拉取
   字段索引 (27 个, | 分隔):
     0:  CPU 温度 (raw)
     1:  2.4G 温度
     2:  5.2G 温度
     3:  5.8G 温度
     4:  内存 used (KB)
     5:  内存 total (KB)
     6:  内存 pct
     7:  Uptime (秒)
     8:  ECM avail (1/0)
     9:  IPv4 accelerated
     10: IPv6 accelerated
     11: DB total connections
     12: IPv4 TCP acc
     13: IPv4 UDP acc
     14: IPv6 TCP acc
     15: IPv6 UDP acc
     16: IPv4 ICMP acc
     17: IPv6 ICMP acc
     18: DB TCP
     19: DB UDP
     20: DB Other
     21: CPU pct
     22: RX speed (bytes/s)
     23: TX speed (bytes/s)
     24: RX total bytes
     25: TX total bytes
     26: WAN interface name
   =================================================================== */
function fetchData() {
    if (stopped) return;
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '?data', true);
    xhr.timeout = 5000;

    xhr.onload = function() {
        if (xhr.status !== 200) return stopTimer();

        var d = (xhr.responseText || '').split('|');
        if (d.length < 27) return stopTimer();

        var real = parseInt(d[7]) || 0;
        if (real < uptime - 10) return stopTimer();
        uptime = real;

        updateTemp('cpu',      d[0], tempBufs.cpu);
        updateTemp('wifi24g',  d[1], tempBufs.w24);
        updateTemp('wifi5g',   d[2], tempBufs.w5);
        updateTemp('wifigame', d[3], tempBufs.wg);

        updateMemory(d[4], d[5], d[6]);
        updateEcm(d, 8);
        updateCpu(d[21]);
        updateNetwork(d[22], d[23], d[24], d[25], d[26]);
    };

    xhr.onerror = xhr.ontimeout = stopTimer;
    xhr.send();
}

/* ===================================================================
   启动
   =================================================================== */
(function init() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '?data', true);
    xhr.timeout = 5000;

    xhr.onload = function() {
        if (xhr.status !== 200) { startTimer(); fetchData(); setInterval(fetchData, 3000); return; }
        var d = (xhr.responseText || '').split('|');
        if (d.length >= 27) {
            uptime = parseInt(d[7]) || 0;
            updateTemp('cpu',      d[0], tempBufs.cpu);
            updateTemp('wifi24g',  d[1], tempBufs.w24);
            updateTemp('wifi5g',   d[2], tempBufs.w5);
            updateTemp('wifigame', d[3], tempBufs.wg);
            updateMemory(d[4], d[5], d[6]);
            updateEcm(d, 8);
            updateCpu(d[21]);
            updateNetwork(d[22], d[23], d[24], d[25], d[26]);
        }
        startTimer();
        setInterval(fetchData, 3000);
    };

    xhr.onerror = xhr.ontimeout = function() {
        startTimer();
        setInterval(fetchData, 3000);
    };
    xhr.send();
})();
</script>
</body>
</html>
HTML