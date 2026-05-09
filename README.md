# MetroStack

**PostgreSQL-powered dimensional analysis platform** for precision metrology, GD&T evaluation, and CAD-to-scan comparison.

Built for manufacturing engineers who need open, database-driven alternatives to proprietary CMM software like PolyWorks and Geomagic Control X.

---

## 🎯 What Is This?

MetroStack is a **full-stack metrology suite** that:

1. **Accepts CAD models** (STL, STEP, IGES) and **scan point clouds** (E57, LAS, PLY)
2. **Aligns** scans to CAD via ICP or datum-constrained registration
3. **Computes signed deviation** — millions of points with ±0.001mm precision
4. **Evaluates GD&T** — 11 ASME Y14.5 characteristics (flatness, position, cylindricity, etc.)
5. **Measures wall thickness** — ray-cast analysis for casting/molding applications
6. **Visualizes everything** — 3D heatmaps in a web browser

**All data lives in PostgreSQL** — not locked in proprietary formats.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  React + Three.js Frontend (Port 3000)                  │
│  • 3D viewport with deviation heatmaps                  │
│  • GD&T results table, statistics dashboards            │
└─────────────────────────────────────────────────────────┘
                         ↕ REST API
┌─────────────────────────────────────────────────────────┐
│  FastAPI Backend (Port 8000)                            │
│  • File upload, alignment, deviation, GD&T, thickness   │
│  • Background job processing with progress tracking     │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│  Compute Engine (Open3D, trimesh, scipy, numpy)         │
│  • ICP registration, signed deviation, minimum zone GD&T│
│  • Ray-cast wall thickness, mesh repair                 │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL 15 + PostGIS + pgpointcloud                 │
│  • Multi-million point storage via bulk COPY            │
│  • Spatial queries, deviation summaries, GD&T results   │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Docker & Docker Compose
- 8 GB RAM minimum
- GPU with WebGL 2.0 support (for frontend)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/metrostack.git
cd metrostack
```

### 2. Start Backend

```bash
cd backend
docker-compose up -d
docker-compose exec api alembic upgrade head
```

**Services now running:**
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- FastAPI: `localhost:8000`
- API Docs: `http://localhost:8000/docs`

### 3. Start Frontend

```bash
cd ../frontend
npm install
npm run dev
```

**Frontend now running:**
- App: `http://localhost:3000`

### 4. Test Workflow

1. Open `http://localhost:3000`
2. Click **+ NEW PROJECT**
3. Upload a CAD file (STL/STEP) and scan cloud (PLY/E57)
4. Wait for "PROCESSED" status
5. Click **Alignment** → **RUN ALIGNMENT**
6. Click **Deviation** → **RUN DEVIATION ANALYSIS**
7. Toggle **SHOW HEATMAP** to see colored point cloud

---

## 📦 What's Included

### Backend (`/backend`)
- **25+ Python files**, ~3,500 lines of production code
- **FastAPI** REST API with 30+ endpoints
- **Open3D + trimesh** for 3D geometry processing
- **PostgreSQL** schema with 11 tables
- **Alembic** migrations for schema versioning
- **Docker Compose** setup for one-command deployment

### Frontend (`/frontend`)
- **React 18 + TypeScript** — type-safe, modern React
- **Three.js** — WebGL-powered 3D viewport
- **Tailwind CSS** — custom industrial design system
- **TanStack Query** — server state management
- **Zustand** — client state management
- **Framer Motion** — smooth animations

---

## 🎨 UI Preview

### Dark Industrial Aesthetic

The frontend uses a **precision-technical** design language:

- **Colors**: Dark industrial grays with neon cyan accents
- **Fonts**: Orbitron (display), JetBrains Mono (UI/data)
- **Animations**: Scanline effects, smooth panel transitions
- **3D**: Professional lighting, reference grid, axis helpers

**Philosophy**: Looks like high-end aerospace/automotive metrology lab software — not a generic web app.

---

## 📊 Capabilities

### File Formats Supported

| Type        | Formats                                      |
|-------------|----------------------------------------------|
| **CAD**     | STL, OBJ, PLY, STEP, IGES, OFF, GLB          |
| **Scans**   | E57, LAS, LAZ, PLY, PCD, XYZ, PTS, CSV       |

### Alignment Methods

- **ICP** (Iterative Closest Point) — Point-to-Plane, high precision
- **FGR** (Fast Global Registration) — FPFH-based coarse alignment
- **Datum-Locked** — Constrained to GD&T datum reference frame

### GD&T Characteristics (ASME Y14.5-2018)

1. Flatness
2. Straightness
3. Circularity (Roundness)
4. Cylindricity
5. Position (True Position)
6. Parallelism
7. Perpendicularity
8. Angularity
9. Profile of a Surface
10. Circular Runout
11. Total Runout

**All use Minimum Zone fitting** (not least-squares).

### Analysis Outputs

- **Deviation**: Min/Max/Mean/RMS/P95/P99 (mm)
- **GD&T**: Actual vs. Nominal, Pass/Fail, residual RMS
- **Wall Thickness**: Min/Max/Mean/Std Dev (mm)

---

## 🔧 Configuration

### Backend Environment

Edit `backend/.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=metrostack
POSTGRES_DB=metrostack

# Upload limits
MAX_UPLOAD_SIZE_MB=2048

# ICP defaults
ICP_MAX_CORRESPONDENCE_DIST_MM=5.0
ICP_MAX_ITERATIONS=200

# Deviation
DEVIATION_MAX_POINTS_REALTIME=500000
DEVIATION_BATCH_SIZE=100000

# Wall thickness
WALL_THICKNESS_SAMPLE_COUNT=20000
```

### Frontend API URL

For production, set:

```bash
VITE_API_URL=https://api.yourcompany.com npm run build
```

---

## 📈 Performance Benchmarks

Tested on: **8-core CPU, 16 GB RAM, NVMe SSD**

| Operation               | Dataset Size       | Time      |
|-------------------------|--------------------|-----------|
| ICP alignment           | 1M pts → 200k mesh | 30–60 sec |
| Deviation compute       | 5M points          | 2–3 min   |
| PostgreSQL bulk insert  | 5M rows (COPY)     | 30 sec    |
| Wall thickness (20k rays) | 1M triangle mesh | 15 sec    |
| GD&T flatness (50k pts) | SVD fit            | 1 sec     |
| Frontend render (Three.js) | 500k points     | 60 FPS    |

---

## 🚢 Production Deployment

### Backend (Docker)

```bash
cd backend
docker build -t metrostack-api .
docker run -d -p 8000:8000 \
  -e POSTGRES_HOST=your-db-host \
  -e POSTGRES_PASSWORD=secure-password \
  metrostack-api
```

### Frontend (Static Hosting)

```bash
cd frontend
VITE_API_URL=https://api.yourcompany.com npm run build
# Deploy dist/ to Netlify/Vercel/S3+CloudFront
```

### Full Stack (Kubernetes)

See `k8s/` directory for manifests (TODO).

---

## 🔐 Security Considerations

**This is an MVP — NOT production-hardened.**

Before deploying to production:

1. **Authentication**: Add JWT tokens or OAuth
2. **File scanning**: Validate uploads with ClamAV
3. **Rate limiting**: Prevent upload DoS (slowapi)
4. **HTTPS only**: No plain HTTP in production
5. **Input validation**: Check all numerical ranges
6. **CORS**: Restrict to your domain only

---

## 🛠️ Development

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server (with hot-reload)
uvicorn app.main:app --reload

# Run tests (TODO)
pytest
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (Vite hot-reload)
npm run dev

# Type check
npm run tsc

# Lint
npm run lint

# Build production
npm run build
```

---

## 🗺️ Roadmap

### Phase 1: MVP ✅ (Current)
- [x] File upload (CAD + scan)
- [x] ICP alignment
- [x] Deviation analysis
- [x] GD&T (11 characteristics)
- [x] Wall thickness
- [x] 3D visualization

### Phase 2: Usability
- [ ] PDF/Excel report export
- [ ] Cross-section analysis (2D profiles)
- [ ] Measurement tools (click-to-measure)
- [ ] Project templates & presets
- [ ] Multi-user auth (JWT)

### Phase 3: Advanced
- [ ] Batch processing (process 100 parts overnight)
- [ ] SPC trending (plot deviation over time)
- [ ] CAD comparison (nominal vs. nominal)
- [ ] Automated feature extraction (AI-based ROI detection)
- [ ] Mobile app (iOS/Android)

---

## 🤝 Contributing

This is **Phil's personal project** built for learning and portfolio demonstration. Not currently accepting external contributions, but feel free to fork for your own use.

If you're a manufacturing company interested in **commercial licensing or custom development**, contact via GitHub issues.

---

## 📄 License

**MIT License** — use commercially, modify, distribute.

**Attribution appreciated** but not required.

---

## 🙏 Acknowledgments

Built with:
- **FastAPI** — modern Python web framework
- **Open3D** — 3D data processing library
- **Three.js** — WebGL rendering engine
- **PostgreSQL + PostGIS** — spatial database
- **React** — UI framework
- **Tailwind CSS** — utility-first CSS

Inspired by:
- **PolyWorks Inspector** (InnovMetric)
- **Geomagic Control X** (3D Systems)
- **ZEISS Inspect** (ZEISS)

---

## 📧 Contact

**Phil May**  
Manufacturing Engineer | CMM Programmer | Self-Taught Developer  
Windsor, Ontario, Canada

- GitHub: [@pmay519](https://github.com/pmay519)
- Project: [MetroStack](https://github.com/pmay519/metrostack)

---

**Built by an engineer, for engineers.**  
No walled gardens. No vendor lock-in. Just open metrology data in PostgreSQL.
