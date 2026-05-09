# MetroStack Frontend

**Precision-industrial 3D metrology interface** built with React, Three.js, and Tailwind CSS.

---

## Features

### 🎯 **3D Visualization**
- **Three.js viewport** with orbit controls, grid, and professional lighting
- **Point cloud rendering** — millions of points with vertex colors
- **Deviation heatmap** — blue (inside) → white (on surface) → red (outside)
- **Wall thickness map** — viridis colormap for sequential data
- **CAD mesh wireframe** — reference geometry overlay

### 📊 **Analysis Panels**
- **File Upload** — drag-and-drop STL, E57, PLY, LAS with live processing status
- **Alignment** — ICP/FGR controls with real-time quality metrics
- **Deviation** — statistics dashboard, color scale control, P95/RMS/range
- **GD&T** — feature definition modal, 11 characteristic types, pass/fail table
- **Wall Thickness** — sample count control, min/max/mean/std stats

### 💎 **UI/UX**
- **Industrial aesthetic** — dark mode with neon cyan accents, technical fonts
- **Responsive panels** — collapsible sidebar/control panel, smooth animations
- **Real-time updates** — job polling, background task progress
- **Type-safe** — full TypeScript coverage with backend schema matching

---

## Quick Start

### Prerequisites
- Node.js 18+
- Running MetroStack backend on `http://localhost:8000`

### 1. Install Dependencies

```bash
cd metrostack/frontend
npm install
```

### 2. Start Dev Server

```bash
npm run dev
```

Frontend runs at **http://localhost:3000** with Vite hot-reload.

### 3. Build for Production

```bash
npm run build
npm run preview  # test production build
```

Output: `dist/` directory ready for static hosting.

---

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── MainLayout.tsx           # App shell with header + panels
│   │   ├── ProjectSidebar.tsx       # Project list + create modal
│   │   ├── Viewport3D.tsx           # Three.js 3D scene ⭐
│   │   ├── UploadPanel.tsx          # CAD + scan file upload
│   │   ├── AlignmentPanel.tsx       # ICP/FGR controls
│   │   ├── DeviationPanel.tsx       # Heatmap stats + scale
│   │   ├── GDTPanel.tsx             # Feature definition + results
│   │   └── WallThicknessPanel.tsx   # Ray-cast thickness
│   ├── lib/
│   │   ├── api.ts                   # Axios client, all endpoints
│   │   ├── store.ts                 # Zustand global state
│   │   └── colormap.ts              # Deviation/thickness color maps
│   ├── types/
│   │   └── api.ts                   # TypeScript types (matches backend)
│   ├── styles/
│   │   └── index.css                # Tailwind + custom CSS
│   ├── App.tsx                      # React Query provider
│   └── main.tsx                     # Entry point
├── public/
│   └── favicon.svg
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js               # Custom industrial palette
```

---

## Tech Stack

| Layer              | Technology                          |
|--------------------|-------------------------------------|
| **Framework**      | React 18, TypeScript 5.3            |
| **3D Graphics**    | Three.js, @react-three/fiber, @react-three/drei |
| **State**          | Zustand (global), TanStack Query (server) |
| **Styling**        | Tailwind CSS, Framer Motion         |
| **Data Fetching**  | Axios, TanStack Query               |
| **Build**          | Vite 5                              |

---

## Configuration

### API Endpoint

Vite proxies `/api` to the backend in development. Edit `vite.config.ts`:

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',  // ← change if backend runs elsewhere
      changeOrigin: true,
    },
  },
}
```

For production, set `VITE_API_URL` environment variable:

```bash
VITE_API_URL=https://api.metrostack.yourcompany.com npm run build
```

Then update `src/lib/api.ts`:

```typescript
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
})
```

### Color Palette

Custom industrial theme in `tailwind.config.js`:

```javascript
colors: {
  industrial: { 50: '#f0f4f8', ..., 950: '#0a1929' },
  neon: {
    cyan: '#00d9ff',
    blue: '#0080ff',
    purple: '#8b5cf6',
    green: '#10b981',
    amber: '#f59e0b',
    red: '#ef4444',
  },
}
```

---

## Development Workflow

### 1. Create Project
- Click **+** in sidebar
- Enter name/part number
- Project appears in list

### 2. Upload Files
- Select project
- Drag CAD file (STL/STEP) to **Files** panel
- Drag scan cloud (E57/PLY/LAS)
- Wait for "PROCESSED" status (green checkmark)

### 3. Align
- Switch to **Alignment** panel
- Choose ICP or FGR
- Click **RUN ALIGNMENT**
- View RMSE + fitness score

### 4. Deviation Analysis
- Switch to **Deviation** panel
- Click **RUN DEVIATION ANALYSIS**
- Toggle **SHOW HEATMAP**
- Adjust color scale bounds

### 5. GD&T
- Switch to **GD&T** panel
- Click **+** to define features
- Select characteristic type (flatness, cylindricity, etc.)
- Set tolerance
- Click **RUN GD&T ANALYSIS**
- View pass/fail table

### 6. Wall Thickness
- Switch to **Thickness** panel
- Set sample count (10k–100k)
- Click **RUN THICKNESS ANALYSIS**
- View min/max/mean stats

---

## Performance Notes

### Large Point Clouds (>1M points)

The backend automatically downsamples to 500k points for deviation results. Frontend renders at 60 FPS with:

```typescript
<pointsMaterial size={0.8} vertexColors sizeAttenuation />
```

For very dense clouds (>2M), Three.js may lag on rotation. Solutions:
1. Increase backend downsample limit
2. Use LOD (Level of Detail) in Three.js
3. Implement point cloud octree culling

### Three.js Memory

Each point cloud creates GPU buffers. If switching between multiple projects:

```typescript
// Dispose geometries when unmounting
useEffect(() => {
  return () => {
    geometry.dispose()
    material.dispose()
  }
}, [geometry, material])
```

### React Query Cache

Default stale time is 30 seconds. Increase for slower networks:

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5 minutes
    },
  },
})
```

---

## Customization

### Add New Analysis Type

1. **Backend**: Add route in `backend/app/api/routes/analysis.py`
2. **Types**: Add to `frontend/src/types/api.ts`
3. **API**: Add method in `frontend/src/lib/api.ts`
4. **Panel**: Create `src/components/NewAnalysisPanel.tsx`
5. **Layout**: Add to `PANELS` array in `MainLayout.tsx`

### Custom Color Schemes

Edit `src/lib/colormap.ts`:

```typescript
export function deviationToColor(dev: number, min: number, max: number) {
  // Your custom colormap logic
}
```

### Change Fonts

Edit `src/styles/index.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=YourFont&display=swap');

body {
  font-family: 'YourFont', monospace;
}
```

---

## Deployment

### Static Hosting (Netlify, Vercel, Cloudflare Pages)

```bash
npm run build
# Deploy dist/ directory
```

**Important**: Configure rewrites for SPA routing:

**Netlify** (`public/_redirects`):
```
/*    /index.html   200
```

**Vercel** (`vercel.json`):
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

### Docker

```dockerfile
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
```

---

## Troubleshooting

### "Cannot connect to backend"

Check Vite proxy in `vite.config.ts` matches backend URL:
```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd frontend && npm run dev
```

### Three.js canvas is blank

Open browser console. Common errors:
- **WebGL not supported** — update GPU drivers
- **CORS error** — backend must allow `http://localhost:3000`
- **Geometry undefined** — data not loaded yet, add loading state

### Point cloud doesn't render

Check in React DevTools → TanStack Query:
- Is `deviation-results` query status `success`?
- Does `data.x.length > 0`?
- Are all arrays same length?

### Tailwind styles not applying

Ensure `index.css` is imported in `main.tsx`:
```typescript
import './styles/index.css'
```

Run Tailwind watch:
```bash
npx tailwindcss -i ./src/styles/index.css -o ./dist/output.css --watch
```

---

## Browser Support

- **Chrome/Edge** 100+ ✅
- **Firefox** 98+ ✅
- **Safari** 15+ ✅ (limited WebGL performance)

**WebGL 2.0 required** — Three.js r128+ needs modern GPU.

---

## Roadmap

- [ ] **Export results** — PDF report generation, CSV downloads
- [ ] **Measurement tools** — click-to-measure distance, angle
- [ ] **Cross-section view** — slice plane tool for 2D profiles
- [ ] **Animation** — rotate/explode views, deviation timeline
- [ ] **Comparison mode** — side-by-side multi-project view
- [ ] **Mobile support** — responsive layout for tablets

---

## License

MIT — matches backend license.
