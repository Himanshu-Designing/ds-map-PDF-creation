import os
import io

# CRITICAL: Clear any existing PROJ environment variables
for key in ['PROJ_LIB', 'PROJ_DATA', 'GDAL_DATA']:
    if key in os.environ:
        del os.environ[key]

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server
import matplotlib.pyplot as plt
import geopandas as gpd
import osmnx as ox
from shapely.geometry import box
import numpy as np
from matplotlib.lines import Line2D


def generate_pdf_from_geojson(geojson_data: dict, padding: float = 0.002) -> bytes:
    """
    Generate a PDF map from GeoJSON data with OSM context.

    Args:
        geojson_data: Dictionary containing GeoJSON data
        padding: Bounding box padding in degrees (default ~200m)

    Returns:
        bytes: PDF file content
    """
    # Create GeoDataFrame from GeoJSON
    print("Step 0")
    gdf = gpd.GeoDataFrame.from_features(geojson_data['features'])

    # Set CRS if provided, otherwise assume WGS84
    if 'crs' in geojson_data:
        gdf.crs = geojson_data['crs']
    elif gdf.crs is None:
        gdf.crs = 'EPSG:4326'

    # Convert to WGS84 (required for OSMnx)
    gdf_wgs84 = gdf.to_crs(epsg=4326)

    # Get bounding box with padding for context
    bbox = gdf_wgs84.total_bounds
    bbox_padded = [
        bbox[0] - padding,  # west
        bbox[1] - padding,  # south
        bbox[2] + padding,  # east
        bbox[3] + padding   # north
    ]

    polygon = box(bbox_padded[0], bbox_padded[1], bbox_padded[2], bbox_padded[3])

    # Create a figure with desired size
    fig, ax = plt.subplots(figsize=(11, 8.5), facecolor='white')
    ax.set_facecolor('#d9d9d9')  # Light background

    # Download and plot different layers

    # 1. Download BUILDINGS
    print("Step 1")
    try:
        buildings = ox.features_from_polygon(
            polygon,
            tags={'building': True}
        )
        buildings = buildings[buildings.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        buildings.plot(ax=ax,
                      facecolor='#cfbbab',
                      edgecolor='#999999',
                      linewidth=0.3,
                      alpha=0.7,
                      zorder=2)
    except Exception:
        pass

    # 2. Download WATER BODIES
    print("Step 2")
    try:
        water = ox.features_from_polygon(
            polygon,
            tags={'natural': ['water', 'waterway'], 'waterway': True}
        )
        water_poly = water[water.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        if len(water_poly) > 0:
            water_poly.plot(ax=ax,
                          facecolor='#aad3df',
                          edgecolor='#6ba3b8',
                          linewidth=0.5,
                          alpha=0.7,
                          zorder=1)
    except Exception:
        pass

    # 3. Download GREEN SPACES (parks, gardens)
    print("Step 3")
    try:
        green = ox.features_from_polygon(
            polygon,
            tags={'leisure': ['park', 'garden'], 'landuse': ['grass', 'forest', 'recreation_ground']}
        )
        green = green[green.geometry.type.isin(['Polygon', 'MultiPolygon'])]
        if len(green) > 0:
            green.plot(ax=ax,
                      facecolor='#c8e6c9',
                      edgecolor='#81c784',
                      linewidth=0.3,
                      alpha=0.5,
                      zorder=1)
    except Exception:
        pass

    # 4. Download STREET NETWORK with names
    print("Step 4")
    edges = None
    try:
        G = ox.graph_from_polygon(
            polygon,
            network_type='all',
            simplify=False
        )
        nodes, edges = ox.graph_to_gdfs(G)

        # Classify and plot roads by type with better visibility
        highway_styles = {
            'motorway': {'color': '#e8926b', 'width': 4, 'zorder': 7, 'alpha': 1},
            'trunk': {'color': '#f9b380', 'width': 3, 'zorder': 6, 'alpha': 1},
            'primary': {'color': '#fcd6a4', 'width': 2.5, 'zorder': 5, 'alpha': 1},
            'secondary': {'color': '#ffffff', 'width': 2, 'zorder': 4, 'alpha': 1},
            'tertiary': {'color': '#ffffff', 'width': 1.5, 'zorder': 4, 'alpha': 1},
            'residential': {'color': '#ffffff', 'width': 1.2, 'zorder': 3, 'alpha': 0.9},
            'service': {'color': '#ffffff', 'width': 0.8, 'zorder': 3, 'alpha': 0.8},
            'footway': {'color': '#f0f0f0', 'width': 0.5, 'zorder': 2, 'alpha': 0.6},
            'path': {'color': '#f0f0f0', 'width': 0.5, 'zorder': 2, 'alpha': 0.6},
        }

        # Plot roads by type
        for road_type, style in highway_styles.items():
            if 'highway' in edges.columns:
                mask = edges['highway'].apply(
                    lambda x: road_type in str(x).lower() if x is not None else False
                )
                roads_subset = edges[mask]
                if len(roads_subset) > 0:
                    roads_subset.plot(ax=ax,
                                    linewidth=style['width'],
                                    color=style['color'],
                                    edgecolor='#666666',
                                    alpha=style['alpha'],
                                    zorder=style['zorder'])
    except Exception:
        pass

    # 5. Add STREET NAMES (Smart placement - only once per street)
    print("Step 5")
    if edges is not None and 'name' in edges.columns:
        street_labels = {}

        # Filter for major streets only
        major_streets = edges[
            (edges['highway'].apply(lambda x: any(t in str(x).lower() for t in ['primary', 'secondary', 'tertiary', 'residential', 'trunk']) if x is not None else False)) &
            (edges['name'].notna())
        ].copy()

        # For each unique street name, find the longest segment
        for idx, row in major_streets.iterrows():
            try:
                name = row['name']
                if isinstance(name, list):
                    name = name[0]

                name = str(name).strip()

                # Only keep the longest segment for each street name
                length = row.geometry.length
                if name not in street_labels or length > street_labels[name]['length']:
                    coords = list(row.geometry.coords)
                    if len(coords) >= 2:
                        # Calculate angle
                        dx = coords[-1][0] - coords[0][0]
                        dy = coords[-1][1] - coords[0][1]
                        angle = np.degrees(np.arctan2(dy, dx))

                        # Keep text readable
                        if angle > 90:
                            angle -= 180
                        elif angle < -90:
                            angle += 180

                        street_labels[name] = {
                            'geometry': row.geometry,
                            'length': length,
                            'angle': angle
                        }
            except:
                pass

        # Now plot only ONE label per street
        for name, data in street_labels.items():
            try:
                centroid = data['geometry'].centroid

                ax.text(centroid.x, centroid.y, name,
                       fontsize=7,
                       ha='center',
                       va='center',
                       rotation=data['angle'],
                       color='#333333',
                       fontweight='normal',
                       fontstyle='italic',
                       bbox=dict(boxstyle='round,pad=0.3',
                               facecolor='white',
                               edgecolor='none',
                               alpha=0.8),
                       zorder=15)
            except:
                pass

    # 6. Plot YOUR DATA on top (most important layer)
    print("Step 6")
    gdf_wgs84.plot(ax=ax,
                   legend=True,
                   cmap='Reds',
                   edgecolor='darkred',
                   linewidth=2.5,
                   alpha=0.8,
                   zorder=20)

    # Styling
    ax.set_title('Map with Streets, Buildings and Labels',
                 fontsize=18,
                 fontweight='bold',
                 pad=20)
    ax.set_xlabel('Longitude', fontsize=11)
    ax.set_ylabel('Latitude', fontsize=11)

    # Add subtle grid
    ax.grid(True, alpha=0.2, linestyle=':', linewidth=0.5, color='gray')

    # Add north arrow
    ax.annotate('N', xy=(0.96, 0.96), xycoords='axes fraction',
               fontsize=18, fontweight='bold',
               ha='center', va='center',
               bbox=dict(boxstyle='circle', facecolor='white', edgecolor='black', linewidth=2))
    ax.annotate('↑', xy=(0.96, 0.94), xycoords='axes fraction',
               fontsize=14, ha='center', va='top')

    # Add legend for your data
    legend_elements = [
        Line2D([0], [0], color='darkred', linewidth=3, label='Your Data'),
        Line2D([0], [0], color='#666666', linewidth=2, label='Roads'),
        plt.Rectangle((0, 0), 1, 1, fc='#d9d9d9', ec='#999999', label='Buildings'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9, framealpha=0.9)

    # Tight layout
    plt.tight_layout()

    # Save to bytes buffer instead of file
    buffer = io.BytesIO()
    plt.savefig(buffer,
                format='pdf',
                dpi=300,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none')
    plt.close()

    # Get the PDF bytes
    buffer.seek(0)
    return buffer.read()
