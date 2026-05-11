import { useMemo, useEffect } from 'react'
import { Canvas, useLoader, useThree } from '@react-three/fiber'
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
      <div className="absolute inset-0 pointer-events-none z-10">
        <div className="w-full h-0.5 bg-gradient-to-r from-transparent via-neon-cyan/20 to-transparent animate-scan-line" />
      </div>

      <Canvas>
        <PerspectiveCamera makeDefault position={[300, 300, 300]} fov={50} />
        <OrbitControls enableDamping dampingFactor={0.05} rotateSpeed={0.5} zoomSpeed={0.8} panSpeed={0.5} />
        <ambientLight intensity={0.4} />
        <directionalLight position={[10, 10, 5]} intensity={0.8} castShadow />
        <directionalLight position={[-10, -10, -5]} intensity={0.3} />
        <pointLight position={[0, 50, 0]} intensity={0.5} color="#00d9ff" />
        <Environment preset="warehouse" />
        <Grid args={[500, 500]} cellSize={10} cellThickness={0.5} cellColor="#486581" sectionSize={50} sectionThickness={1} sectionColor="#829ab1" fadeDistance={400} fadeStrength={1} infiniteGrid />
        <axesHelper args={[100]} />
        
        <SceneContent projectId={projectId} />
        <MemoryManager />
      </Canvas>

      <ViewportHUD />
    </div>
  )
}

function MemoryManager() {
  const { scene } = useThree()
  const { lastDeletedFile, setLastDeletedFile } = useAppStore()

  useEffect(() => {
    if (lastDeletedFile) {
      const { id } = lastDeletedFile
      scene.traverse((object) => {
        if ((object instanceof THREE.Mesh || object instanceof THREE.Points) && object.userData.projectId === id) {
          object.geometry.dispose()
          if (Array.isArray(object.material)) {
            object.material.forEach(m => m.dispose())
          } else {
            object.material.dispose()
          }
          scene.remove(object)
        }
      })
      setLastDeletedFile(null)
    }
  }, [lastDeletedFile, scene, setLastDeletedFile])

  return null
}

function SceneContent({ projectId }: { projectId: string }) {
  const { showCAD, showScan, showDeviation, showWallThickness } = useAppStore()

  const { data: cadInfo } = useQuery({ queryKey: ['cad-info', projectId], queryFn: () => uploadAPI.getCADInfo(projectId), enabled: showCAD })
  const { data: scanInfo } = useQuery({ queryKey: ['scan-info', projectId], queryFn: () => uploadAPI.getScanInfo(projectId), enabled: showScan && !showDeviation })
  const { data: deviationData } = useQuery({ queryKey: ['deviation-results', projectId], queryFn: () => analysisAPI.getDeviationResults(projectId, 500_000), enabled: showDeviation })
  const { data: wallThicknessData } = useQuery({ queryKey: ['wall-thickness-results', projectId], queryFn: () => analysisAPI.getWallThicknessResults(projectId, 50_000), enabled: showWallThickness })

  return (
    <group>
      {showCAD && cadInfo && <CADMesh projectId={projectId} />}
      {showScan && !showDeviation && scanInfo && <ScanPointCloud projectId={projectId} count={scanInfo.point_count ?? 10000} bbox={{ min: [scanInfo.bbox_min_x ?? 0, scanInfo.bbox_min_y ?? 0, scanInfo.bbox_min_z ?? 0], max: [scanInfo.bbox_max_x ?? 100, scanInfo.bbox_max_y ?? 100, scanInfo.bbox_max_z ?? 100] }} />}
      {showDeviation && deviationData && <DeviationPointCloud projectId={projectId} x={deviationData.x} y={deviationData.y} z={deviationData.z} deviations={deviationData.deviation_mm} scaleMin={deviationData.stats.scale_min_mm} scaleMax={deviationData.stats.scale_max_mm} />}
      {showWallThickness && wallThicknessData && <WallThicknessPointCloud projectId={projectId} x={wallThicknessData.x} y={wallThicknessData.y} z={wallThicknessData.z} thickness={wallThicknessData.thickness_mm} minThickness={wallThicknessData.stats.min_mm} maxThickness={wallThicknessData.stats.max_mm} />}
    </group>
  )
}

function CADMesh({ projectId }: { projectId: string }) {
  const geometry = useLoader(STLLoader, `/api/projects/${projectId}/cad/file`)
  return (
    <mesh userData={{ projectId }}>
      <primitive object={geometry} attach="geometry" />
      <meshStandardMaterial color="#486581" transparent opacity={0.8} emissive="#00d9ff" emissiveIntensity={0.1} />
    </mesh>
  )
}

function ScanPointCloud({ projectId, count, bbox }: any) {
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
    <points userData={{ projectId }}>
      <bufferGeometry><bufferAttribute attach="attributes-position" count={points.length / 3} array={points} itemSize={3} /></bufferGeometry>
      <pointsMaterial size={0.5} color="#9fb3c8" sizeAttenuation />
    </points>
  )
}

function DeviationPointCloud({ projectId, x, y, z, deviations, scaleMin, scaleMax }: any) {
  const geometry = useMemo(() => {
    const count = x.length
    const positions = new Float32Array(count * 3); const colors = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      positions[i * 3] = x[i]; positions[i * 3 + 1] = y[i]; positions[i * 3 + 2] = z[i]
      const color = deviationToColor(deviations[i], scaleMin, scaleMax)
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b
    }
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return geom
  }, [x, y, z, deviations, scaleMin, scaleMax])
  return <points geometry={geometry} userData={{ projectId }}><pointsMaterial size={0.8} vertexColors sizeAttenuation /></points>
}

function WallThicknessPointCloud({ projectId, x, y, z, thickness, minThickness, maxThickness }: any) {
  const geometry = useMemo(() => {
    const count = x.length
    const positions = new Float32Array(count * 3); const colors = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      positions[i * 3] = x[i]; positions[i * 3 + 1] = y[i]; positions[i * 3 + 2] = z[i]
      const color = thicknessToColor(thickness[i], minThickness, maxThickness)
      colors[i * 3] = color.r; colors[i * 3 + 1] = color.g; colors[i * 3 + 2] = color.b
    }
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    return geom
  }, [x, y, z, thickness, minThickness, maxThickness])
  return <points geometry={geometry} userData={{ projectId }}><pointsMaterial size={1.2} vertexColors sizeAttenuation /></points>
}

function ViewportHUD() {
  const { showCAD, showScan, showDeviation, showWallThickness } = useAppStore()
  return (
    <div className="absolute top-4 left-4 pointer-events-none">
      <div className="flex flex-col gap-2 font-mono text-xs text-neon-cyan/60">
        {showCAD && <div className="flex items-center gap-2"><div className="w-2 h-2 bg-industrial-500 border border-neon-cyan/50" /><span>CAD REFERENCE</span></div>}
        {showScan && !showDeviation && <div className="flex items-center gap-2"><div className="w-2 h-2 bg-industrial-300" /><span>SCAN CLOUD</span></div>}
        {showDeviation && <div className="flex items-center gap-2"><div className="w-2 h-2 bg-gradient-to-r from-blue-500 via-white to-red-500" /><span>DEVIATION HEATMAP</span></div>}
        {showWallThickness && <div className="flex items-center gap-2"><div className="w-2 h-2 bg-gradient-to-r from-purple-600 via-green-500 to-yellow-400" /><span>WALL THICKNESS</span></div>}
      </div>
    </div>
  )
}
