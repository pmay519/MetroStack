import { create } from 'zustand'
import type { Project } from '@/types/api'

interface AppState {
  // Current project
  currentProject: Project | null
  setCurrentProject: (project: Project | null) => void

  // UI state
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void

  activePanel: 'files' | 'alignment' | 'deviation' | 'gdt' | 'wall-thickness' | null
  setActivePanel: (
    panel: 'files' | 'alignment' | 'deviation' | 'gdt' | 'wall-thickness' | null
  ) => void

  // 3D Viewport state
  showCAD: boolean
  showScan: boolean
  showDeviation: boolean
  showWallThickness: boolean
  setShowCAD: (show: boolean) => void
  setShowScan: (show: boolean) => void
  setShowDeviation: (show: boolean) => void
  setShowWallThickness: (show: boolean) => void

  // Deviation heatmap color scale
  deviationScaleMin: number
  deviationScaleMax: number
  setDeviationScale: (min: number, max: number) => void
}

export const useAppStore = create<AppState>((set) => ({
  // Project
  currentProject: null,
  setCurrentProject: (project) => set({ currentProject: project }),

  // UI
  sidebarOpen: true,
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  activePanel: 'files',
  setActivePanel: (panel) => set({ activePanel: panel }),

  // 3D Viewport visibility
  showCAD: true,
  showScan: false,
  showDeviation: false,
  showWallThickness: false,
  setShowCAD: (show) => set({ showCAD: show }),
  setShowScan: (show) => set({ showScan: show }),
  setShowDeviation: (show) => set({ showDeviation: show }),
  setShowWallThickness: (show) => set({ showWallThickness: show }),

  // Deviation scale
  deviationScaleMin: -0.5,
  deviationScaleMax: 0.5,
  setDeviationScale: (min, max) => set({ deviationScaleMin: min, deviationScaleMax: max }),
}))
