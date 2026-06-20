# BIMFabrikHH API

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_api)
[![Python Version](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_api/pkgs/container/bimfabrikhh_api)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)

A FastAPI-based service for generating IFC (Industry Foundation Classes) models from Hamburg's open geospatial data.
Features OGC API Processes implementation with Celery-based asynchronous task processing for scalable BIM model
generation.

## Overview

This package is one of the main components of the BIMFabrikHH project, together with the following packages:

- **BIMFabrikHH_core**  
  - [GitHub](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_core)  
  - [OpenCode](https://gitlab.opencode.de/LGV-BIM-Leitstelle/bimfabrikhh_core)
- **ifcfactory**  
  - [GitHub](https://github.com/LGV-BIM-Leitstelle/ifcfactory)  
  - [OpenCode](https://gitlab.opencode.de/LGV-BIM-Leitstelle/ifcfactory)
- **BIMFabrikHH_api**  
  - [GitHub](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_api)  
  - [OpenCode](https://gitlab.opencode.de/LGV-BIM-Leitstelle/BIMFabrikHH_api)

These three packages make up the **BIMFabrikHH** Project, enabling automated BIM and IFC workflows as part of the Connected Urban Twins (CUT) project.

BIMFabrikHH is a development by the **Freie und Hansestadt Hamburg, Landesbetrieb Geoinformation und Vermessung,
BIM-Leitstelle** as part of the *Connected Urban Twins (CUT)* project. It provides automated conversion of geospatial
data from heterogeneous formats to IFC (Industry Foundation Classes) format, enabling BIM (Building Information
Modeling) methodology implementation.

Geospatial data such as DGM (Digital Terrain Models), city models, and other infrastructure data are crucial foundations
for construction planning. These data are often available as GIS data, but BIM methodology requires conversion to IFC
format. BIMFabrikHH aims to provide geospatial data in IFC format with relevant information from heterogeneous formats.

### Key Benefits

- **Automation**: Simplifies and standardizes repetitive processes through automation
- **Resource Efficiency**: Saves resources through streamlined workflows
- **BIM Adoption**: Promotes BIM usage within the City of Hamburg (FHH)
- **Usability**: Improves usability in the Master Portal
- **Universal Application**: One application for all geospatial data conversion needs
- **Modular Architecture**: Clean separation of concerns with reusable components

## Features
This project is under intensive development. Features are being added and improved rapidly; users should expect frequent updates, experimental components, and breaking changes as the platform evolves toward a stable and robust release. Feedback and contributions are highly welcome during this phase.


## Features

- **OGC API Processes** - Standardized geospatial processing endpoints
- **Asynchronous Processing** - Celery workers for background task execution
- **Multiple Model Types**:
    - Tree Models - Street trees from cadastral data with elevation
    - City Models - Buildings from CityGML (LoD1/LoD2)
    - Terrain Models - Digital Ground Models (DGM) from GeoTIFF
- **In-Memory Processing** - GeoTIFF files and CityGML city model XML files are processed directly from URLs
- **Docker Ready** - Container images published to GitHub Container Registry

## Quick Start

### Using Docker (Recommended for Production)

```bash
# Pull the latest image
docker pull ghcr.io/lgv-bim-leitstelle/bimfabrikhh_api:latest

# Run the container
docker run -d -p 8083:8083 -v ./output:/app/output ghcr.io/lgv-bim-leitstelle/bimfabrikhh_api:latest
```

### Local Development

**Prerequisites:**

- Python 3.11+
- Poetry (recommended) or pip
- Access to [BIMFabrikHH_core](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_core)
- Access to [ifcfactory](https://github.com/LGV-BIM-Leitstelle/ifcfactory) or install via PyPI

**Installation:**

```bash
# Clone repository
git clone https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_api.git
cd BIMFabrikHH_api

# Install dependencies
poetry install

# Copy environment template
cp env.example .env

# Start the application
python main.py
```

## API Documentation

Once running, access the interactive API documentation:

- **OGC API Processes**: http://localhost:8083/ogc/docs
- **Data API**: http://localhost:8083/data/docs
- **Main Landing Page**: http://localhost:8083/

## Architecture

### System Components

```
┌─────────────┐      ┌─────────────┐
│   FastAPI   │      │   Celery    │
│  (Web API)  │ ───> │   Worker    │
└─────────────┘      └─────────────┘
       │                    │
       └────────┬───────────┘
                ▼
         ┌─────────────┐
         │   Output    │
         │   (IFC)     │
         └─────────────┘
```

### Processing Pipeline

1. **API Request** - FastAPI receives OGC process execution request
2. **Task Queue** - Job submitted to Celery
3. **Background Processing** - Celery worker processes model generation
4. **Data Fetching** - Fetches Hamburg Open Data (GeoJSON, CityGML, GeoTIFF)
5. **In-Memory Processing** - GeoTIFF downloaded and processed in RAM
6. **IFC Generation** - Creates IFC file using BIMFabrikHH_core
7. **Result** - IFC file saved and download URL returned

## Supported Models

### 1. Tree Models

Generates IFC models of street trees from Hamburg's tree cadastre.

**Features:**

- Tree positions from OGC API
- Elevation data from DGM (in-memory)
- Tree species and height attributes
- Custom property sets

**Example Request:**

```bash
POST /ogc/processes/generate-tree-model/execution
{
  "bbox": {
    "min_x": 9.9756,
    "min_y": 53.5522,
    "max_x": 9.9789,
    "max_y": 53.5536
  }
}
```

### 2. City Models

Generates IFC models of buildings from CityGML data.

**Features:**

- LoD1 and LoD2 support
- Building geometries and attributes
- Automatic tile fetching
- Color-coded representations

### 3. Terrain Models

Generates IFC terrain models from digital ground model (DGM) data.

**Features:**

- GeoTIFF processing (in-memory from URLs)
- Adaptive mesh sampling
- Point importance filtering
- Optimized triangulation

## Deployment

### Production Deployment with Docker

**Pull and run:**

```bash
# Pull latest image
docker pull ghcr.io/lgv-bim-leitstelle/bimfabrikhh_api:latest

# Run container
docker run -d \
  --name bimfabrikhh-api \
  -p 8083:8083 \
  -v /path/to/output:/app/output \
  --restart unless-stopped \
  ghcr.io/lgv-bim-leitstelle/bimfabrikhh_api:latest
```

**Check status:**

```bash
# View logs
docker logs -f bimfabrikhh-api

# Check container status
docker ps

# Stop container
docker stop bimfabrikhh-api

# Start container
docker start bimfabrikhh-api
```

**Run container with redis backend and broker via podman**
```bash
# Set up pod
podman pod create --name bimfabrikhh-pod -p 6379:6379 -p 8083:8083
podman run -d --pod bimfabrikhh-pod --name redis-backend redis:7
podman run -d \
  --pod bimfabrikhh-pod \
  --name bimfabrikhh-api \
  -v /path/to/output:/app/output \
  --restart unless-stopped \
  --env-file .env \
  ghcr.io/lgv-bim-leitstelle/bimfabrikhh_api:latest \
  --db redis

# View logs
podman logs -f bimfabrikhh-api
podman logs -f redis-backend

# stop the pod
podman pod stop bimfabrikhh-pod
```

### Configuration

Settings are configured via environment variables. In Docker, these are baked into the image from `env.example`.

**Key Settings:**

| Variable             | Description                | Default                                          |
|----------------------|----------------------------|--------------------------------------------------|
| `BASE_URL`           | Public API URL             | `http://localhost:8083`                          |
| `API_HOST`           | Bind address               | `0.0.0.0`                                        |
| `API_PORT`           | Port number                | `8083`                                           |
| `OUTPUT_FOLDER_PATH` | IFC output directory       | `output` (or `/app/output` in Docker)            |
| `DATA_BASE_URL`      | Hamburg Open Data base URL | `https://daten-hamburg.de/BIM/daten_bimfabrikhh` |

**Result Backend:**

The API uses SQLite as the default Celery result backend (no Redis required). Database files are stored in `/app/database` inside the container.

See `env.example` for all available settings.

## Development

### Project Structure

```
BIMFabrikHH_api/
├── src/
│   ├── api/
│   │   ├── data_api/          # OGC Features endpoints
│   │   ├── ogc_api/            # OGC Processes endpoints
│   │   │   ├── processes/      # Process definitions
│   │   │   ├── services/       # Celery tasks
│   │   │   └── utils/          # Utilities
│   │   └── web_app.py          # Main FastAPI app
│   └── database/               # SQLite backend
├── main.py                     # Application entry point
├── pyproject.toml              # Dependencies
├── Dockerfile                  # Container definition
└── env.example                 # Configuration template
```

### Running Locally

```bash
# Install dependencies
poetry install

# Start API
python main.py

# Or run Celery worker separately for debugging
celery -A src.api.ogc_api.services.generate_bim_modells worker --loglevel=info
```

### Testing

```bash
# Run tests (when available)
poetry run pytest

# Check code formatting
poetry run black src/

# Type checking
poetry run mypy src/
```

## License

This project (`BIMFabrikHH_api`) is licensed under the **MIT License**.

**Dependencies:**
- **[BIMFabrikHH_core](https://github.com/LGV-BIM-Leitstelle/BIMFabrikHH_core)**: LGPL-3.0 License
- **[ifcfactory](https://github.com/LGV-BIM-Leitstelle/ifcfactory)**: LGPL-3.0 License

**What this means for you:**
- **Using the API service** (via REST endpoints): No license restrictions on your code - use any license you want
- **Using pre-built Docker images**: No license restrictions on your applications
- **Modifying the API code**: MIT License applies
- **Modifying BIMFabrikHH_core or ifcfactory**: LGPL-3.0 applies to those modifications

## Contact

**BIM-Leitstelle Hamburg**  
Landesbetrieb Geoinformation und Vermessung  
Ahmed Salem <ahmed.salem@gv.hamburg.de>
