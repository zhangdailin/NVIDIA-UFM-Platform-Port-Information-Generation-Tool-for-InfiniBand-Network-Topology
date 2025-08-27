## 项目简介

使用 UFM 导出的端口信息 CSV，自动生成 CLOS 三层（Core/Spine/Leaf）拓扑的交互式网页（Cytoscape）。支持自动发现最新 CSV、POD 分组展示、点击节点/边查看信息、POD 视图切换，以及可配置的布局参数。

## 环境要求

- 已安装 Python 3.8+（系统自带或 Anaconda 皆可）
- 无需额外第三方库（前端通过 CDN 加载 Cytoscape）

## CSV 数据要求

脚本读取 UFM 端口导出 CSV，需包含以下列（区分大小写）：
- `System`
- `Port`
- `Peer Node`
- `Peer Port`

脚本会自动处理 BOM 头（如果有）。文件名不限，默认会在当前目录下按通配符 `Ports-*.csv` 自动选择“修改时间最新”的一个。

## 快速开始

Windows PowerShell（当前项目根目录）：
```powershell
python .\generate_topology.py
```

或指定 CSV 和输出文件：
```powershell
python .\generate_topology.py --csv .\Ports-20250731.csv --output .\topology.html
```

执行完成后，打开生成的 `topology.html` 即可查看拓扑。

## 常用参数

```text
--csv <path>                指定端口 CSV 文件路径；未指定时自动匹配最新 Ports-*.csv
--csv-glob <pattern>        自动匹配模式，默认 Ports-*.csv
--output <file>             输出 HTML 文件名，默认 topology.html

--layer-gap <int>           三层（Core/Spine/Leaf）之间的垂直间距，默认 900
--node-gap <int>            Core 同层节点间距，默认 200
--spine-gap <int>           Spine 同层节点间距，默认 350
--leaf-gap <int>            Leaf 同层节点间距，默认 350
--label-width <int>         节点标签最大宽度（px），默认 150（长设备名更易读）

--pod-spacing <int>         ALL 视图中各 POD 的固定水平间距；
                            不指定时会“自动计算”（基于 POD 内容宽度 + pod-margin）
--pod-margin <int>          自动计算 POD 间距时的额外边距，默认 200

--max-chains <int>          页面底部示例链路条数上限，默认 15
--debug                     打印调试信息
--debug-target-leaf <name>  仅在 --debug 时，打印指定 Leaf 的链路详情
```

示例：
```powershell
# 使用最新 CSV + 默认参数
python .\generate_topology.py

# 指定 CSV、输出到 out.html、加宽标签
python .\generate_topology.py --csv .\Ports-20250731.csv --output .\out.html --label-width 180

# 手动加大 POD 间距（优先级高于自动计算）
python .\generate_topology.py --pod-spacing 1800

# 使用自动间距，但加大外边距
python .\generate_topology.py --pod-margin 300

# 打印调试信息并聚焦某个 Leaf 的链路
python .\generate_topology.py --debug --debug-target-leaf MDC-...-POD2-...-IBLF-008
```

## 网页交互说明

- 页面左上角下拉框：切换 `ALL` 或各个 `POD` 视图
- 点击节点（Core/Spine/Leaf）：
  - 显示该设备的连线统计和对端端口列表（右侧信息面板）
  - 点击 Core 或 Spine 节点时，会动态叠加 Core-Spine 的连线，便于排查（再次点击空白处可清除）
- 点击边：显示源/目标端口号（右侧信息面板）

## 布局与视觉

- POD 水平位置：
  - 默认按内容宽度自动计算统一的 `POD` 间距，避免重叠
  - 如仍感觉拥挤，可用 `--pod-margin` 增加外边距，或直接指定 `--pod-spacing`
- Core 居中：自动计算所有 `Spine/Leaf` 的水平范围，将 `Core` 层整体居中显示
- 节点标签：可通过 `--label-width` 增加标签宽度以完整显示设备名

## 常见问题（FAQ）

1. POD 之间仍有重叠？
   - 先尝试提高 `--pod-margin`，例如 300 或 400
   - 或直接指定较大的 `--pod-spacing`（如 1800），覆盖自动计算

2. Core 没有居中在 Spine/Leaf 上？
   - 重新生成时确保已包含全部 POD 的节点（默认是有的）
   - 若你只展示少量 POD，可直接改小或改大 `--node-gap` 让 Core 排布更紧凑/更分散

3. 设备名太长看不清？
   - 使用 `--label-width 180` 或更大数值

4. 我想以机架/序号对齐排序？
   - 目前默认以设备名排序并在 POD 内居中。如果你有明确排序规则（如解析 Gxx/Uxx），请告知，我们可以按机架/序号做行列对齐。

## 目录结构（关键文件）

```text
generate_topology.py   # 主脚本：读取 CSV，生成 topology.html
topology.html          # 生成的交互式拓扑网页（运行脚本后得到）
Ports-*.csv            # UFM 导出的端口信息（任意版本，脚本会选最新）
README.md              # 本使用说明
```

## 版权与致谢

- 前端可视化基于 Cytoscape（通过 CDN 动态加载）
- 本脚本仅使用 Python 标准库


