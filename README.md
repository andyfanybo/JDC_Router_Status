# JDC Router Status

京东云（JD Cloud）亚瑟/雅典娜路由器实时状态监控 CGI 脚本。

基于 OpenWrt 系统，通过 Web 页面实时展示路由器的 CPU 温度、WiFi 芯片温度、内存使用率、网络速率、NSS 硬件加速状态等信息。

## 功能特性

- 🌡️ **温度监控**：CPU 核心温度、2.4G / 5.2G / 5.8G 三频 WiFi 芯片温度
- 🧠 **系统状态**：CPU 占用率（含进度条）、内存使用情况、运行时长
- 🌐 **网络信息**：实时下载/上传速率、累计流量统计、WAN 口自动识别
- ⚡ **NSS 硬件加速**：IPv4/IPv6 加速连接数（TCP/UDP/ICMP）、连接总数、加速覆盖率
- 🌙 **深色/浅色模式**：支持手动切换和跟随系统主题，偏好自动记忆
- 🔄 **自动刷新**：每 3 秒自动拉取最新数据，运行时长独立计时
- 📱 **响应式布局**：适配手机和桌面浏览器

## 适用设备

- 京东云 AX1800 Pro（亚瑟）
- 京东云 AX6600（雅典娜）
- 其他基于 Qualcomm IPQ60xx 平台的 OpenWrt 路由器（需支持 ECM/NSS）

## 安装使用

1. 将 `status.cgi` 上传至路由器的 `/www/cgi-bin/` 目录：

```bash
scp status.cgi root@192.168.68.1:/www/cgi-bin/
```

2. SSH 登录路由器，赋予执行权限：

```bash
chmod +x /www/cgi-bin/status.cgi
```

3. 浏览器访问以下地址即可查看状态页面：

```
http://192.168.68.1/cgi-bin/status.cgi
```

> 💡 如果路由器管理地址不是 `192.168.68.1`，请替换为实际的 IP 地址。

## 技术原理

脚本分为两部分：

- **Shell 后端**（`?data` 参数）：通过读取 `/sys/class/thermal/`、`/proc/meminfo`、`/proc/stat`、`/sys/kernel/debug/ecm/` 等系统接口，采集实时数据并以管道符分隔返回。
- **HTML/JS 前端**：纯原生实现，无外部依赖，通过 AJAX 定时拉取后端数据并渲染到页面。

### 数据采集来源

| 数据项 | 来源路径 |
|--------|----------|
| CPU 温度 | `/sys/class/thermal/thermal_zone0/temp` |
| 2.4G WiFi 温度 | `/sys/class/net/wifi1/thermal/temp` |
| 5.2G WiFi 温度 | `/sys/class/net/wifi0/thermal/temp` |
| 5.8G WiFi 温度 | `/sys/class/net/wifi2/thermal/temp` |
| 内存信息 | `/proc/meminfo` |
| CPU 占用率 | `/proc/stat`（1 秒采样间隔） |
| 网络速率 | `/sys/class/net/<wan_if>/statistics/` |
| NSS 加速统计 | `/sys/kernel/debug/ecm/ecm_db/` |
| 运行时长 | `/proc/uptime` |

## 截图

![状态监控页面](status.png)

## 许可证

MIT License
