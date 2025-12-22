import os
import sys

# CRITICAL: Clear any existing PROJ environment variables
for key in ['PROJ_LIB', 'PROJ_DATA', 'GDAL_DATA']:
    if key in os.environ:
        del os.environ[key]

import matplotlib.pyplot as plt
import geopandas as gpd
import osmnx as ox
from shapely.geometry import box
import numpy as np
from collections import defaultdict

def main():
    print("Hello from cad-be!")
    print(f"OSMnx version: {ox.__version__}")
    
    # Read your GeoJSON file
    gdf = gpd.read_file('data.geojson')
    
    # Convert to WGS84 (required for OSMnx)
    gdf_wgs84 = gdf.to_crs(epsg=4326)
    print("step1 - Data loaded and reprojected")
    
    # Get bounding box with some padding for context
    bbox = gdf_wgs84.total_bounds
    padding = 0.002  # Add ~200m padding
    bbox_padded = [
        bbox[0] - padding,  # west
        bbox[1] - padding,  # south
        bbox[2] + padding,  # east
        bbox[3] + padding   # north
    ]
    print(f"Bounding box: West={bbox_padded[0]:.6f}, South={bbox_padded[1]:.6f}, East={bbox_padded[2]:.6f}, North={bbox_padded[3]:.6f}")
    
    polygon = box(bbox_padded[0], bbox_padded[1], bbox_padded[2], bbox_padded[3])
    
    # Create a figure with desired size
    fig, ax = plt.subplots(figsize=(11, 8.5), facecolor='white')
    ax.set_facecolor('#d9d9d9')  # Light background
    
    # Download and plot different layers
    print("\nstep2 - Downloading OpenStreetMap data...")
    
    # 1. Download BUILDINGS
    print("  → Downloading buildings...")
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
        print(f"    ✓ Plotted {len(buildings)} buildings")
    except Exception as e:
        print(f"    ✗ Buildings failed: {e}")
    
    # 2. Download WATER BODIES
    print("  → Downloading water bodies...")
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
        print(f"    ✓ Plotted {len(water)} water features")
    except Exception as e:
        print(f"    ✗ Water failed: {e}")
    
    # 3. Download GREEN SPACES (parks, gardens)
    print("  → Downloading green spaces...")
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
            print(f"    ✓ Plotted {len(green)} green spaces")
    except Exception as e:
        print(f"    ✗ Green spaces failed: {e}")
    
    # 4. Download STREET NETWORK with names
    print("  → Downloading street network...")
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
        
        print(f"    ✓ Plotted {len(edges)} street segments")
        
    except Exception as e:
        print(f"    ✗ Streets failed: {e}")
    
    # 5. Add STREET NAMES (Smart placement - only once per street)
    print("  → Adding street names...")
    if edges is not None and 'name' in edges.columns:
        # Group streets by name and find the longest segment for each
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
        
        print(f"    ✓ Added {len(street_labels)} unique street labels")
    
    # 6. Plot YOUR DATA on top (most important layer)
    print("\nstep3 - Plotting your data...")
    gdf_wgs84.plot(ax=ax, 
                   legend=True,
                   cmap='Reds',
                   edgecolor='darkred',
                   linewidth=2.5,
                   alpha=0.8,
                   zorder=20)
    
    print("step4 - Finalizing map...")
    
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
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='darkred', linewidth=3, label='Your Data'),
        Line2D([0], [0], color='#666666', linewidth=2, label='Roads'),
        plt.Rectangle((0, 0), 1, 1, fc='#d9d9d9', ec='#999999', label='Buildings'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9, framealpha=0.9)
    
    # Tight layout
    plt.tight_layout()
    
    # Export as high-quality vector PDF
    print("step5 - Saving PDF...")
    plt.savefig('output_map_detailed.pdf', 
                format='pdf',
                dpi=300,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none')
    plt.close()
    
    print("\n✓ Detailed vector PDF saved successfully!")
    print("  ✓ Streets are now clearly visible with better contrast")
    print("  ✓ Street names appear only ONCE per unique street")
    print("  ✓ Professional cartographic styling applied")
    print("  ✓ Map will stay sharp at any zoom level")

if __name__ == "__main__":
    main()