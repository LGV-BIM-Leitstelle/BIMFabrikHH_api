"""
In-memory GeoTIFF processing utilities.

Downloads GeoTIFF files from URLs and processes them in memory without saving to disk.
"""

import logging
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
import rasterio
from rasterio.io import MemoryFile

logger = logging.getLogger(__name__)


def download_geotiff_to_memory(url: str, timeout: int = 60) -> Optional[BytesIO]:
    """
    Download a GeoTIFF file from URL into memory.
    
    Args:
        url: URL to the GeoTIFF file.
        timeout: Request timeout in seconds.
        
    Returns:
        BytesIO object containing the GeoTIFF data, or None if download failed.
    """
    try:
        logger.info(f"Downloading GeoTIFF from: {url}")
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        
        buffer = BytesIO(response.content)
        logger.info(f"Downloaded {len(response.content) / 1024 / 1024:.2f} MB")
        return buffer
    except requests.RequestException as e:
        logger.error(f"Failed to download GeoTIFF: {e}")
        return None


def extract_elevation_from_memory(
    geotiff_data: BytesIO,
    x_coords: List[float],
    y_coords: List[float]
) -> List[Optional[float]]:
    """
    Extract elevation values at specific coordinates from in-memory GeoTIFF.
    
    Args:
        geotiff_data: BytesIO object containing GeoTIFF data.
        x_coords: List of X coordinates (UTM).
        y_coords: List of Y coordinates (UTM).
        
    Returns:
        List of elevation values (None for points outside raster).
    """
    geotiff_data.seek(0)  # Reset buffer position
    
    with MemoryFile(geotiff_data) as memfile:
        with memfile.open() as dataset:
            elevations = []
            for x, y in zip(x_coords, y_coords):
                try:
                    row, col = dataset.index(x, y)
                    if 0 <= row < dataset.height and 0 <= col < dataset.width:
                        value = dataset.read(1)[row, col]
                        elevations.append(float(value) if value != dataset.nodata else None)
                    else:
                        elevations.append(None)
                except (ValueError, IndexError):
                    elevations.append(None)
            return elevations


def extract_terrain_mesh_from_memory(
    geotiff_data: BytesIO,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    downsample_factor: int = 4
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract terrain mesh data from in-memory GeoTIFF.
    
    Args:
        geotiff_data: BytesIO object containing GeoTIFF data.
        bbox: Optional bounding box (min_x, min_y, max_x, max_y) in UTM.
        downsample_factor: Factor to downsample the raster data.
        
    Returns:
        Tuple of (x_coords, y_coords, z_values) numpy arrays.
    """
    geotiff_data.seek(0)  # Reset buffer position
    
    with MemoryFile(geotiff_data) as memfile:
        with memfile.open() as dataset:
            # Read the raster data
            data = dataset.read(1)
            transform = dataset.transform
            nodata = dataset.nodata
            
            # Downsample
            data = data[::downsample_factor, ::downsample_factor]
            
            # Get coordinates
            height, width = data.shape
            rows, cols = np.meshgrid(
                np.arange(0, height) * downsample_factor,
                np.arange(0, width) * downsample_factor,
                indexing='ij'
            )
            
            # Transform to UTM coordinates
            x_coords = transform.c + (cols + 0.5) * transform.a
            y_coords = transform.f + (rows + 0.5) * transform.e
            z_values = data
            
            # Flatten arrays
            x_flat = x_coords.flatten()
            y_flat = y_coords.flatten()
            z_flat = z_values.flatten()
            
            # Remove nodata values
            if nodata is not None:
                valid_mask = z_flat != nodata
                x_flat = x_flat[valid_mask]
                y_flat = y_flat[valid_mask]
                z_flat = z_flat[valid_mask]
            
            # Filter by bounding box if provided
            if bbox is not None:
                min_x, min_y, max_x, max_y = bbox
                bbox_mask = (
                    (x_flat >= min_x) & (x_flat <= max_x) &
                    (y_flat >= min_y) & (y_flat <= max_y)
                )
                x_flat = x_flat[bbox_mask]
                y_flat = y_flat[bbox_mask]
                z_flat = z_flat[bbox_mask]
            
            return x_flat, y_flat, z_flat


def download_multiple_geotiffs(
    base_url: str,
    filenames: List[str],
    timeout: int = 60
) -> Dict[str, BytesIO]:
    """
    Download multiple GeoTIFF files into memory.
    
    Args:
        base_url: Base URL for the GeoTIFF files.
        filenames: List of filenames to download.
        timeout: Request timeout in seconds.
        
    Returns:
        Dictionary mapping filename to BytesIO buffer.
    """
    buffers = {}
    for filename in filenames:
        url = f"{base_url}/{filename}"
        buffer = download_geotiff_to_memory(url, timeout)
        if buffer is not None:
            buffers[filename] = buffer
        else:
            logger.warning(f"Failed to download: {filename}")
    return buffers

