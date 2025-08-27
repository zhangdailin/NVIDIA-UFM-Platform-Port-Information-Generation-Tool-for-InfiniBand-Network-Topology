## Overview

Generate an interactive CLOS (Core/Spine/Leaf) topology web page from UFM-exported port CSV data. The output is a Cytoscape-based HTML that supports POD grouping, interactive inspection (click nodes/edges), and configurable layout.

## Requirements

- Python 3.8+ (system Python or Anaconda)
- No extra Python packages required (Cytoscape is loaded via CDN in the HTML)

## CSV format

The script expects a UFM port CSV with these exact column headers:
- `System`
- `Port`
- `Peer Node`
- `Peer Port`

The script handles BOM automatically if present. File name is flexible; by default the script will pick the most recently modified one matching `Ports-*.csv` in the current directory.

## Quick start

Windows PowerShell (run in the project root):
```powershell
python .\generate_topology.py
```

Specify CSV and output file explicitly:
```powershell
python .\generate_topology.py --csv .\Ports-20250731.csv --output .\topology.html
```

Open the generated `topology.html` in a browser to view the topology.

## CLI options

```text
--csv <path>                Path to the UFM ports CSV. If not set, the newest
                            file matching --csv-glob is used.
--csv-glob <pattern>        Glob for auto-picking CSV (default: Ports-*.csv)
--output <file>             Output HTML file name (default: topology.html)

--layer-gap <int>           Vertical gap between Core/Spine/Leaf layers (default: 900)
--node-gap <int>            Horizontal gap between Core nodes (default: 200)
--spine-gap <int>           Horizontal gap between Spine nodes (default: 350)
--leaf-gap <int>            Horizontal gap between Leaf nodes (default: 350)
--label-width <int>         Max label width in px (default: 150)

--pod-spacing <int>         Fixed horizontal spacing between PODs in ALL view;
                            if omitted, spacing is auto-calculated from content width
                            plus --pod-margin.
--pod-margin <int>          Extra margin used by auto POD spacing (default: 200)

--max-chains <int>          Max number of sample chain lines shown (default: 15)
--debug                     Print debug logs
--debug-target-leaf <name>  With --debug, print link details for a specific Leaf
```

Examples:
```powershell
# Use newest CSV with defaults
python .\generate_topology.py

# Explicit CSV, custom output, wider labels
python .\generate_topology.py --csv .\Ports-20250731.csv --output .\out.html --label-width 180

# Force large fixed POD spacing (overrides auto spacing)
python .\generate_topology.py --pod-spacing 1800

# Keep auto spacing but increase outer margin
python .\generate_topology.py --pod-margin 300

# Debug, focusing on a specific Leaf
python .\generate_topology.py --debug --debug-target-leaf MDC-...-POD2-...-IBLF-008
```

## Web UI interactions

- POD selector (top-left): switch between `ALL` and specific PODs
- Click a node (Core/Spine/Leaf):
  - Shows number of connections and peer ports in the right info panel
  - Clicking Core or Spine also overlays Core–Spine links for easier tracing
    (click empty canvas to clear overlays)
- Click an edge: shows source/target ports in the right info panel

## Layout and visuals

- POD placement:
  - By default, POD spacing is auto-calculated from its content width plus margin
  - If still crowded, increase `--pod-margin` or set a fixed `--pod-spacing`
- Core centering:
  - Core layer is centered above the combined horizontal range of all Spine/Leaf
- Labels:
  - Use `--label-width` to increase node label wrap width for long device names

## Troubleshooting (FAQ)

1) PODs overlap in ALL view
   - Increase `--pod-margin` to 300 or 400
   - Or set a fixed `--pod-spacing` (e.g., 1800) to override auto spacing

2) Core not centered above Spine/Leaf
   - Ensure the view includes the relevant PODs (ALL view does by default)
   - Tweak `--node-gap` to make Core nodes more compact or more spread out

3) Device names are truncated
   - Increase `--label-width` (e.g., 180 or 220)

4) I want rack/sequence-based alignment
   - The current layout centers devices by name ordering within each POD.
     If you have concrete rules (e.g., parse Gxx/Uxx), we can add rack/row alignment.

## Project structure

```text
generate_topology.py   # Main script: read CSV and generate topology.html
topology.html          # Generated interactive topology web (after running script)
Ports-*.csv            # UFM port CSV exports (newest is picked by default)
README.md              # User guide
```