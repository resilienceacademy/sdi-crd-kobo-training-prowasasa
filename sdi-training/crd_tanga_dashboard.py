import requests
import geopandas as gpd
import pandas as pd
import json
import webbrowser
import os
from datetime import datetime

CRD = "https://crd.resilienceacademy.ac.tz"
WFS = f"{CRD}/geoserver/ows"

print("=" * 60)
print("  Tanga Urban Planning Dashboard")
print("  Source: Resilience Academy CRD")
print("=" * 60)

# ---------- 1. List Tanga datasets via REST API -----------
print("\nFetching Tanga datasets from CRD API...")
r = requests.get(f"{CRD}/api/v2/resources", params={"filter{regions.name.in}": "Tanga"})
tanga_datasets = r.json()
total_datasets = tanga_datasets['total']
datasets_list = tanga_datasets['resources']
print(f"Tanga datasets found: {total_datasets}")

# ---------- 2. Define layers to load by theme -----------
THEMES = {
    "Institutions & Facilities": {
        "layers": {
            "geonode:institutions": {"color": "#E74C3C", "icon": "school"},
            "geonode:facilities": {"color": "#9B59B6", "icon": "hospital"},
        },
        "description": "Health, education & public institutions"
    },
    "Road Network": {
        "layers": {
            "geonode:main_roads": {"color": "#E67E22", "icon": "road"},
            "geonode:minor_roads": {"color": "#F39C12", "icon": "road"},
            "geonode:local_roads": {"color": "#D4AC6E", "icon": "road"},
        },
        "description": "Main, minor & local road infrastructure"
    },
    "Land Use": {
        "layers": {
            "geonode:existing_landuse": {"color": "#27AE60", "icon": "land"},
        },
        "description": "Current land use zones"
    },
    "Water Infrastructure": {
        "layers": {
            "geonode:waterpipe_network": {"color": "#3498DB", "icon": "water"},
            "geonode:water_treatment": {"color": "#2980B9", "icon": "water"},
            "geonode:storage_tanks": {"color": "#1ABC9C", "icon": "water"},
        },
        "description": "Water supply network, treatment & storage"
    },
    "Environment & Conservation": {
        "layers": {
            "geonode:conservation_area": {"color": "#2ECC71", "icon": "tree"},
            "geonode:rivers": {"color": "#5DADE2", "icon": "water"},
        },
        "description": "Conservation areas & rivers"
    },
    "Administrative Boundaries": {
        "layers": {
            "geonode:tanga_city_boundary": {"color": "#8E44AD", "icon": "boundary"},
            "geonode:wards_boundaries": {"color": "#AF7AC5", "icon": "boundary"},
        },
        "description": "City & ward boundaries"
    },
}

# ---------- 3. Load WFS layers -----------
loaded_layers = {}
layer_stats = []

for theme_name, theme in THEMES.items():
    print(f"\nLoading {theme_name}...")
    for layer_name, style in theme["layers"].items():
        try:
            wfs_url = (
                f"{WFS}?service=WFS&version=2.0.0"
                f"&request=GetFeature&typeName={layer_name}"
                f"&outputFormat=application/json"
            )
            gdf = gpd.read_file(wfs_url)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            loaded_layers[layer_name] = {
                "gdf": gdf,
                "theme": theme_name,
                "color": style["color"],
                "count": len(gdf),
            }
            geom_type = str(gdf.geom_type.unique()[0]) if len(gdf) > 0 else "N/A"
            layer_stats.append({
                "theme": theme_name,
                "layer": layer_name.replace("geonode:", ""),
                "features": len(gdf),
                "geom_type": geom_type,
            })
            print(f"  ✓ {layer_name}: {len(gdf)} features ({geom_type})")
        except Exception as e:
            print(f"  ✗ {layer_name}: Failed - {e}")

# ---------- 4. Prepare data for HTML -----------
# Calculate center from all loaded point/polygon data
all_centroids_x, all_centroids_y = [], []
for info in loaded_layers.values():
    gdf = info["gdf"]
    if len(gdf) > 0:
        all_centroids_x.append(gdf.geometry.centroid.x.mean())
        all_centroids_y.append(gdf.geometry.centroid.y.mean())

center_lat = sum(all_centroids_y) / len(all_centroids_y) if all_centroids_y else -5.07
center_lon = sum(all_centroids_x) / len(all_centroids_x) if all_centroids_x else 39.10

# Build GeoJSON per layer for the map
geojson_layers = {}
for layer_name, info in loaded_layers.items():
    geojson_layers[layer_name] = {
        "geojson": json.loads(info["gdf"].to_json()),
        "color": info["color"],
        "theme": info["theme"],
        "count": info["count"],
    }

# Stats by theme
theme_counts = {}
for info in loaded_layers.values():
    theme_counts[info["theme"]] = theme_counts.get(info["theme"], 0) + info["count"]

total_features = sum(info["count"] for info in loaded_layers.values())

# Land use analysis
landuse_counts = {}
if "geonode:existing_landuse" in loaded_layers:
    lu_gdf = loaded_layers["geonode:existing_landuse"]["gdf"]
    for col in ['landuse', 'type', 'name', 'lu_type', 'category', 'class']:
        if col in lu_gdf.columns:
            landuse_counts = lu_gdf[col].value_counts().dropna().head(12).to_dict()
            break
    if not landuse_counts and len(lu_gdf.columns) > 1:
        # Try first non-geometry string column
        for col in lu_gdf.columns:
            if col != 'geometry' and lu_gdf[col].dtype == 'object':
                landuse_counts = lu_gdf[col].value_counts().dropna().head(12).to_dict()
                break

# Datasets table rows
datasets_rows = ""
for ds in datasets_list:
    subtype = ds.get('subtype', 'N/A')
    title = ds.get('title', 'Untitled')
    badge_color = '#007064' if subtype == 'vector' else '#E8A838' if subtype == 'raster' else '#6B7280'
    datasets_rows += f"""
        <tr>
            <td>{title}</td>
            <td><span class="badge" style="background:{badge_color}">{subtype}</span></td>
        </tr>"""

# Layer stats table rows
layer_stats_rows = ""
for s in layer_stats:
    layer_stats_rows += f"""
        <tr>
            <td>{s['theme']}</td>
            <td><code>{s['layer']}</code></td>
            <td>{s['features']:,}</td>
            <td>{s['geom_type']}</td>
        </tr>"""

# Theme chart data
chart_theme_labels = json.dumps(list(theme_counts.keys()))
chart_theme_values = json.dumps(list(theme_counts.values()))
theme_colors = json.dumps(['#E74C3C', '#E67E22', '#27AE60', '#3498DB', '#2ECC71', '#8E44AD'][:len(theme_counts)])

# Land use chart data
chart_lu_labels = json.dumps(list(landuse_counts.keys()))
chart_lu_values = json.dumps(list(landuse_counts.values()))

# Build JS layer toggle controls
layer_toggles = ""
for theme_name, theme in THEMES.items():
    layer_toggles += f'<div class="toggle-group"><div class="toggle-title">{theme_name}</div>'
    for layer_name, style in theme["layers"].items():
        short = layer_name.replace("geonode:", "")
        count = loaded_layers.get(layer_name, {}).get("count", 0)
        checked = "checked" if layer_name in loaded_layers else ""
        layer_toggles += f"""
            <label class="toggle-item">
                <input type="checkbox" {checked} onchange="toggleLayer('{layer_name}', this.checked)">
                <span class="color-dot" style="background:{style['color']}"></span>
                {short} <span class="feat-count">({count:,})</span>
            </label>"""
    layer_toggles += '</div>'

# ---------- 5. Generate HTML Dashboard -----------
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tanga CRD Dashboard</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: #F0F2F5; color: #1a1a1a; }}

        .header {{
            background: linear-gradient(135deg, #1B2A4A 0%, #2C3E6B 60%, #3B5998 100%);
            color: white; padding: 24px 32px;
            display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        .header h1 {{ font-size: 1.6rem; font-weight: 700; }}
        .header .subtitle {{ font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }}
        .header .timestamp {{ font-size: 0.75rem; opacity: 0.7; text-align: right; }}

        .stats-bar {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px; padding: 20px 32px;
        }}
        .stat-card {{
            background: white; border-radius: 12px; padding: 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .stat-card .label {{ font-size: 0.7rem; color: #6B7280; text-transform: uppercase;
            letter-spacing: 0.05em; font-weight: 600; }}
        .stat-card .value {{ font-size: 1.7rem; font-weight: 700; margin-top: 4px; }}
        .stat-card:nth-child(1) {{ border-left: 4px solid #E74C3C; }}
        .stat-card:nth-child(1) .value {{ color: #E74C3C; }}
        .stat-card:nth-child(2) {{ border-left: 4px solid #3498DB; }}
        .stat-card:nth-child(2) .value {{ color: #3498DB; }}
        .stat-card:nth-child(3) {{ border-left: 4px solid #27AE60; }}
        .stat-card:nth-child(3) .value {{ color: #27AE60; }}
        .stat-card:nth-child(4) {{ border-left: 4px solid #E67E22; }}
        .stat-card:nth-child(4) .value {{ color: #E67E22; }}
        .stat-card:nth-child(5) {{ border-left: 4px solid #8E44AD; }}
        .stat-card:nth-child(5) .value {{ color: #8E44AD; }}

        .main-grid {{
            display: grid; grid-template-columns: 280px 1fr;
            gap: 20px; padding: 0 32px 20px;
        }}
        @media (max-width: 900px) {{ .main-grid {{ grid-template-columns: 1fr; }} }}

        .sidebar {{ display: flex; flex-direction: column; gap: 16px; }}

        .card {{
            background: white; border-radius: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden;
        }}
        .card-header {{
            padding: 14px 18px; font-weight: 600; font-size: 0.9rem;
            border-bottom: 1px solid #E5E7EB; color: #1B2A4A;
        }}
        .card-body {{ padding: 0; }}

        #map {{ height: 550px; width: 100%; }}

        .toggle-group {{ padding: 8px 14px; border-bottom: 1px solid #F0F0F0; }}
        .toggle-title {{ font-size: 0.7rem; font-weight: 700; color: #1B2A4A;
            text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
        .toggle-item {{
            display: flex; align-items: center; gap: 6px; padding: 3px 0;
            font-size: 0.78rem; cursor: pointer; color: #374151;
        }}
        .toggle-item input {{ margin: 0; cursor: pointer; }}
        .color-dot {{
            width: 10px; height: 10px; border-radius: 50%; display: inline-block;
        }}
        .feat-count {{ color: #9CA3AF; font-size: 0.7rem; }}

        .bottom-grid {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 20px; padding: 0 32px 20px;
        }}
        @media (max-width: 900px) {{ .bottom-grid {{ grid-template-columns: 1fr; }} }}

        .chart-container {{ padding: 20px; height: 340px; }}

        table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
        th {{ background: #F0F2F5; padding: 10px 14px; text-align: left;
            font-weight: 600; color: #1B2A4A; position: sticky; top: 0; }}
        td {{ padding: 9px 14px; border-bottom: 1px solid #F0F2F5; }}
        tr:hover {{ background: #F7F9FC; }}
        code {{ background: #F0F2F5; padding: 2px 6px; border-radius: 4px;
            font-size: 0.75rem; color: #374151; }}

        .badge {{
            display: inline-block; padding: 2px 10px; border-radius: 12px;
            color: white; font-size: 0.72rem; font-weight: 600;
        }}

        .table-scroll {{ max-height: 340px; overflow-y: auto; }}

        .footer {{
            text-align: center; padding: 20px; font-size: 0.75rem; color: #9CA3AF;
        }}
        .footer a {{ color: #2C3E6B; text-decoration: none; }}

        .layer-panel {{ max-height: 520px; overflow-y: auto; }}
    </style>
</head>
<body>

<div class="header">
    <div>
        <h1>Tanga Urban Planning Dashboard</h1>
        <div class="subtitle">Community Resilience Database &mdash; Resilience Academy &mdash; Masterplan 2016-2036</div>
    </div>
    <div class="timestamp">
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
        Source: crd.resilienceacademy.ac.tz
    </div>
</div>

<div class="stats-bar">
    <div class="stat-card">
        <div class="label">Total Features Loaded</div>
        <div class="value">{total_features:,}</div>
    </div>
    <div class="stat-card">
        <div class="label">CRD Datasets</div>
        <div class="value">{total_datasets}</div>
    </div>
    <div class="stat-card">
        <div class="label">Themes</div>
        <div class="value">{len(THEMES)}</div>
    </div>
    <div class="stat-card">
        <div class="label">Layers Loaded</div>
        <div class="value">{len(loaded_layers)}</div>
    </div>
    <div class="stat-card">
        <div class="label">City</div>
        <div class="value" style="font-size:1.1rem">Tanga, TZ</div>
    </div>
</div>

<!-- Map + Layer Panel -->
<div class="main-grid">
    <div class="sidebar">
        <div class="card">
            <div class="card-header">Layer Controls</div>
            <div class="card-body layer-panel">
                {layer_toggles}
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-header">Tanga Interactive Map</div>
        <div class="card-body"><div id="map"></div></div>
    </div>
</div>

<!-- Charts & Tables -->
<div class="bottom-grid">
    <!-- Features by Theme Chart -->
    <div class="card">
        <div class="card-header">Features by Theme</div>
        <div class="card-body">
            <div class="chart-container">
                <canvas id="themeChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Land Use Chart -->
    <div class="card">
        <div class="card-header">Land Use Categories</div>
        <div class="card-body">
            <div class="chart-container">
                <canvas id="landUseChart"></canvas>
            </div>
        </div>
    </div>

    <!-- Loaded Layers Table -->
    <div class="card">
        <div class="card-header">Loaded Layer Details ({len(loaded_layers)} layers)</div>
        <div class="card-body">
            <div class="table-scroll">
                <table>
                    <thead><tr><th>Theme</th><th>Layer</th><th>Features</th><th>Geometry</th></tr></thead>
                    <tbody>{layer_stats_rows}</tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- All CRD Datasets Table -->
    <div class="card">
        <div class="card-header">All Tanga Datasets in CRD ({total_datasets})</div>
        <div class="card-body">
            <div class="table-scroll">
                <table>
                    <thead><tr><th>Dataset Title</th><th>Type</th></tr></thead>
                    <tbody>{datasets_rows}</tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<div class="footer">
    Data from <a href="https://crd.resilienceacademy.ac.tz" target="_blank">Resilience Academy CRD</a>
    &bull; Tanga Masterplan 2016-2036 &bull; Dashboard generated with Python, Leaflet &amp; Chart.js
</div>

<script>
    // ---- Map ----
    var map = L.map('map').setView([{center_lat}, {center_lon}], 13);

    var baseLayers = {{
        'CartoDB Light': L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}@2x.png', {{
            attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19
        }}),
        'OpenStreetMap': L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; OpenStreetMap', maxZoom: 19
        }}),
        'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: '&copy; Esri', maxZoom: 19
        }})
    }};
    baseLayers['CartoDB Light'].addTo(map);
    L.control.layers(baseLayers).addTo(map);

    // ---- Load GeoJSON layers ----
    var allLayers = {{}};
    var layerData = {json.dumps({k: {"geojson": v["geojson"], "color": v["color"], "theme": v["theme"]} for k, v in geojson_layers.items()})};

    function styleFeature(color, geomType) {{
        if (geomType === 'Point' || geomType === 'MultiPoint') {{
            return null; // handled by pointToLayer
        }}
        return {{
            color: color, weight: geomType.includes('Line') ? 3 : 2,
            opacity: 0.8, fillColor: color, fillOpacity: 0.25
        }};
    }}

    for (var layerName in layerData) {{
        var data = layerData[layerName];
        var layer = L.geoJSON(data.geojson, {{
            style: function(feature) {{
                var gt = feature.geometry.type;
                return styleFeature(data.color, gt);
            }},
            pointToLayer: function(feature, latlng) {{
                var color = data.color;
                return L.circleMarker(latlng, {{
                    radius: 6, fillColor: color, color: '#fff',
                    weight: 1.5, opacity: 1, fillOpacity: 0.8
                }});
            }},
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var popup = '<div style="font-family:Inter,sans-serif;font-size:12px;max-width:250px">';
                popup += '<div style="font-weight:700;margin-bottom:6px;color:#1B2A4A;border-bottom:1px solid #eee;padding-bottom:4px">' + layerName.replace('geonode:', '') + '</div>';
                for (var key in props) {{
                    if (props[key] && key !== 'geometry') {{
                        popup += '<b>' + key + ':</b> ' + props[key] + '<br>';
                    }}
                }}
                popup += '</div>';
                layer.bindPopup(popup);
            }}
        }});
        // closure to capture correct color
        (function(ln, col) {{
            allLayers[ln] = L.geoJSON(layerData[ln].geojson, {{
                style: function(feature) {{
                    return styleFeature(col, feature.geometry.type);
                }},
                pointToLayer: function(feature, latlng) {{
                    return L.circleMarker(latlng, {{
                        radius: 6, fillColor: col, color: '#fff',
                        weight: 1.5, opacity: 1, fillOpacity: 0.8
                    }});
                }},
                onEachFeature: function(feature, layer) {{
                    var props = feature.properties;
                    var popup = '<div style="font-family:Inter,sans-serif;font-size:12px;max-width:250px">';
                    popup += '<div style="font-weight:700;margin-bottom:6px;color:#1B2A4A;border-bottom:1px solid #eee;padding-bottom:4px">' + ln.replace('geonode:', '') + '</div>';
                    for (var key in props) {{
                        if (props[key] && key !== 'geometry') {{
                            popup += '<b>' + key + ':</b> ' + props[key] + '<br>';
                        }}
                    }}
                    popup += '</div>';
                    layer.bindPopup(popup);
                }}
            }}).addTo(map);
        }})(layerName, data.color);
    }}

    function toggleLayer(name, visible) {{
        if (allLayers[name]) {{
            if (visible) {{ map.addLayer(allLayers[name]); }}
            else {{ map.removeLayer(allLayers[name]); }}
        }}
    }}

    // ---- Theme Doughnut Chart ----
    new Chart(document.getElementById('themeChart').getContext('2d'), {{
        type: 'doughnut',
        data: {{
            labels: {chart_theme_labels},
            datasets: [{{
                data: {chart_theme_values},
                backgroundColor: {theme_colors},
                borderWidth: 2, borderColor: '#fff'
            }}]
        }},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{
                legend: {{ position: 'right', labels: {{ font: {{ size: 11 }}, padding: 12 }} }}
            }}
        }}
    }});

    // ---- Land Use Bar Chart ----
    new Chart(document.getElementById('landUseChart').getContext('2d'), {{
        type: 'bar',
        data: {{
            labels: {chart_lu_labels},
            datasets: [{{
                label: 'Count',
                data: {chart_lu_values},
                backgroundColor: '#27AE60',
                borderRadius: 4
            }}]
        }},
        options: {{
            indexAxis: 'y',
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ color: '#F0F2F5' }} }},
                y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
            }}
        }}
    }});
</script>

</body>
</html>"""

# ---------- 6. Save and open -----------
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crd_tanga_dashboard.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nDashboard saved: {output_path}")

# Export summary CSV
stats_df = pd.DataFrame(layer_stats)
stats_df.to_csv('tanga_layer_stats.csv', index=False)
print("Layer stats exported: tanga_layer_stats.csv")

webbrowser.open(f'file://{output_path}')
print("Dashboard opened in browser!")
