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
print("  Mwanza Urban Planning Dashboard")
print("  Source: Resilience Academy CRD")
print("=" * 60)

# ---------- 1. List Mwanza datasets via REST API -----------
print("\nFetching Mwanza datasets from CRD API...")
r = requests.get(f"{CRD}/api/v2/resources", params={
    "filter{regions.name.in}": "Mwanza",
    "page_size": 200
})
mwanza_datasets = r.json()
total_datasets = mwanza_datasets['total']
datasets_list = mwanza_datasets['resources']
print(f"Mwanza datasets found: {total_datasets}")

# ---------- 2. Define layers to load by theme -----------
THEMES = {
    "Administrative Boundaries": {
        "layers": {
            "geonode:regional_boundaries": {"color": "#8E44AD", "weight": 3, "fill": 0.05},
            "geonode:district_boundaries_9a3af830e8c06df98d4319c7d480c542": {"color": "#C0392B", "weight": 2.5, "fill": 0.08},
            "geonode:ward_boundaries_3f7b0f55ee9ba5ff1b1d6823c209cd35": {"color": "#E67E22", "weight": 1.5, "fill": 0.06},
        },
        "description": "Regional, district & ward boundaries"
    },
    "Health Facilities": {
        "layers": {
            "geonode:mwanza_health_facilities": {"color": "#E74C3C", "weight": 2, "fill": 0.7},
        },
        "description": "Hospitals, clinics & health centres"
    },
    "Businesses & Finance": {
        "layers": {
            "geonode:mwanza_businesses": {"color": "#007064", "weight": 1, "fill": 0.6},
            "geonode:mwanza_financial_amenities": {"color": "#1ABC9C", "weight": 1, "fill": 0.7},
        },
        "description": "Businesses & financial amenities"
    },
    "Road Network": {
        "layers": {
            "geonode:mwanza_roads": {"color": "#F39C12", "weight": 2, "fill": 0},
            "geonode:existing_road_centreline": {"color": "#D4AC6E", "weight": 1.5, "fill": 0},
        },
        "description": "Existing road infrastructure"
    },
    "Land Use": {
        "layers": {
            "geonode:existing_landuse_plan": {"color": "#27AE60", "weight": 1.5, "fill": 0.2},
        },
        "description": "Current land use zones"
    },
    "Water Supply": {
        "layers": {
            "geonode:existing_water_supply_network": {"color": "#3498DB", "weight": 2, "fill": 0},
            "geonode:existing_water_supply_zone": {"color": "#2980B9", "weight": 1.5, "fill": 0.1},
            "geonode:existing_service_reservoir": {"color": "#1F618D", "weight": 2, "fill": 0.6},
        },
        "description": "Water supply network, zones & reservoirs"
    },
    "Drainage & Flood": {
        "layers": {
            "geonode:existing_natural_drainage_network": {"color": "#5DADE2", "weight": 2, "fill": 0},
            "geonode:mwanza_drainage_points": {"color": "#2E86C1", "weight": 1, "fill": 0.7},
        },
        "description": "Natural drainage & flood points"
    },
    "Hazards (Rockfall)": {
        "layers": {
            "geonode:mwanza_rockfall_locations": {"color": "#922B21", "weight": 2, "fill": 0.7},
            "geonode:mwanza_households_at_risk_of_rockfall": {"color": "#E74C3C", "weight": 1, "fill": 0.5},
        },
        "description": "Rockfall locations & at-risk households"
    },
    "Tourism & POI": {
        "layers": {
            "geonode:mwanza_tourist_facilities": {"color": "#AF7AC5", "weight": 1, "fill": 0.7},
            "geonode:mwanza_religious_facilities": {"color": "#7D3C98", "weight": 1, "fill": 0.7},
        },
        "description": "Tourism sites & religious facilities"
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
                "weight": style["weight"],
                "fill": style["fill"],
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
all_centroids_x, all_centroids_y = [], []
for info in loaded_layers.values():
    gdf = info["gdf"]
    if len(gdf) > 0:
        bounds = gdf.total_bounds
        all_centroids_x.append((bounds[0] + bounds[2]) / 2)
        all_centroids_y.append((bounds[1] + bounds[3]) / 2)

center_lat = sum(all_centroids_y) / len(all_centroids_y) if all_centroids_y else -2.52
center_lon = sum(all_centroids_x) / len(all_centroids_x) if all_centroids_x else 32.90

# Build GeoJSON per layer
geojson_layers = {}
for layer_name, info in loaded_layers.items():
    geojson_layers[layer_name] = {
        "geojson": json.loads(info["gdf"].to_json()),
        "color": info["color"],
        "weight": info["weight"],
        "fill": info["fill"],
        "theme": info["theme"],
        "count": info["count"],
    }

# Stats by theme
theme_counts = {}
for info in loaded_layers.values():
    theme_counts[info["theme"]] = theme_counts.get(info["theme"], 0) + info["count"]

total_features = sum(info["count"] for info in loaded_layers.values())

# Business type analysis
business_counts = {}
if "geonode:mwanza_businesses" in loaded_layers:
    biz_gdf = loaded_layers["geonode:mwanza_businesses"]["gdf"]
    for col in ['amenity', 'shop', 'office', 'landuse', 'building', 'type', 'category']:
        if col in biz_gdf.columns:
            business_counts = biz_gdf[col].value_counts().dropna().head(12).to_dict()
            break
    if not business_counts:
        for col in biz_gdf.columns:
            if col != 'geometry' and biz_gdf[col].dtype == 'object':
                vc = biz_gdf[col].value_counts().dropna()
                if len(vc) > 1:
                    business_counts = vc.head(12).to_dict()
                    break

# Land use analysis
landuse_counts = {}
if "geonode:existing_landuse_plan" in loaded_layers:
    lu_gdf = loaded_layers["geonode:existing_landuse_plan"]["gdf"]
    for col in ['landuse', 'type', 'name', 'lu_type', 'category', 'class']:
        if col in lu_gdf.columns:
            landuse_counts = lu_gdf[col].value_counts().dropna().head(12).to_dict()
            break
    if not landuse_counts:
        for col in lu_gdf.columns:
            if col != 'geometry' and lu_gdf[col].dtype == 'object':
                vc = lu_gdf[col].value_counts().dropna()
                if len(vc) > 1:
                    landuse_counts = vc.head(12).to_dict()
                    break

# Administrative stats
admin_stats = {}
for lname, label in [
    ("geonode:regional_boundaries", "Regions"),
    ("geonode:district_boundaries_9a3af830e8c06df98d4319c7d480c542", "Districts"),
    ("geonode:ward_boundaries_3f7b0f55ee9ba5ff1b1d6823c209cd35", "Wards"),
]:
    if lname in loaded_layers:
        gdf_a = loaded_layers[lname]["gdf"]
        admin_stats[label] = len(gdf_a)
        # Try to extract names
        for col in ['name', 'NAME', 'ward_name', 'district_n', 'region_nam', 'ADM1_EN', 'ADM2_EN', 'ADM3_EN']:
            if col in gdf_a.columns:
                names = gdf_a[col].dropna().unique().tolist()
                admin_stats[f"{label}_names"] = names
                break

# Dataset table rows
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

# Admin names cards
admin_cards_html = ""
for label in ["Regions", "Districts", "Wards"]:
    count = admin_stats.get(label, 0)
    names = admin_stats.get(f"{label}_names", [])
    names_str = ", ".join(sorted(names)[:20]) if names else "N/A"
    admin_cards_html += f"""
    <div class="admin-card">
        <div class="admin-count">{count}</div>
        <div class="admin-label">{label}</div>
        <div class="admin-names">{names_str}</div>
    </div>"""

# Chart data
chart_theme_labels = json.dumps(list(theme_counts.keys()))
chart_theme_values = json.dumps(list(theme_counts.values()))
theme_colors = json.dumps([
    '#8E44AD', '#E74C3C', '#007064', '#F39C12', '#27AE60',
    '#3498DB', '#5DADE2', '#922B21', '#AF7AC5'
][:len(theme_counts)])

chart_biz_labels = json.dumps(list(business_counts.keys()))
chart_biz_values = json.dumps(list(business_counts.values()))

chart_lu_labels = json.dumps(list(landuse_counts.keys()))
chart_lu_values = json.dumps(list(landuse_counts.values()))

# Layer toggle controls
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
    <title>Mwanza CRD Dashboard</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: #F0F4F3; color: #1a1a1a; }}

        .header {{
            background: linear-gradient(135deg, #004640 0%, #007064 60%, #009688 100%);
            color: white; padding: 24px 32px;
            display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        .header h1 {{ font-size: 1.6rem; font-weight: 700; }}
        .header .subtitle {{ font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }}
        .header .timestamp {{ font-size: 0.75rem; opacity: 0.7; text-align: right; }}

        .stats-bar {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 16px; padding: 20px 32px;
        }}
        .stat-card {{
            background: white; border-radius: 12px; padding: 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
        }}
        .stat-card .label {{ font-size: 0.7rem; color: #6B7280; text-transform: uppercase;
            letter-spacing: 0.05em; font-weight: 600; }}
        .stat-card .value {{ font-size: 1.7rem; font-weight: 700; margin-top: 4px; }}
        .stat-card:nth-child(1) {{ border-left: 4px solid #007064; }}
        .stat-card:nth-child(1) .value {{ color: #007064; }}
        .stat-card:nth-child(2) {{ border-left: 4px solid #E74C3C; }}
        .stat-card:nth-child(2) .value {{ color: #E74C3C; }}
        .stat-card:nth-child(3) {{ border-left: 4px solid #3498DB; }}
        .stat-card:nth-child(3) .value {{ color: #3498DB; }}
        .stat-card:nth-child(4) {{ border-left: 4px solid #F39C12; }}
        .stat-card:nth-child(4) .value {{ color: #F39C12; }}
        .stat-card:nth-child(5) {{ border-left: 4px solid #8E44AD; }}
        .stat-card:nth-child(5) .value {{ color: #8E44AD; }}
        .stat-card:nth-child(6) {{ border-left: 4px solid #27AE60; }}
        .stat-card:nth-child(6) .value {{ color: #27AE60; }}

        /* Admin boundary section */
        .admin-section {{
            padding: 0 32px 20px;
        }}
        .admin-section h2 {{
            font-size: 1rem; color: #004640; font-weight: 700; margin-bottom: 12px;
        }}
        .admin-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .admin-card {{
            background: white; border-radius: 12px; padding: 18px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.08);
            border-top: 3px solid #8E44AD;
        }}
        .admin-count {{
            font-size: 2rem; font-weight: 700; color: #8E44AD;
        }}
        .admin-label {{
            font-size: 0.8rem; font-weight: 600; color: #4A5568;
            text-transform: uppercase; letter-spacing: 0.04em;
        }}
        .admin-names {{
            font-size: 0.78rem; color: #6B7280; margin-top: 8px;
            line-height: 1.5;
        }}

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
            border-bottom: 1px solid #E5E7EB; color: #004640;
        }}
        .card-body {{ padding: 0; }}

        #map {{ height: 580px; width: 100%; }}

        .toggle-group {{ padding: 8px 14px; border-bottom: 1px solid #F0F0F0; }}
        .toggle-title {{ font-size: 0.7rem; font-weight: 700; color: #004640;
            text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
        .toggle-item {{
            display: flex; align-items: center; gap: 6px; padding: 3px 0;
            font-size: 0.76rem; cursor: pointer; color: #374151;
        }}
        .toggle-item input {{ margin: 0; cursor: pointer; }}
        .color-dot {{
            width: 10px; height: 10px; border-radius: 50%; display: inline-block;
        }}
        .feat-count {{ color: #9CA3AF; font-size: 0.7rem; }}

        .bottom-grid {{
            display: grid; grid-template-columns: 1fr 1fr 1fr;
            gap: 20px; padding: 0 32px 20px;
        }}
        @media (max-width: 1100px) {{ .bottom-grid {{ grid-template-columns: 1fr 1fr; }} }}
        @media (max-width: 700px) {{ .bottom-grid {{ grid-template-columns: 1fr; }} }}

        .chart-container {{ padding: 20px; height: 320px; }}

        .tables-grid {{
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 20px; padding: 0 32px 20px;
        }}
        @media (max-width: 900px) {{ .tables-grid {{ grid-template-columns: 1fr; }} }}

        table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
        th {{ background: #F0F4F3; padding: 10px 14px; text-align: left;
            font-weight: 600; color: #004640; position: sticky; top: 0; }}
        td {{ padding: 9px 14px; border-bottom: 1px solid #F0F4F3; }}
        tr:hover {{ background: #F7FAFA; }}
        code {{ background: #F0F4F3; padding: 2px 6px; border-radius: 4px;
            font-size: 0.75rem; color: #374151; }}

        .badge {{
            display: inline-block; padding: 2px 10px; border-radius: 12px;
            color: white; font-size: 0.72rem; font-weight: 600;
        }}

        .table-scroll {{ max-height: 360px; overflow-y: auto; }}

        .footer {{
            text-align: center; padding: 20px; font-size: 0.75rem; color: #9CA3AF;
        }}
        .footer a {{ color: #007064; text-decoration: none; }}

        .layer-panel {{ max-height: 550px; overflow-y: auto; }}
    </style>
</head>
<body>

<div class="header">
    <div>
        <h1>Mwanza Urban Planning Dashboard</h1>
        <div class="subtitle">Community Resilience Database &mdash; Resilience Academy &mdash; Mwanza Master Plan</div>
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
        <div class="label">Health Facilities</div>
        <div class="value">{loaded_layers.get("geonode:mwanza_health_facilities", {}).get("count", 0):,}</div>
    </div>
    <div class="stat-card">
        <div class="label">Water Supply Features</div>
        <div class="value">{theme_counts.get("Water Supply", 0):,}</div>
    </div>
    <div class="stat-card">
        <div class="label">Road Features</div>
        <div class="value">{theme_counts.get("Road Network", 0):,}</div>
    </div>
    <div class="stat-card">
        <div class="label">CRD Datasets</div>
        <div class="value">{total_datasets}</div>
    </div>
    <div class="stat-card">
        <div class="label">Themes</div>
        <div class="value">{len(THEMES)}</div>
    </div>
</div>

<!-- Administrative Boundaries Section -->
<div class="admin-section">
    <h2>Administrative Boundaries</h2>
    <div class="admin-grid">
        {admin_cards_html}
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
        <div class="card-header">Mwanza Interactive Map &mdash; {len(loaded_layers)} layers loaded</div>
        <div class="card-body"><div id="map"></div></div>
    </div>
</div>

<!-- Charts -->
<div class="bottom-grid">
    <div class="card">
        <div class="card-header">Features by Theme</div>
        <div class="card-body">
            <div class="chart-container">
                <canvas id="themeChart"></canvas>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-header">Business Categories</div>
        <div class="card-body">
            <div class="chart-container">
                <canvas id="bizChart"></canvas>
            </div>
        </div>
    </div>
    <div class="card">
        <div class="card-header">Land Use Categories</div>
        <div class="card-body">
            <div class="chart-container">
                <canvas id="landUseChart"></canvas>
            </div>
        </div>
    </div>
</div>

<!-- Tables -->
<div class="tables-grid">
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
    <div class="card">
        <div class="card-header">All Mwanza Datasets in CRD ({total_datasets})</div>
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
    &bull; Mwanza Master Plan &bull; Dashboard generated with Python, Leaflet &amp; Chart.js
</div>

<script>
    // ---- Map ----
    var map = L.map('map').setView([{center_lat}, {center_lon}], 12);

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
    var layerData = {json.dumps({k: {
        "geojson": v["geojson"],
        "color": v["color"],
        "weight": v["weight"],
        "fill": v["fill"],
        "theme": v["theme"]
    } for k, v in geojson_layers.items()})};

    // Render order: boundaries first, then polygons, lines, points last
    var renderOrder = [];
    var boundaryLayers = [];
    var otherLayers = [];
    for (var ln in layerData) {{
        if (layerData[ln].theme === 'Administrative Boundaries') {{
            boundaryLayers.push(ln);
        }} else {{
            otherLayers.push(ln);
        }}
    }}
    renderOrder = boundaryLayers.concat(otherLayers);

    renderOrder.forEach(function(layerName) {{
        var data = layerData[layerName];
        allLayers[layerName] = L.geoJSON(data.geojson, {{
            style: function(feature) {{
                var gt = feature.geometry.type;
                if (gt === 'Point' || gt === 'MultiPoint') return null;
                return {{
                    color: data.color,
                    weight: data.weight,
                    opacity: 0.85,
                    fillColor: data.color,
                    fillOpacity: data.fill,
                    dashArray: data.theme === 'Administrative Boundaries' ? '6 3' : null
                }};
            }},
            pointToLayer: function(feature, latlng) {{
                return L.circleMarker(latlng, {{
                    radius: 6, fillColor: data.color, color: '#fff',
                    weight: 1.5, opacity: 1, fillOpacity: 0.8
                }});
            }},
            onEachFeature: function(feature, layer) {{
                var props = feature.properties;
                var popup = '<div style="font-family:Inter,sans-serif;font-size:12px;max-width:280px">';
                popup += '<div style="font-weight:700;margin-bottom:6px;color:#004640;border-bottom:2px solid ' + data.color + ';padding-bottom:4px">' + layerName.replace('geonode:', '').replace(/_/g, ' ') + '</div>';
                var count = 0;
                for (var key in props) {{
                    if (props[key] && key !== 'geometry' && count < 12) {{
                        popup += '<b>' + key + ':</b> ' + props[key] + '<br>';
                        count++;
                    }}
                }}
                popup += '</div>';
                layer.bindPopup(popup);
            }}
        }}).addTo(map);
    }});

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
                legend: {{ position: 'right', labels: {{ font: {{ size: 10 }}, padding: 8 }} }}
            }}
        }}
    }});

    // ---- Business Bar Chart ----
    new Chart(document.getElementById('bizChart').getContext('2d'), {{
        type: 'bar',
        data: {{
            labels: {chart_biz_labels},
            datasets: [{{
                label: 'Count',
                data: {chart_biz_values},
                backgroundColor: '#007064',
                borderRadius: 4
            }}]
        }},
        options: {{
            indexAxis: 'y',
            responsive: true, maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ color: '#F0F4F3' }} }},
                y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
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
                x: {{ grid: {{ color: '#F0F4F3' }} }},
                y: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 10 }} }} }}
            }}
        }}
    }});
</script>

</body>
</html>"""

# ---------- 6. Save and open -----------
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mwanza_crd_dashboard.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nDashboard saved: {output_path}")

# Export stats CSV
stats_df = pd.DataFrame(layer_stats)
stats_df.to_csv('mwanza_layer_stats.csv', index=False)
print("Layer stats exported: mwanza_layer_stats.csv")

# Export business CSV
if "geonode:mwanza_businesses" in loaded_layers:
    biz_gdf = loaded_layers["geonode:mwanza_businesses"]["gdf"]
    export = biz_gdf.copy()
    export['longitude'] = export.geometry.centroid.x
    export['latitude'] = export.geometry.centroid.y
    export.drop(columns='geometry').to_csv('mwanza_businesses_stats.csv', index=False)
    print("Business data exported: mwanza_businesses_stats.csv")

webbrowser.open(f'file://{output_path}')
print("Dashboard opened in browser!")
