from fastapi import APIRouter
import matplotlib.pyplot as plt
import geopandas as gpd
import contextily as cx

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("")
def health_check():
    return {"status": "OK"}