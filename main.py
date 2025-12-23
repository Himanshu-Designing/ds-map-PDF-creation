from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from app.api.health import router as health_router
from app.services.pdf_generator import generate_pdf_from_geojson
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI(title="Python Backend API",)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

@app.get("/")
def root():
    return {"status": "Backend is running"}

@app.post("/download")
async def download_pdf(file: UploadFile = File(...)):
    """
    Generate and download a PDF map from a GeoJSON file.

    This endpoint accepts a GeoJSON file and generates a detailed PDF map with:
    - OpenStreetMap context (buildings, water, green spaces, streets)
    - Street name labels
    - Professional cartographic styling
    - High-quality vector output (300 DPI)

    Args:
        file: GeoJSON file upload

    Returns:
        PDF file as downloadable response
    """
    # Validate file type
    if not file.filename.endswith('.geojson') and not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=400,
            detail="File must be a GeoJSON file (.geojson or .json)"
        )

    try:
        # Read and parse GeoJSON file
        contents = await file.read()
        geojson_data = json.loads(contents)

        # Validate basic GeoJSON structure
        if 'type' not in geojson_data or 'features' not in geojson_data:
            raise HTTPException(
                status_code=400,
                detail="Invalid GeoJSON format. Must contain 'type' and 'features' fields."
            )

        # Generate PDF
        pdf_bytes = generate_pdf_from_geojson(geojson_data)

        # Return as downloadable PDF
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=map_output.pdf"
            }
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON format in uploaded file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )
