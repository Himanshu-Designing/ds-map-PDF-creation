# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python backend project combining two components:
1. **FastAPI Web API** - A simple REST API service for health checks
2. **Geospatial Mapping Script** - A standalone script (`pdf.py`) for generating detailed vector maps from GeoJSON data using OpenStreetMap data

## Technology Stack

- **Web Framework**: FastAPI
- **Geospatial Libraries**: GDAL/PROJ (via pyogrio, rasterio), GeoPandas, OSMnx, Shapely
- **Visualization**: Matplotlib, Contextily
- **Python Version**: 3.13 (based on .venv configuration)

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1  # Windows PowerShell
# or
source .venv/bin/activate    # Unix-like systems

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run FastAPI server (default development mode)
uvicorn app.main:app --reload

# Run FastAPI with specific host/port
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Run the standalone mapping script
python pdf.py
```

## Architecture

### FastAPI Application Structure
```
app/
├── main.py              # FastAPI app entry point, root endpoint
├── core/
│   └── config.py        # Environment configuration (.env loading)
├── api/
│   └── health.py        # Health check router (/health endpoint)
├── models/              # (Currently empty - for data models)
└── services/            # (Currently empty - for business logic)
```

### Key Architectural Patterns

**Router-based Organization**: The FastAPI app uses APIRouter for modular endpoint organization. Health check endpoints are in `app/api/health.py` and mounted with `/health` prefix.

**Environment Configuration**: Uses `python-dotenv` to load configuration from `.env` file. The ENV variable defaults to "development".

**Geospatial Data Processing** (pdf.py):
1. Loads GeoJSON data and reprojects to WGS84 (EPSG:4326)
2. Downloads contextual OSM data (buildings, water, greenspaces, streets) for the bounding box
3. Renders layered map with proper z-ordering (background → streets → user data on top)
4. Applies cartographic styling with street name labels (one label per unique street)
5. Exports high-quality vector PDF at 300 DPI

## Important Implementation Details

### GDAL/PROJ Environment Variables
The `pdf.py` script **clears PROJ environment variables** (`PROJ_LIB`, `PROJ_DATA`, `GDAL_DATA`) at startup to avoid conflicts between system GDAL and Python package installations. This is critical for Windows environments where multiple GDAL installations may exist.

### Geospatial Data Layers (pdf.py)
Maps are rendered in this z-order (bottom to top):
1. Background color (#d9d9d9)
2. Water bodies (z=1)
3. Green spaces (z=1)
4. Buildings (z=2)
5. Streets by type (z=2-7, with motorways highest)
6. Street name labels (z=15, deduplicated by street name)
7. User GeoJSON data (z=20, always on top)

### Street Classification
Roads are styled by OpenStreetMap highway type with different widths and colors:
- Motorway: 4px, orange-red (#e8926b)
- Primary/Secondary/Tertiary: 2.5-1.5px, white
- Residential: 1.2px, white with 90% opacity
- Service roads and footpaths: 0.5-0.8px, light gray

## Dependencies

Key geospatial dependencies requiring native libraries (GDAL/PROJ):
- `rasterio==1.4.4` - Raster data I/O (includes GDAL bindings)
- `pyogrio==0.12.1` - Vector data I/O (GDAL alternative to Fiona)
- `geopandas==1.1.1` - Spatial dataframes
- `osmnx` - OpenStreetMap data download (not in requirements.txt but used in pdf.py)

Note: The requirements.txt is missing `osmnx`, `python-dotenv`, `fastapi`, and `uvicorn`. These should be added when running the application.
