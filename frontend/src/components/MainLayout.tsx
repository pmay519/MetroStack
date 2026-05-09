import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Upload,
  Crosshair,
  TrendingUp,
  Ruler,
  Layers,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { clsx } from 'clsx'

import ProjectSidebar from './ProjectSidebar'
import UploadPanel from './UploadPanel'
import AlignmentPanel from './AlignmentPanel'
import DeviationPanel from './DeviationPanel'
import GDTPanel from './GDTPanel'
import WallThicknessPanel from './WallThicknessPanel'
import Viewport3D from './Viewport3D'

type PanelType = 'files' | 'alignment' | 'deviation' | 'gdt' | 'wall-thickness' | null

const PANELS = [
  { id: 'files' as const, label: 'Files', icon: Upload },
  { id: 'alignment' as const, label: 'Alignment', icon: Crosshair },
  { id: 'deviation' as const, label: 'Deviation', icon: TrendingUp },
  { id: 'gdt' as const, label: 'GD&T', icon: Ruler },
  { id: 'wall-thickness' as const, label: 'Thickness', icon: Layers },
]

export default function MainLayout() {
  const { currentProject, activePanel, setActivePanel, sidebarOpen, setSidebarOpen } =
    useAppStore()
  const [controlPanelOpen, setControlPanelOpen] = useState(true)

  return (
    <div className="flex h-screen bg-industrial-950 text-industrial-100 overflow-hidden">
      {/* Project Sidebar */}
      <AnimatePresence mode="wait">
        {sidebarOpen && (
          <motion.div
            initial={{ x: -320 }}
            animate={{ x: 0 }}
            exit={{ x: -320 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="relative z-20"
          >
            <ProjectSidebar />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sidebar Toggle */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute top-4 left-4 z-30 p-2 bg-industrial-800 hover:bg-industrial-700
                 border border-industrial-700 rounded text-neon-cyan transition-all
                 hover:shadow-neon-sm"
      >
        {sidebarOpen ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
      </button>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header projectName={currentProject?.name} />

        {/* Viewport + Control Panel */}
        <div className="flex-1 flex overflow-hidden">
          {/* 3D Viewport */}
          <div className="flex-1 relative">
            {currentProject ? (
              <Viewport3D projectId={currentProject.id} />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-industrial-500 font-mono text-sm">
                  <div className="text-neon-cyan text-6xl mb-4">⬡</div>
                  SELECT OR CREATE A PROJECT
                  <br />
                  TO BEGIN ANALYSIS
                </div>
              </div>
            )}
          </div>

          {/* Control Panel */}
          <AnimatePresence mode="wait">
            {controlPanelOpen && currentProject && (
              <motion.div
                initial={{ x: 400 }}
                animate={{ x: 0 }}
                exit={{ x: 400 }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                className="w-96 bg-industrial-900 border-l border-industrial-700 flex flex-col"
              >
                {/* Panel Tabs */}
                <div className="flex border-b border-industrial-700 bg-industrial-850">
                  {PANELS.map((panel) => (
                    <button
                      key={panel.id}
                      onClick={() => setActivePanel(panel.id)}
                      className={clsx(
                        'flex-1 px-3 py-3 text-xs font-mono transition-all border-b-2',
                        activePanel === panel.id
                          ? 'border-neon-cyan text-neon-cyan bg-industrial-900'
                          : 'border-transparent text-industrial-400 hover:text-industrial-200 hover:bg-industrial-800'
                      )}
                    >
                      <div className="flex flex-col items-center gap-1">
                        <panel.icon size={16} />
                        <span>{panel.label}</span>
                      </div>
                    </button>
                  ))}
                </div>

                {/* Panel Content */}
                <div className="flex-1 overflow-hidden">
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={activePanel}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.2 }}
                      className="h-full"
                    >
                      {activePanel === 'files' && <UploadPanel />}
                      {activePanel === 'alignment' && <AlignmentPanel />}
                      {activePanel === 'deviation' && <DeviationPanel />}
                      {activePanel === 'gdt' && <GDTPanel />}
                      {activePanel === 'wall-thickness' && <WallThicknessPanel />}
                    </motion.div>
                  </AnimatePresence>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Control Panel Toggle */}
          {currentProject && (
            <button
              onClick={() => setControlPanelOpen(!controlPanelOpen)}
              className="absolute top-4 right-4 z-10 p-2 bg-industrial-800 hover:bg-industrial-700
                       border border-industrial-700 rounded text-neon-cyan transition-all
                       hover:shadow-neon-sm"
            >
              {controlPanelOpen ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Header ────────────────────────────────────────────────────────────────────

function Header({ projectName }: { projectName?: string }) {
  return (
    <header className="h-16 bg-industrial-900 border-b border-industrial-700 flex items-center px-6">
      <div className="flex items-center gap-4 flex-1">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-neon-cyan to-neon-blue rounded flex items-center justify-center">
            <span className="text-industrial-950 font-display font-bold text-lg">M</span>
          </div>
          <div>
            <h1 className="font-display text-xl text-neon-cyan tracking-wider">METROSTACK</h1>
            <div className="text-xs text-industrial-500 font-mono">
              DIMENSIONAL ANALYSIS PLATFORM
            </div>
          </div>
        </div>

        {/* Current Project */}
        {projectName && (
          <div className="ml-8 pl-8 border-l border-industrial-700">
            <div className="text-xs text-industrial-500 font-mono">ACTIVE PROJECT</div>
            <div className="font-mono text-sm text-industrial-100">{projectName}</div>
          </div>
        )}
      </div>

      {/* Status Indicators */}
      <div className="flex items-center gap-4">
        <StatusIndicator label="BACKEND" status="online" />
        <StatusIndicator label="3D ENGINE" status="online" />
      </div>
    </header>
  )
}

// ── Status Indicator ──────────────────────────────────────────────────────────

function StatusIndicator({ label, status }: { label: string; status: 'online' | 'offline' }) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <div
          className={clsx(
            'w-2 h-2 rounded-full',
            status === 'online' ? 'bg-neon-green' : 'bg-neon-red'
          )}
        />
        {status === 'online' && (
          <div className="absolute inset-0 w-2 h-2 rounded-full bg-neon-green animate-pulse-glow" />
        )}
      </div>
      <span className="text-xs font-mono text-industrial-400">{label}</span>
    </div>
  )
}
