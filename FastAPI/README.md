# MetroStack Backend

PostgreSQL-powered metrology platform for dimensional analysis, GD&T evaluation, and wall thickness measurement. Built with FastAPI, Open3D, trimesh, and PostGIS.

---

## Features

- **File Upload**: STL, OBJ, PLY, STEP (CAD) + E57, LAS, PCD, XYZ (scans)
- **Alignment**: ICP, Fast Global Registration, datum-constrained registration
- **Deviation Analysis**: Signed point-to-CAD distance with heatmap colour scaling
- **GD&T**: Flatness, cylindricity, circularity, position, parallelism, perpendicularity, straightness, profile, runout
- **Wall Thickness**: Ray-cast thickness mapping across watertight meshes
- **PostgreSQL Storage**: Millions of points stored efficiently via bulk COPY
- **Async Everything**: FastAPI + SQLAlchemy 2.0 async, background task processing

---

## Quick Start (Docker)

### Prerequisites

- Docker & Docker Compose
- At least 8 GB RAM (for large point clouds)

### 1. Clone & Configure

```bash
cd metrostack/backend
cp .env.example .env
# Edit .env if needed (defaults work for Docker setup)
```

### 2. Start Services

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** (port 5432) with PostGIS + pgpointcloud
- **Redis** (port 6379) for task queue
- **FastAPI** (port 8000) with hot-reload
- **pgAdmin** (port 5050) — optional DB admin UI

### 3. Run Migrations

```bash
docker-compose exec api alembic upgrade head
```

### 4. Test

```bash
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","environment":"development"}
```

API docs: **http://localhost:8000/docs**

---

## Local Development (Without Docker)

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with PostGIS + pgpointcloud extensions
- Redis (optional — for background tasks)

### 1. Install PostgreSQL Extensions

```sql
CREATE DATABASE metrostack;
\c metrostack;
CREATE EXTENSION postgis;
CREATE EXTENSION pointcloud;
CREATE EXTENSION pointcloud_postgis;
```

### 2. Install Python Dependencies

```bash
cd metrostack/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit DATABASE_URL to point to your local PostgreSQL
```

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Start Server

```bash
uvicorn app.main:app --reload
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

---

## API Workflow

### 1. Create Project

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Part","part_number":"PN-12345"}'
```

Returns: `{"id": "uuid-here", ...}`

### 2. Upload CAD & Scan

```bash
# CAD mesh
curl -X POST http://localhost:8000/api/projects/{project_id}/upload-cad \
  -F "file=@part.stl"

# Scan cloud
curl -X POST http://localhost:8000/api/projects/{project_id}/upload-scan \
  -F "file=@scan.ply"
```

Files process in background. Poll `/api/projects/{id}/cad` and `/scan` for `is_processed: true`.

### 3. Run Alignment

```bash
curl -X POST http://localhost:8000/api/projects/{project_id}/align \
  -H "Content-Type: application/json" \
  -d '{"method":"icp"}'
```

Returns: `{"job_id": "...", "status": "queued"}`

Poll: `GET /api/projects/{project_id}/jobs/{job_id}` until `status: "complete"`.

### 4. Run Deviation Analysis

```bash
curl -X POST http://localhost:8000/api/projects/{project_id}/analyze/deviation \
  -H "Content-Type: application/json" \
  -d '{}'
```

Get results:
```bash
curl http://localhost:8000/api/projects/{project_id}/results/deviation
```

Returns columnar JSON: `{x: [...], y: [...], z: [...], deviation_mm: [...], stats: {...}}`

### 5. Define & Run GD&T Features

```bash
# Create flatness feature
curl -X POST http://localhost:8000/api/projects/{project_id}/gdt/features \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Datum A",
    "feature_type": "flatness",
    "tolerance_upper_mm": 0.05,
    "roi_min_x": -50, "roi_max_x": 50,
    "roi_min_y": -50, "roi_max_y": 50,
    "roi_min_z": 0, "roi_max_z": 5
  }'

# Run GD&T analysis
curl -X POST http://localhost:8000/api/projects/{project_id}/analyze/gdt

# Get results
curl http://localhost:8000/api/projects/{project_id}/results/gdt
```

### 6. Wall Thickness

```bash
curl -X POST http://localhost:8000/api/projects/{project_id}/analyze/wall-thickness \
  -H "Content-Type: application/json" \
  -d '{"sample_count": 10000}'

# Results
curl http://localhost:8000/api/projects/{project_id}/results/wall-thickness
```

---

## Project Structure

```
backend/
├── app/
│   ├── api/routes/          # FastAPI route handlers
│   │   ├── projects.py      # CRUD for projects
│   │   ├── upload.py        # File upload endpoints
│   │   └── analysis.py      # Alignment, deviation, GD&T, wall thickness
│   ├── core/
│   │   └── config.py        # Pydantic settings
│   ├── db/
│   │   └── session.py       # Async SQLAlchemy engine
│   ├── models/
│   │   └── models.py        # ORM models (Project, CADModel, etc.)
│   ├── schemas/
│   │   └── schemas.py       # Pydantic request/response schemas
│   ├── services/            # Core metrology compute modules
│   │   ├── ingest.py        # File loading (trimesh, Open3D)
│   │   ├── alignment.py     # ICP, FGR, datum-constrained registration
│   │   ├── deviation.py     # Signed point-to-surface deviation
│   │   ├── gdt.py           # GD&T characteristic calculations
│   │   └── wall_thickness.py # Ray-casting thickness
│   └── main.py              # FastAPI app factory
├── migrations/              # Alembic database migrations
├── docker-compose.yml       # Docker services
├── Dockerfile               # FastAPI container
├── requirements.txt         # Python dependencies
└── README.md                # This file
```

---

## Key Technologies

| Layer          | Stack                                           |
|----------------|-------------------------------------------------|
| **Framework**  | FastAPI 0.111, Uvicorn, Pydantic v2             |
| **Database**   | PostgreSQL 15, PostGIS 3.4, pgpointcloud, asyncpg |
| **ORM**        | SQLAlchemy 2.0 (async), Alembic migrations      |
| **3D Compute** | Open3D 0.18, trimesh 4.3, NumPy, SciPy          |
| **File I/O**   | laspy (LAS/LAZ), pye57 (E57), aiofiles          |
| **Async**      | asyncio, BackgroundTasks (future: Celery)       |

---

## Performance Notes

- **Deviation bulk insert**: Uses asyncpg `copy_records_to_table` — handles 5M points in ~30 seconds.
- **ICP alignment**: Point-to-Plane typically converges in 50–200 iterations. Voxel-downsample large scans to <1M points for interactive speed.
- **Wall thickness**: Ray-casting is single-threaded in trimesh. 20k samples on a 1M-triangle mesh takes ~15 seconds.
- **GD&T fitting**: Minimum Zone algorithms use scipy optimisation — expect 1–5 seconds per feature depending on point density.

---

## Troubleshooting

### "Module 'open3d' has no attribute 'pipelines'"

Upgrade Open3D: `pip install --upgrade open3d>=0.18`

### "STEP files not loading"

pythonocc-core required:
```bash
conda install -c conda-forge pythonocc-core
```

### Migrations fail with "relation already exists"

Reset DB:
```bash
docker-compose down -v
docker-compose up -d
docker-compose exec api alembic upgrade head
```

### Point cloud has no normals after loading

File format doesn't include normals. Open3D auto-estimates them during `load_point_cloud()` via KDTree search.

---

## Next Steps

- [ ] Celery worker for true distributed background jobs
- [ ] PDF/Excel report generation (reportlab, openpyxl)
- [ ] Cross-section analysis (slice plane → 2D profile extraction)
- [ ] Multipart CAD assembly support (STEP import with hierarchy)
- [ ] User authentication & multi-tenancy
- [ ] Frontend integration (React + Three.js)

---

## License

MIT — Commercial metrology use permitted.
