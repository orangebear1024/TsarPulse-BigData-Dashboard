# TsarPulse-BigData-Dashboard

<div align="center">

**数据中心基础设施运行监控大屏系统**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![ECharts](https://img.shields.io/badge/ECharts-5.5-AA344D?logo=apacheecharts&logoColor=white)](https://echarts.apache.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📖 项目简介

基于 **Python 大数据生态 × MySQL 关系型数据库 × Flask 轻量级微服务 × 前端数据大屏** 构建的全栈分布式主机监控系统。系统从 4 张原始 TSAR 时序明细表出发，经过 Pandas 分块清洗 → MySQL 小时级滚动聚合 → Flask RESTful API → ECharts 可视化大屏，完整实现了**数据采集、清洗、入库、聚合、查询、展示**的全链路闭环。

> ⚡ 20 台主机 · 11 类监控指标 · 79,275 条原始明细 · 1000 个时间桶聚合 · 50 条智能告警

---

## 🚀 核心技术特性

<table>
<tr>
<td width="50%">

### 🧠 大数据高并发清洗
使用 **Pandas `chunksize` 分块读取** 技术，高效加工 4 张原始时序明细数据（`.dat` 制表符分隔文件），通过 SQLAlchemy `to_sql(method='multi')` 批量写入 MySQL，防止内存溢出。单次导入 **79,275 行** 数据仅需数秒。

</td>
<td width="50%">

### ⏱️ 时间戳智能解析
在 SQL 层全自动将**毫秒级 Unix 长整数时间戳**（`1782835200000`）转换为北京时间格式 `YYYY-MM-DD HH:00`，实现 `FROM_UNIXTIME(ts/1000)` → `DATE_FORMAT` 的标准化对齐流水线。

</td>
</tr>
<tr>
<td width="50%">

### 📊 小时级滚动聚合加工
基于原生 SQL 的 **`GROUP BY` + `AVG()` + `MAX()`** 聚合算子，按 `(小时桶, 主机, 指标标签)` 三维度实时计算滚动窗口内的统计值，同时根据 `MAX(value)` 超过阈值（磁盘 ≥99%、CPU ≥94%）自动触发生成告警流水。

</td>
<td width="50%">

### 🔗 实时全栈无缝联动
Flask 暴露高内聚 RESTful API（`/api/metrics` + `?hostid=`），前端通过 `fetch()` 异步动态拉取。点击主机矩阵任意方块 → 携带 `hostid` 参数重新请求 → **所有图表与告警流水秒级动态过滤切换**。按 `ESC` 一键恢复全局视图。

</td>
</tr>
<tr>
<td width="50%">

### 🎨 赛博曜石 · 极光极简风
- **配色方案**：极光绿 `#10B981`（健康）、电光紫 `#6366F1`（平稳）、琥珀橙 `#F59E0B`（警告）、珊瑚红 `#EF4444`（故障）
- **毛玻璃卡片**：`backdrop-filter: blur(20px)` 半透明面板
- **呼吸灯动画**：健康主机 3s 极光绿脉冲，故障主机 2s 珊瑚红脉冲
- **Tailwind 响应式网格**：`grid-cols-1 lg:grid-cols-4` 多端自适应

</td>
<td width="50%">

### ⚙️ 告警智能分级
```
[危险] host019 磁盘利用率 max_value 达到 99.81%    ← 珊瑚红
[警告] host010 磁盘利用率 max_value 达到 99.51%    ← 琥珀橙
[信息] host020 CPU使用率 max_value 达到 94.96%     ← 电光紫
```
三级着色标签 + 垂直无限循环滚动，hover 暂停。

</td>
</tr>
</table>

---

## 🛠️ 项目结构

```
TsarPulse-BigData-Dashboard/
│
├── app.py                       # Flask 后端微服务（API + 静态文件服务）
├── index.html                   # 前端数据大屏（Tailwind CSS + ECharts）
├── import_raw_to_mysql.py       # 数据导入脚本（Pandas chunksize 分块）
├── .gitignore                   # Git 忽略规则
├── README.md                    # 📄 本文件
│
└── data/                        # 原始 TSAR 明细数据
    ├── disk_tsar.dat            #    磁盘 I/O 性能明细（12,000 行）
    ├── pref_tsar.dat            #    主机 CPU/内存/网络 性能明细（67,200 行）
    ├── host_detail.dat          #    主机元数据（20 行）
    ├── mod_detail.dat           #    模块描述元数据（55 行）
    └── hourly_monitor_report.xlsx  # 小时级汇总报告
```

---

## ⚡ 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|----------|
| Python | ≥ 3.10 |
| MySQL | 8.0+ |
| 浏览器 | Chrome / Edge / Firefox 最新版 |

### 1. 克隆项目

```bash
git clone https://github.com/orangebear1024/TsarPulse-BigData-Dashboard.git
cd TsarPulse-BigData-Dashboard
```

### 2. 安装 Python 依赖

```bash
pip install flask pandas sqlalchemy pymysql
```

### 3. 确保 MySQL 已启动

```bash
# Windows
net start MySQL80
# 或 sc query MySQL80
```

默认配置：`localhost:3306` · `root` · `123456`

### 4. 一键导入原始数据

```bash
python import_raw_to_mysql.py
```

输出示例：
```
[OK] Database 'tsar_pulse' ready.
[OK] Tables created/verified.
[>>>] Importing pref_tsar ...   67,200 rows imported.
[>>>] Importing disk_tsar ...   12,000 rows imported.
[>>>] Importing host_detail ...     20 rows imported.
[>>>] Importing mod_detail ...      55 rows imported.
=======================================================
  disk_tsar                12,000 rows
  pref_tsar                67,200 rows
  host_detail                  20 rows
  mod_detail                   55 rows
  ──────────────────────────────
  TOTAL                    79,275 rows
```

### 5. 启动后端服务

```bash
python app.py
```

```
=======================================================
  TsarPulse — Full-Stack Dashboard
  http://localhost:5000
  http://localhost:5000/api/metrics
  http://localhost:5000/api/metrics?hostid=host010
=======================================================
```

### 6. 访问大屏

浏览器打开 **http://localhost:5000**，或双击 `index.html`。

---

## 🔌 API 文档

### `GET /api/metrics`

返回全主机聚合的 KPI、时序数据和告警列表。

### `GET /api/metrics?hostid=host010`

返回指定主机的独立监控数据，用于前端主机矩阵点击联动。

<details>
<summary>📋 响应结构（点击展开）</summary>

```json
{
  "kpi": {
    "totalHosts": 20,
    "activeHosts": 20,
    "avgCpuLoad": 35.08,
    "totalNetThroughput": 10025.8,
    "unackedAlerts": 22
  },
  "hosts": [
    { "hostid": "host001", "hostname": "server-001.hismartlab.cn",
      "status": "healthy", "max_disk_util": 99.22 }
  ],
  "criticalHost": "host019",
  "warningHosts": ["host004", "host012"],
  "tagDistribution": [
    { "tag": "cpu_percent", "label": "CPU使用率", "count": 16800 }
  ],
  "timeSeries": {
    "cpu_percent": [["07-01 00:00", 35.22, 68.84], ...],
    "mem_metric":   [["07-01 00:00", 75572.6, 91864], ...],
    "net_speed_mb": [["07-01 00:00", 563.62, 824.81], ...],
    "disk_latency_ms": [["07-01 00:00", 20.12, 20.12], ...],
    "disk_util_percent": [["07-01 00:00", 85.3, 99.79], ...]
  },
  "alerts": [
    { "time": "2026-08-09 09:45", "host": "host004",
      "tag": "disk_util_percent", "tagLabel": "磁盘利用率",
      "value": 99.79, "severity": "critical" }
  ]
}
```

</details>

---

## 🎯 交互指南

| 操作 | 效果 |
|------|------|
| 点击主机矩阵方块 | 所有图表 + 告警流水切换为该主机独立数据 |
| 再次点击同一方块 | 取消筛选，恢复全局聚合视图 |
| 按 `ESC` 键 | 恢复全局聚合视图 |
| hover 告警滚动区 | 滚动暂停，方便逐条查看 |
| 拖拽浏览器窗口 | 所有 ECharts 图表自动 resize 适配 |

---

## 🏗️ 技术栈

| 层 | 技术 |
|----|------|
| 数据清洗 | Python · Pandas · SQLAlchemy |
| 数据库 | MySQL 8.0 · InnoDB · 复合索引 |
| 后端 | Flask 3.x · RESTful API · CORS |
| 前端 | HTML5 · Tailwind CSS 3 · ECharts 5.5 · Vanilla JS |
| 部署 | GitHub · Git · gh CLI |

---

## 📄 License

MIT © 2026

---

<div align="center">
  <sub>Built with ❤️ for Big Data Course Assignment</sub>
</div>
