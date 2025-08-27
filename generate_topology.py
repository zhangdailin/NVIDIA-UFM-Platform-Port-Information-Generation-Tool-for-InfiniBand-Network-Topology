import csv
import re
import json
import argparse
import glob
import os
from pathlib import Path
from collections import defaultdict

# 参数配置
parser = argparse.ArgumentParser(description='根据 UFM 端口信息生成 CLOS 拓扑 HTML')
parser.add_argument('--csv', dest='csv', default=None, help='指定端口 CSV 路径')
parser.add_argument('--csv-glob', dest='csv_glob', default='Ports-*.csv', help='CSV 文件匹配模式，未指定 --csv 时选取最新的一个')
parser.add_argument('--output', dest='output', default='topology.html', help='输出 HTML 文件名')
parser.add_argument('--layer-gap', dest='layer_gap', type=int, default=900, help='三层之间的垂直间距')
parser.add_argument('--node-gap', dest='node_gap', type=int, default=200, help='Core 同层节点间距')
parser.add_argument('--spine-gap', dest='spine_gap', type=int, default=350, help='Spine 同层节点间距')
parser.add_argument('--leaf-gap', dest='leaf_gap', type=int, default=350, help='Leaf 同层节点间距')
parser.add_argument('--label-width', dest='label_width', type=int, default=150, help='节点标签最大宽度（px）')
parser.add_argument('--pod-spacing', dest='pod_spacing', type=int, default=None, help='ALL 视图中各 POD 的水平间距；未指定时自动计算')
parser.add_argument('--pod-margin', dest='pod_margin', type=int, default=200, help='自动计算 POD 间距时的额外边距')
parser.add_argument('--max-chains', dest='max_chains', type=int, default=15, help='链路详细信息条数上限')
parser.add_argument('--debug', dest='debug', action='store_true', help='启用调试输出')
parser.add_argument('--debug-target-leaf', dest='debug_target_leaf', default='', help='调试：仅在 --debug 时输出该 Leaf 的链路情况')
args = parser.parse_args()

def pick_latest_csv(pattern: str):
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p))
    return files[-1]

csv_path = args.csv or pick_latest_csv(args.csv_glob) or 'Ports-20250731.csv'
if args.debug:
    print(f'使用的CSV: {csv_path}')


def get_device_layer(device_name):
    if 'IBCR' in device_name:
        return 'core'
    elif 'IBSP' in device_name:
        return 'spine'
    elif 'IBLF' in device_name:
        return 'leaf'
    else:
        return 'unknown'


# 1. 构建完整的端口映射
port_map = {}  # (System, Port) -> (Peer Node, Peer Port)
with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',')
    if reader.fieldnames[0].startswith('\ufeff'):
        reader.fieldnames[0] = reader.fieldnames[0].replace('\ufeff', '')
    for row in reader:
        sys = row['System'].strip()
        port = row['Port'].strip()
        peer = row['Peer Node'].strip()
        peer_port = row['Peer Port'].strip()
        port_map[(sys, port)] = (peer, peer_port)

# 2. 追溯三台设备链路关系
three_device_chains = []
core_devices = set()
spine_devices = set()
leaf_devices = set()
edges = set()
device_count = defaultdict(int)
unique_edges = set()
nodes = {}
# 先正常追溯三设备链路
for (sys, port), (peer, peer_port) in port_map.items():
    key_b = (peer, peer_port)
    if key_b in port_map:
        peer2, peer2_port = port_map[key_b]
        if any(role in sys for role in ['IBCR', 'IBSP', 'IBLF']) or \
           any(role in peer for role in ['IBCR', 'IBSP', 'IBLF']) or \
           any(role in peer2 for role in ['IBCR', 'IBSP', 'IBLF']):
            chain = {
                'device_a': sys,
                'device_b': peer,
                'device_c': peer2,
                'port_a': port,
                'port_b': peer_port,
                'port_c': peer2_port,
                'layer_a': get_device_layer(sys),
                'layer_b': get_device_layer(peer),
                'layer_c': get_device_layer(peer2)
            }
            three_device_chains.append(chain)
            device_count[sys] += 1
            device_count[peer] += 1
            device_count[peer2] += 1
            n1 = sys
            n2 = peer
            n3 = peer2
        nodes[n1] = sys
        nodes[n2] = peer
        nodes[n3] = peer2
# 只按设备名的边
edge1 = tuple(sorted([n1, n2]))
edge2 = tuple(sorted([n2, n3]))
if edge1 not in unique_edges:
    edges.add((n1, None, n2, None))
    unique_edges.add(edge1)
if edge2 not in unique_edges:
    edges.add((n2, None, n3, None))
    unique_edges.add(edge2)
# 补充所有 leaf-spine 直连边（每一条链路都保留端口信息，正反向只保留一条）
for (sys, port), (peer, peer_port) in port_map.items():
    if (('IBLF' in sys and 'IBSP' in peer) or (
        'IBSP' in sys and 'IBLF' in peer)):
        edge_key = tuple(sorted([(sys, port), (peer, peer_port)]))
        if edge_key not in unique_edges:
            edges.add((sys, port, peer, peer_port))
            unique_edges.add(edge_key)

# 统计三层设备
for dev in nodes:
    layer = get_device_layer(dev)
    if layer == 'core':
        core_devices.add(dev)
    elif layer == 'spine':
        spine_devices.add(dev)
    elif layer == 'leaf':
        leaf_devices.add(dev)

core_list = sorted(list(core_devices))
spine_list = sorted(list(spine_devices))
leaf_list = sorted(list(leaf_devices))
layer_gap = args.layer_gap
node_gap = args.node_gap
spine_node_gap = args.spine_gap
leaf_node_gap = args.leaf_gap
pod_spacing = args.pod_spacing  # 若为 None，后续自动计算
max_count = max(len(core_list), len(spine_list), len(leaf_list))
center_x = (max_count - 1) * node_gap / 2

# 统计所有POD
pod_names = set()
pod_color_map = {}
pod_colors = [
    "#f1c40f33",
    "#a2d5f2cc",
    "#b8e994cc",
    "#f7cac9cc",
    "#f9e79fcc",
    "#d2b4fccc",
     "#f5cba7cc"]
for dev in list(spine_list) + list(leaf_list):
    m = re.search(r'POD(\d+)', dev)
    if m:
        pod_names.add(m.group(0))
pod_names = sorted(list(pod_names))
pod_names = ["ALL"] + pod_names
for idx, pod in enumerate(pod_names):
    pod_color_map[pod] = pod_colors[idx % len(pod_colors)]
pods_only = [p for p in pod_names if p != "ALL"]

# 预计算各 POD 父容器宽度，并据此确定 ALL 视图的水平间距
pod_container_width_map = {}
for pod in pods_only:
    pod_spine_devices_tmp = [dev for dev in spine_list if pod in dev]
    pod_leaf_devices_tmp = [dev for dev in leaf_list if pod in dev]
    max_span_spine_tmp = (len(pod_spine_devices_tmp) - 1) * spine_node_gap if len(pod_spine_devices_tmp) > 0 else 0
    max_span_leaf_tmp = (len(pod_leaf_devices_tmp) - 1) * leaf_node_gap if len(pod_leaf_devices_tmp) > 0 else 0
    container_width_tmp = max(max_span_spine_tmp, max_span_leaf_tmp, 300) + 300
    pod_container_width_map[pod] = container_width_tmp
pod_spacing_effective = pod_spacing if pod_spacing is not None else (max(pod_container_width_map.values() or [900]) + args.pod_margin)

# 记录设备与端口的映射
device_port_map = defaultdict(set)
for (sys, port), (peer, peer_port) in port_map.items():
    device_port_map[sys].add(port)
    device_port_map[peer].add(peer_port)

# 生成每个POD的节点和边（只包含该POD的父节点、spine/leaf节点，以及core与该POD的spine/leaf之间的边）
pod_node_map = {}
pod_edge_map = {}
core_node_objs = []
for idx, dev in enumerate(core_list):
    x = idx * node_gap - (len(core_list) - 1) * node_gap / 2 + center_x
    core_node_objs.append({
        "data": {"id": dev, "label": dev, "layer": "core"},
        "position": {"x": x, "y": 0},
        "style": {"background-color": "#e74c3c", "width": "50px", "height": "50px"}
    })
# ALL POD 节点和边合集（仅收集非 Core 节点，Core 单独维护）
all_nodes = []
all_edges = []
# 不在pod_edge_map中补充IBCR<->IBSP的边
# 但生成ibcr_ibsp_edges_map[pod][spine]，用于前端点击spine节点时动态添加
ibcr_ibsp_edges_map = {pod: {} for pod in pod_names}
for pod in pod_names:
    if pod == "ALL":
        continue
    pod_node_map[pod] = []
    pod_edge_map[pod] = []
    # 计算该 POD 的水平偏移
    pod_idx = pods_only.index(pod) if pod in pods_only else 0
    pod_offset_x = (pod_idx - (len(pods_only) - 1) / 2) * pod_spacing_effective
    # 该 POD 内 spines 与 leafs 列表
    pod_spine_devices = [dev for dev in spine_list if pod in dev]
    pod_leaf_devices = [dev for dev in leaf_list if pod in dev]
    # 计算父容器宽度以适配子节点
    max_span_spine = (len(pod_spine_devices) - 1) * spine_node_gap if len(pod_spine_devices) > 0 else 0
    max_span_leaf = (len(pod_leaf_devices) - 1) * leaf_node_gap if len(pod_leaf_devices) > 0 else 0
    container_width = max(max_span_spine, max_span_leaf, 300) + 300
    # pod_spacing_effective 已预先计算，无需在此处更新
    # 父节点
    pod_node_map[pod].append({
        "data": {"id": pod, "label": pod},
        "position": {"x": pod_offset_x, "y": layer_gap * 1.5},
        "grabbable": False, "selectable": False,
        "style": {"background-color": pod_color_map[pod], "shape": "roundrectangle", "width": container_width, "height": 350, "label": pod, "font-size": "20px", "text-valign": "top", "text-halign": "center", "z-index": 0}
    })
    # IBSP
    pod_spine = []
    for j, dev in enumerate(pod_spine_devices):
        x = pod_offset_x + (j - (len(pod_spine_devices) - 1) / 2) * spine_node_gap
        pod_spine.append(dev)
        pod_node_map[pod].append({
            "data": {"id": dev, "label": dev, "layer": "spine", "parent": pod},
            "position": {"x": x, "y": layer_gap},
            "style": {"background-color": "#3498db", "width": "45px", "height": "45px"}
        })
    # IBLF
    pod_leaf = []
    for j, dev in enumerate(pod_leaf_devices):
        x = pod_offset_x + (j - (len(pod_leaf_devices) - 1) / 2) * leaf_node_gap
        pod_leaf.append(dev)
        pod_node_map[pod].append({
            "data": {"id": dev, "label": dev, "layer": "leaf", "parent": pod},
            "position": {"x": x, "y": layer_gap * 2},
            "style": {"background-color": "#27ae60", "width": "40px", "height": "40px"}
        })
    # 边：只保留core与该POD的spine/leaf之间的边，以及该POD内部的边（不补充IBCR<->IBSP）
    for edge in edges:
        if len(edge) == 4:
            src, src_port, dst, dst_port = edge
        else:
            src, src_port, dst, dst_port = edge[0], None, edge[2], None
        # 跳过没有端口信息的边
        if src_port is None or dst_port is None:
            continue
        # 只保留本POD相关的边
        if (
            (src in core_list and dst in pod_leaf) or
            (dst in core_list and src in pod_leaf) or
            (src in pod_spine + pod_leaf and dst in pod_spine + pod_leaf)
        ):
            edge_id = f"{src}:{src_port}->{dst}:{dst_port}"
            src_ports = [src_port] if src_port else list(
    device_port_map[src]) if src in device_port_map else []
            dst_ports = [dst_port] if dst_port else list(
    device_port_map[dst]) if dst in device_port_map else []
            pod_edge_map[pod].append({
                "data": {
                    "id": edge_id,
                    "source": src,
                    "target": dst,
                    "src_ports": src_ports,
                    "dst_ports": dst_ports
                }
            })
    # pod 内独立去重
    ibcr_ibsp_edge_set = set()
    for (sys, port), (peer, peer_port) in port_map.items():
        if ('IBCR' in sys and 'IBSP' in peer) or (
            'IBSP' in sys and 'IBCR' in peer):
            if (pod in sys) or (pod in peer):
                # 确定spine和core，强制core为source，spine为target
                if 'IBSP' in sys:
                    spine, core = sys, peer
                    spine_port, core_port = port, peer_port
                else:
                    spine, core = peer, sys
                    spine_port, core_port = peer_port, port
                edge_key = tuple(sorted([(core, core_port), (spine, spine_port)]))
                if edge_key in ibcr_ibsp_edge_set:
                    continue
                ibcr_ibsp_edge_set.add(edge_key)
                if spine not in ibcr_ibsp_edges_map[pod]:
                    ibcr_ibsp_edges_map[pod][spine] = []
                ibcr_ibsp_edges_map[pod][spine].append({
                    "data": {
                        "id": f"{core}:{core_port}->{spine}:{spine_port}",
                        "source": core,
                        "target": spine,
                        "src_ports": [core_port],
                        "dst_ports": [spine_port]
                    }
                })

# 计算所有 spine/leaf 的水平范围，并让 Core 居中于其上方
child_xs = []
for pod in pods_only:
    for node in pod_node_map.get(pod, []):
        if node.get("data", {}).get("layer") in ("spine", "leaf"):
            child_xs.append(node.get("position", {}).get("x", 0))
if child_xs:
    mid_x = (min(child_xs) + max(child_xs)) / 2
else:
    mid_x = 0
# 重新计算 Core 的 X 坐标，使其整体居中
core_node_objs = []
for idx, dev in enumerate(core_list):
    x = mid_x + (idx - (len(core_list) - 1) / 2) * node_gap
    core_node_objs.append({
        "data": {"id": dev, "label": dev, "layer": "core"},
        "position": {"x": x, "y": 0},
        "style": {"background-color": "#e74c3c", "width": "50px", "height": "50px"}
    })

all_nodes += [node for pod_nodes in pod_node_map.values() for node in pod_nodes]
all_edges += [edge for pod_edges in pod_edge_map.values() for edge in pod_edges]

# 生成ALL合集（不包含 Core，Core 由前端单独添加）
pod_node_map["ALL"] = all_nodes
pod_edge_map["ALL"] = all_edges
# 生成 ibcr_ibsp_edges_map["ALL"]，合并所有POD的core-spine边
ibcr_ibsp_edges_map["ALL"] = {}
for pod in pod_names:
    if pod == "ALL":
        continue
    for spine, edges_list in ibcr_ibsp_edges_map[pod].items():
        if spine not in ibcr_ibsp_edges_map["ALL"]:
            ibcr_ibsp_edges_map["ALL"][spine] = []
        ibcr_ibsp_edges_map["ALL"][spine].extend(edges_list)

def safe_json_for_html(js):
    return js.replace('</script>', '<\\/script>')

core_node_objs_js = safe_json_for_html(json.dumps(core_node_objs, ensure_ascii=False))
pod_nodes_js = safe_json_for_html(json.dumps(pod_node_map, ensure_ascii=False))
pod_edges_js = safe_json_for_html(json.dumps(pod_edge_map, ensure_ascii=False))
pod_list_js = safe_json_for_html(json.dumps(pod_names, ensure_ascii=False))
ibcr_ibsp_edges_map_js = safe_json_for_html(json.dumps(ibcr_ibsp_edges_map, ensure_ascii=False))
label_width_js = args.label_width

pod_select_html = '''
<div style="position:absolute;top:10px;left:400px;z-index:3000;background:rgba(255,255,255,0.95);padding:6px 12px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,0.08);">
  <label for="pod-select" style="font-size:16px;margin-right:8px;">选择POD:</label>
  <select id="pod-select" style="font-size:16px;">
    {options}
  </select>
</div>
'''.replace('{options}', ''.join(
    f'<option value="{pod}"{" selected" if pod=="ALL" else ""}>{pod}</option>' for pod in pod_names
))

# 生成三台设备链路的详细信息
chain_info = []
for i, chain in enumerate(three_device_chains[:15]):
    chain_info.append(f"链路{i+1}: {chain['device_a']}({chain['layer_a']}) → {chain['device_b']}({chain['layer_b']}) → {chain['device_c']}({chain['layer_c']})")

# 调试：输出指定leaf的所有链路和edges中的所有相关边
# 可根据需要修改target_leaf
# 统计三层设备前

if args.debug and args.debug_target_leaf:
    target_leaf = args.debug_target_leaf
    leaf_links = [((sys, port), (peer, peer_port)) for (sys, port), (peer, peer_port) in port_map.items() if sys == target_leaf or peer == target_leaf]
    print(f'{target_leaf} 相关链路总数: {len(leaf_links)}')
    for link in leaf_links:
        print(link)
    leaf_edges = [e for e in edges if target_leaf in e]
    print(f'edges中 {target_leaf} 相关边数: {len(leaf_edges)}')
    for e in leaf_edges:
        print(e)

# 生成alert JS代码时，全部用\n换行，避免非法换行
html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>CLOS三层架构拓扑图</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://unpkg.com/cytoscape@3.26.0/dist/cytoscape.min.js"></script>
  <style>
    #cy {{
      width: 100vw;
      height: 100vh;
      min-width: 0;
      min-height: 0;
      box-sizing: border-box;
      display: block;
      background-color: #f8f9fa;
      overflow: auto;
    }}
    .info {{
      position: absolute; top: 10px; left: 10px; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 14px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); z-index: 1000; max-width: 350px;
    }}
    .legend {{
      position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    .legend-item {{ display: flex; align-items: center; margin: 8px 0; }}
    .legend-color {{ width: 25px; height: 25px; border-radius: 50%; margin-right: 10px; }}
    .chains {{
      position: absolute; bottom: 10px; left: 10px; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 11px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-height: 200px; overflow-y: auto; max-width: 500px;
    }}
    .debug {{ position: absolute; bottom: 10px; right: 10px; background: rgba(255,255,255,0.95); padding: 15px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    /* info-panel 样式自适应 */
    #info-panel {{
      display: none;
      position: fixed;
      top: 0; right: 0;
      height: 100vh;
      max-width: 90vw;
      width: min(350px, 90vw);
      background: #fff;
      box-shadow: -2px 0 10px rgba(0,0,0,0.1);
      z-index: 9999;
      padding: 24px;
      overflow-y: auto;
      overflow-x: auto;
      box-sizing: border-box;
    }}
    #info-panel-content {{
      word-break: break-all;
    }}
  </style>
</head>
<body>
  {pod_select_html}
  <div class="info">
    <strong>CLOS三层架构拓扑图</strong><br>
    Core层(IBCR): {len(core_list)} 个<br>
    Spine层(IBSP): {len(spine_list)} 个<br>
    Leaf层(IBLF): {len(leaf_list)} 个
  </div>
  <div class="legend">
    <strong>CLOS三层架构</strong><br>
    <div class="legend-item"><div class="legend-color" style="background-color: #e74c3c;"></div><span>Core层 (IBCR)</span></div>
    <div class="legend-item"><div class="legend-color" style="background-color: #3498db;"></div><span>Spine层 (IBSP)</span></div>
    <div class="legend-item"><div class="legend-color" style="background-color: #27ae60;"></div><span>Leaf层 (IBLF)</span></div>
  </div>
  <div class="debug">
    <strong>调试信息</strong><br>
    <div id="debug-info">正在加载...</div>
  </div>
  <div id="cy"></div>
  <!-- 信息浮层子页面 -->
  <div id="info-panel" style="display:none;position:fixed;top:0;right:0;height:100vh;width:350px;background:#fff;box-shadow:-2px 0 10px rgba(0,0,0,0.1);z-index:9999;padding:24px;overflow-y:auto;">
    <div id="info-panel-content"></div>
    <button onclick="document.getElementById('info-panel').style.display='none'" style="position:absolute;top:8px;right:8px;">关闭</button>
  </div>
  <!-- 安全传递大JSON数据 -->
  <script type="application/json" id="core-nodes-data">{core_node_objs_js}</script>
  <script type="application/json" id="pod-nodes-data">{pod_nodes_js}</script>
  <script type="application/json" id="pod-edges-data">{pod_edges_js}</script>
  <script type="application/json" id="pod-list-data">{pod_list_js}</script>
  <script type="application/json" id="ibcr-ibsp-edges-map-data">{ibcr_ibsp_edges_map_js}</script>
  <script>
    // 安全获取大JSON数据
    const coreNodes = JSON.parse(document.getElementById('core-nodes-data').textContent);
    const podNodes = JSON.parse(document.getElementById('pod-nodes-data').textContent);
    const podEdges = JSON.parse(document.getElementById('pod-edges-data').textContent);
    const podList = JSON.parse(document.getElementById('pod-list-data').textContent);
    const ibcrIbspEdgesMap = JSON.parse(document.getElementById('ibcr-ibsp-edges-map-data').textContent);
    let currentPod = null;
    let ibcrIbspEdgesAdded = [];
    // 初始只显示Core
    let cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: coreNodes,
      style: [
        {{
          selector: 'node',
          style: {{
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#222',
            'font-size': '11px',
            'text-wrap': 'wrap',
            'text-max-width': '150px',
            'border-width': 2,
            'border-color': '#fff',
            'font-weight': 'bold'
          }}
        }},
        {{
          selector: 'edge',
          style: {{
            'width': 2,
            'line-color': '#666',
            'target-arrow-color': '#666',
            'target-arrow-shape': 'triangle',
            'target-arrow-width': 4,
            'curve-style': 'bezier'
          }}
        }}
      ],
      layout: {{
        name: 'preset',
        fit: true,
        padding: 50
      }},
      minZoom: 0.1,
      maxZoom: 2,
      wheelSensitivity: 0.2,
      motionBlur: true,
      boxSelectionEnabled: false,
      autoungrabify: false,
    }});
    document.getElementById('pod-select').onchange = function() {{
      let pod = this.value;
      currentPod = pod;
      let nodes, edges;
      if (pod && podNodes[pod]) {{
        nodes = coreNodes.concat(podNodes[pod]);
        edges = podEdges[pod];
      }} else {{
        nodes = coreNodes;
        edges = [];
      }}
      cy.elements().remove();
      cy.add(nodes.concat(edges));
      cy.layout({{name: 'preset', fit: true, padding: 50}}).run();
      // 移除所有IBCR<->IBSP边
      ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
      ibcrIbspEdgesAdded = [];
    }};
    function showInfoPanel(html) {{
      document.getElementById('info-panel-content').innerHTML = html;
      document.getElementById('info-panel').style.display = 'block';
    }}
    cy.on('tap', 'edge', function(evt) {{
      var edge = evt.target;
      var src = edge.data('source');
      var dst = edge.data('target');
      var src_ports = edge.data('src_ports') || [];
      var dst_ports = edge.data('dst_ports') || [];
      showInfoPanel(
        '<b>链路信息</b><br>' +
        '源设备: ' + src + '<br>' +
        '目标设备: ' + dst + '<br>' +
        '源端口: ' + src_ports.join(', ') + '<br>' +
        '目标端口: ' + dst_ports.join(', ')
      );
    }});
    cy.on('tap', 'node', function(evt) {{
      var node = evt.target;
      var edges = node.connectedEdges();
      var html = '<b>设备: ' + node.id() + '</b><br>连接数量: ' + edges.length + '<br>';
      edges.forEach(function(edge) {{
        var peer = (edge.data('source') === node.id()) ? edge.data('target') : edge.data('source');
        var src_ports = edge.data('src_ports') || [];
        var dst_ports = edge.data('dst_ports') || [];
        html += '对端: ' + peer + ' | 源端口: ' + src_ports.join(', ') + ' | 目标端口: ' + dst_ports.join(', ') + '<br>';
      }});
      showInfoPanel(html);
      if(node.data('layer') === 'core' && currentPod && ibcrIbspEdgesMap[currentPod]) {{
        ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
        ibcrIbspEdgesAdded = [];
        let connectedSpineEdges = [];
        for (let spine in ibcrIbspEdgesMap[currentPod]) {{
          ibcrIbspEdgesMap[currentPod][spine].forEach(function(edge) {{
            if (edge.data.source === node.id() || edge.data.target === node.id()) {{
              connectedSpineEdges.push(edge);
            }}
          }});
        }}
        connectedSpineEdges.forEach(function(edge) {{
          let ele = cy.add(edge);
          ibcrIbspEdgesAdded.push(ele);
        }});
      }}
      if(node.data('layer') === 'spine' && currentPod && ibcrIbspEdgesMap[currentPod] && ibcrIbspEdgesMap[currentPod][node.id()]) {{
        ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
        ibcrIbspEdgesAdded = [];
        ibcrIbspEdgesMap[currentPod][node.id()].forEach(function(edge) {{
          let ele = cy.add(edge);
          ibcrIbspEdgesAdded.push(ele);
        }});
      }}
    }});
    cy.on('tap', function(evt) {{
      if(evt.target === cy) {{
        document.getElementById('info-panel').style.display = 'none';
        ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
        ibcrIbspEdgesAdded = [];
      }}
    }});
    document.getElementById('debug-info').innerHTML = '初始化成功<br>节点数: ' + cy.nodes().length + '<br>边数: ' + cy.edges().length;
  </script>
  <!--
  <script>
    // 安全获取大JSON数据
    const coreNodes = JSON.parse(document.getElementById('core-nodes-data').textContent);
    const podNodes = JSON.parse(document.getElementById('pod-nodes-data').textContent);
    const podEdges = JSON.parse(document.getElementById('pod-edges-data').textContent);
    const podList = JSON.parse(document.getElementById('pod-list-data').textContent);
    const ibcrIbspEdgesMap = JSON.parse(document.getElementById('ibcr-ibsp-edges-map-data').textContent);
    let currentPod = null;
    let ibcrIbspEdgesAdded = [];
    // 初始只显示Core
    let cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: coreNodes,
      style: [
        {{
          selector: 'node',
          style: {{
            'label': 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'color': '#222',
            'font-size': '11px',
            'text-wrap': 'wrap',
            'text-max-width': '" + String(label_width_js) + "px',
            'border-width': 2,
            'border-color': '#fff',
            'font-weight': 'bold'
          }}
        }},
        {{
          selector: 'edge',
          style: {{
            'width': 2,
            'line-color': '#666',
            'target-arrow-color': '#666',
            'target-arrow-shape': 'triangle',
            'target-arrow-width': 4,
            'curve-style': 'bezier'
          }}
        }}
      ],
      layout: {{
        name: 'preset',
        fit: true,
        padding: 50
      }},
      minZoom: 0.1,
      maxZoom: 2,
      wheelSensitivity: 0.2,
      motionBlur: true,
      boxSelectionEnabled: false,
      autoungrabify: false,
    }});
    document.getElementById('pod-select').onchange = function() {{
      let pod = this.value;
      currentPod = pod;
      let nodes, edges;
      if (pod && podNodes[pod]) {{
        nodes = coreNodes.concat(podNodes[pod]);
        edges = podEdges[pod];
      }} else {{
        nodes = coreNodes;
        edges = [];
      }}
      cy.elements().remove();
      cy.add(nodes.concat(edges));
      cy.layout({{name: 'preset', fit: true, padding: 50}}).run();
      // 移除所有IBCR<->IBSP边
      ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
      ibcrIbspEdgesAdded = [];
    }};
    // 点击边显示端口号
    cy.on('tap', 'edge', function(evt) {{
      var edge = evt.target;
      var src = edge.data('source');
      var dst = edge.data('target');
      var src_ports = edge.data('src_ports') || [];
      var dst_ports = edge.data('dst_ports') || [];
      alert(
        '链路: ' + src + ' → ' + dst + '\\n' +
        '源端口: ' + src_ports.join(', ') + '\\n' +
        '目标端口: ' + dst_ports.join(', ')
      );
    }});
    // 点击spine节点时动态添加IBCR<->IBSP边
    cy.on('tap', 'node', function(evt) {{
      var node = evt.target;
      var degree = node.connectedEdges().length;
      alert(
        '设备: ' + node.id() + '\\n' +
        '连线数量: ' + degree
      );
      if(node.data('layer') === 'spine' && currentPod && ibcrIbspEdgesMap[currentPod] && ibcrIbspEdgesMap[currentPod][node.id()]) {{
        // 先移除之前的IBCR<->IBSP边
        ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
        ibcrIbspEdgesAdded = [];
        // 添加当前spine的IBCR<->IBSP边
        ibcrIbspEdgesMap[currentPod][node.id()].forEach(function(edge) {{
          let ele = cy.add(edge);
          ibcrIbspEdgesAdded.push(ele);
        }});
      }}
    }});
    // 点击空白处移除IBCR<->IBSP边
    cy.on('tap', function(evt) {{
      if(evt.target === cy) {{
        ibcrIbspEdgesAdded.forEach(eid => {{ try{{cy.remove(eid);}}catch(e){{}} }});
        ibcrIbspEdgesAdded = [];
      }}
    }});
    document.getElementById('debug-info').innerHTML = '初始化成功<br>节点数: ' + cy.nodes().length + '<br>边数: ' + cy.edges().length;
    // 页面加载后自动触发一次POD切换事件
    document.getElementById('pod-select').dispatchEvent(new Event('change'));
  </script>
  -->
</body>
</html>
"""

with open(args.output, 'w', encoding='utf-8') as f:
    f.write(html)
if args.debug:
    print(f'已生成: {args.output}')