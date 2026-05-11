import { create } from 'zustand'
import type { Project } from '@/types/api'

interface AppState {
  currentProject: Project | null
  setCurrentProject: (project: Project | null) => void
  closeProject: () => void

  lastDeletedFile: { id: string; type: 'CAD' | 'SCAN' } | null
  setLastDeletedFile: (info: { id: string; type: 'CAD' | 'SCAN' } | null) => void

  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  activePanel: 'files' | 'alignment' | 'deviation' | 'gdt' | 'wall-thickness' | null
  setActivePanel: (panel: 'files' | 'alignment' | 'deviation' | 'gdt' | 'wall-thickness' | null) => void

  showCAD: boolean
  showScan: boolean
  showDeviation: boolean
  showWallThickness: boolean
  setShowCAD: (show: boolean) => void
  setShowScan: (show: boolean) => void
  setShowDeviation: (show: boolean) => void
  setShowWallThickness: (show: boolean) => void

  deviationScaleMin: number
  deviationScaleMax: number
  setDeviationScale: (min: number, max: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),
  closeProject: () => set({ 
    currentProject: null, 
    activePanel: 'files',
    showScan: false,
    showDeviation: false,
    showWallThickness: false,
    lastDeletedFile: null
  }),

  lastDeletedFile: null,
  setLastDeletedFile: (info) => set({ lastDeletedFile: info }),

  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  activePanel: 'files',
  setActivePanel: (panel) => set({ activePanel: panel }),

  showCAD: true,
  showScan: false,
  showDeviation: false,
  showWallThickness: false,
  setShowCAD: (show) => set({ showCAD: show }),
  setShowScan: (show) => set({ showScan: show }),
  setShowDeviation: (show) => set({ showDeviation: show }),
  setShowWallThickness: (show) => set({ showWallThickness: show }),

  deviationScaleMin: -0.5,
  deviationScaleMax: 0.5,
  setDeviationScale: (min, max) => set({ deviationScaleMin: min, deviationScaleMax: max }),
}))
