import { useMemo } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera, Grid, Environment } from '@react-three/drei'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader'
import { useQuery } from '@tanstack/react-query'
import { analysisAPI, uploadAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { deviationToColor, thicknessToColor } from '@/lib/colormap'

interface ViewportProps {
  projectId: string
}

export default function Viewport3D({ projectId }: ViewportProps) {
  return (
    <div className="relative w-full h-full bg-industrial-950">
      {/* Scanline effect overlay */}
      <div className="absolute inset-0 pointer-events-none z-10">
        <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-neon-cyan/20 to-transparent animate-scan-line" />
      </div>

      <Canvas>
        <PerspectiveCamera makeDefault position={[300, 300, 300]} fov={50} />
        <OrbitControls
          enableDamping
          dampingFactor={0.05}
          rotateSpeed={0.5}
          zoomSpeed={0.8}
          panSpeed={0.5}
        />

        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 10, 5]} intensity={0.8} castShadow />
        <directionalLight position={[-10, -10, -5]} intensity={0.3} />
        <pointLight position={[0, 50, 0]} intensity={0.5} color="#00d9ff" />

        {/* Environment */}
        <Environment preset="warehouse" />

        {/* Reference grid */}
        <Grid
          args={[500, 500]}
          cellSize={10}
          cellThickness={0.5}
          cellColor="#486581"
          sectionSize={50}
          sectionThickness={1}
          sectionColor="#829ab1"
          fadeDistance={400}
          fadeStrength={1}
          followCamera={false}
          infiniteGrid
        />

        {/* Axis indicator */}
        <axesHelper args={[100]} />

        {/* Scene content */}
        <SceneContent projectId={projectId} />
      </Canvas>

      {/* Viewport HUD */}
      <ViewportHUD />
    </div>
  )
}

// ── Scene Content ─────────────────────────────────────────────────────────────

function SceneContent({ projectId }: { projectId: string }) {
  const { showCAD, showScan, showDeviation, showWallThickness } = useAppStore()

  // Load CAD mesh info
  const { data: cadInfo } = useQuery({
    queryKey: ['cad-info', projectId],
    queryFn: () => uploadAPI.getCADInfo(projectId),
    enabled: showCAD,
  })

  // Load scan cloud info
  const { data: scanInfo } = useQuery({
    queryKey: ['scan-info', projectId],
    queryFn: () => uploadAPI.getScanInfo(projectId),
    enabled: showScan && !showDeviation,
  })

  // Load deviation point cloud
  const { data: deviationData } = useQuery({
    queryKey: ['deviation-results', projectId],
    queryFn: () => analysisAPI.getDeviationResults(projectId, 500_000),
    enabled: showDeviation,
  })

  // Load wall thickness data
  const { data: wallThicknessData } = useQuery({
    queryKey: ['wall-thickness-results', projectId],
    queryFn: () => analysisAPI.getWallThicknessResults(projectId, 50_000),
    enabled: showWallThickness,
  })

  return (
    <group>
      {/* CAD reference mesh */}
      {showCAD && cadInfo && (
        <CADMesh projectId={projectId} />
      )}

      {/* Raw scan point cloud (monochrome) */}
      {showScan && !showDeviation && scanInfo && (
        <ScanPointCloud
          count={scanInfo.point_count ?? 10000}
          bbox={{
            min: [
              scanInfo.bbox_min_x ?? 0,
              scanInfo.bbox_min_y ?? 0,
              scanInfo.bbox_min_z ?? 0,
            ],
            max: [
              scanInfo.bbox_max_x ?? 100,
              scanInfo.bbox_max_y ?? 100,
              scanInfo.bbox_max_z ?? 100,
            ],
          }}
        />
      )}

      {/* Deviation heatmap point cloud */}
      {showDeviation && deviationData && (
        <DeviationPointCloud
          x={deviationData.x}
          y={deviationData.y}
          z={deviationData.z}
          deviations={deviationData.deviation_mm}
          scaleMin={deviationData.stats.scale_min_mm}
          scaleMax={deviationData.stats.scale_max_mm}
        />
      )}

      {/* Wall thickness heatmap */}
      {showWallThickness && wallThicknessData && (
        <WallThicknessPointCloud
          x={wallThicknessData.x}
          y={wallThicknessData.y}
          z={wallThicknessData.z}
          thickness={wallThicknessData.thickness_mm}
          minThickness={wallThicknessData.stats.min_mm}
          maxThickness={wallThicknessData.stats.max_mm}
        />
      )}
    </group>
  )
}

// ── CAD Mesh (STL loader) ─────────────────────────────────────────────────────

function CADMesh({ projectId }: { projectId: string }) {
  const geometry = useLoader(STLLoader, `/api/projects/${projectId}/cad/file`)

  return (
    <mesh>
      <primitive object={geometry} attach="geometry" />
      <meshStandardMaterial
        color="#486581"
        transparent
        opacity={0.8}
        emissive="#00d9ff"
        emissiveIntensity={0.1}
      />
    </mesh>
  )
}

// ── Scan Point Cloud (monochrome) ─────────────────────────────────────────────

interface BBox {
  min: [number, number, number]
  max: [number, number, number]
}

function ScanPointCloud({ count, bbox }: { count: number; bbox: BBox }) {
  const points = useMemo(() => {
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      positions[i * 3] = THREE.MathUtils.lerp(bbox.min[0], bbox.max[0], Math.random())
      positions[i * 3 + 1] = THREE.MathUtils.lerp(bbox.min[1], bbox.max[1], Math.random())
      positions[i * 3 + 2] = THREE.MathUtils.lerp(bbox.min[2], bbox.max[2], Math.random())
    }
    return positions
  }, [count, bbox])

  return (
    <points>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={points.length / 3}
          array={points}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial size={0.5} color="#9fb3c8" sizeAttenuation />
    </points>
  )
}

// ── Deviation Point Cloud (heatmap) ──────────────────────────────────────────

interface DeviationPointCloudProps {
  x: number[]
  y: number[]
  z: number[]
  deviations: number[]
  scaleMin: number
  scaleMax: number
}

function DeviationPointCloud({
  x,
  y,
  z,
  deviations,
  scaleMin,
  scaleMax,
}: DeviationPointCloudProps) {
  const geometry = useMemo(() => {
    const count = x.length
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)

    for (let i = 0; i < count; i++) {
      positions[i * 3] = x[i]
      positions[i * 3 + 1] = y[i]
      positions[i * 3 + 2] = z[i]

      const color = deviationToColor(deviations[i], scaleMin, scaleMax)
      colors[i * 3] = color.r
      colors[i * 3 + 1] = color.g
      colors[i * 3 + 2] = color.b
    }

    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return geom
  }, [x, y, z, deviations, scaleMin, scaleMax])

  return (
    <points geometry={geometry}>
      <pointsMaterial size={0.8} vertexColors sizeAttenuation />
    </points>
  )
}

// ── Wall Thickness Point Cloud (viridis heatmap) ──────────────────────────────

interface WallThicknessPointCloudProps {
  x: number[]
  y: number[]
  z: number[]
  thickness: number[]
  minThickness: number
  maxThickness: number
}

function WallThicknessPointCloud({
  x,
  y,
  z,
  thickness,
  minThickness,
  maxThickness,
}: WallThicknessPointCloudProps) {
  const geometry = useMemo(() => {
    const count = x.length
    const positions = new Float32Array(count * 3)
    const colors = new Float32Array(count * 3)

    for (let i = 0; i < count; i++) {
      positions[i * 3] = x[i]
      positions[i * 3 + 1] = y[i]
      positions[i * 3 + 2] = z[i]

      const color = thicknessToColor(thickness[i], minThickness, maxThickness)
      colors[i * 3] = color.r
      colors[i * 3 + 1] = color.g
      colors[i * 3 + 2] = color.b
    }

    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return geom
  }, [x, y, z, thickness, minThickness, maxThickness])

  return (
    <points geometry={geometry}>
      <pointsMaterial size={1.2} vertexColors sizeAttenuation />
    </points>
  )
}

// ── Viewport HUD ──────────────────────────────────────────────────────────────

function ViewportHUD() {
  const { showCAD, showScan, showDeviation, showWallThickness } = useAppStore()

  return (
    <div className="absolute top-4 left-4 pointer-events-none">
      <div className="flex flex-col gap-2 font-mono text-xs text-neon-cyan/60">
        {showCAD && <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-industrial-500 border border-neon-cyan/50" />
          <span>CAD REFERENCE</span>
        </div>}
        {showScan && !showDeviation && <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-industrial-300" />
          <span>SCAN CLOUD</span>
        </div>}
        {showDeviation && <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-gradient-to-r from-blue-500 via-white to-red-500" />
          <span>DEVIATION HEATMAP</span>
        </div>}
        {showWallThickness && <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-gradient-to-r from-purple-600 via-green-500 to-yellow-400" />
          <span>WALL THICKNESS</span>
        </div>}
      </div>
    </div>
  )
}
