import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, FolderOpen, ChevronRight, Loader2, X } from 'lucide-react' // Added X icon
import { projectsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import type { Project } from '@/types/api'
import { clsx } from 'clsx'

export default function ProjectSidebar() {
  const [isCreating, setIsCreating] = useState(false)
  const { currentProject, setCurrentProject, closeProject } = useAppStore() // Added closeProject

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: projectsAPI.list,
  })

  return (
    <div className="w-80 h-full bg-industrial-900 border-r border-industrial-700 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-industrial-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg text-neon-cyan tracking-wider">PROJECTS</h2>
          <button
            onClick={() => setIsCreating(true)}
            className="p-2 rounded bg-industrial-800 hover:bg-industrial-700 text-neon-cyan 
                       transition-all hover:shadow-neon-sm"
          >
            <Plus size={18} />
          </button>
        </div>

        {/* Search/Filter */}
        <input
          type="text"
          placeholder="SEARCH PROJECTS..."
          className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700 
                   rounded text-sm font-mono text-industrial-100 placeholder:text-industrial-500
                   focus:border-neon-cyan focus:outline-none"
        />
      </div>

      {/* Project List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <Loader2 className="animate-spin text-neon-cyan" size={24} />
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {projectsData?.items.map((project) => (
              <ProjectItem
                key={project.id}
                project={project}
                isActive={currentProject?.id === project.id}
                onClick={() => setCurrentProject(project)}
                onClose={closeProject} // Pass the close action
              />
            ))}
            {projectsData?.items.length === 0 && (
              <div className="text-center py-12 text-industrial-500 text-sm font-mono">
                NO PROJECTS
                <br />
                CREATE ONE TO START
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      <AnimatePresence>
        {isCreating && (
          <CreateProjectModal onClose={() => setIsCreating(false)} />
        )}
      </AnimatePresence>
    </div>
  )
}

// â”€â”€ Project Item â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface ProjectItemProps {
  project: Project
  isActive: boolean
  onClick: () => void
  onClose: () => void // Added to props
}

function ProjectItem({ project, isActive, onClick, onClose }: ProjectItemProps) {
  const statusColors = {
    pending: 'text-industrial-500',
    ready: 'text-neon-blue',
    aligned: 'text-neon-purple',
    analyzed: 'text-neon-green',
    error: 'text-neon-red',
  }

  const statusLabels = {
    pending: 'PENDING',
    ready: 'READY',
    aligned: 'ALIGNED',
    analyzed: 'ANALYZED',
    error: 'ERROR',
  }

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ x: 4 }}
      className={clsx(
        'w-full p-3 rounded text-left transition-all relative group',
        isActive
          ? 'bg-industrial-800 border border-neon-cyan/30 shadow-neon-sm'
          : 'bg-industrial-850 border border-industrial-800 hover:border-industrial-700'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FolderOpen
              size={14}
              className={isActive ? 'text-neon-cyan' : 'text-industrial-400'}
            />
            <span className="font-mono text-sm text-industrial-100 truncate">
              {project.name}
            </span>
          </div>

          {project.part_number && (
            <div className="text-xs font-mono text-industrial-400 truncate">
              PN: {project.part_number}
            </div>
          )}

          <div className="flex items-center gap-2 mt-2">
            <span className={clsx('text-xs font-mono', statusColors[project.status])}>
              {statusLabels[project.status]}
            </span>
            <div className="flex gap-1">
              {project.has_cad && (
                <div className="w-1.5 h-1.5 rounded-full bg-neon-blue" title="CAD uploaded" />
              )}
              {project.has_scan && (
                <div className="w-1.5 h-1.5 rounded-full bg-neon-purple" title="Scan uploaded" />
              )}
              {project.has_alignment && (
                <div className="w-1.5 h-1.5 rounded-full bg-neon-green" title="Aligned" />
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {isActive && (
            <>
              {/* Close Button implementation */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onClose();
                }}
                className="p-1 rounded hover:bg-industrial-700 text-industrial-400 hover:text-neon-red transition-colors"
                title="Close Project"
              >
                <X size={16} />
              </button>
              <ChevronRight className="text-neon-cyan flex-shrink-0" size={16} />
            </>
          )}
        </div>
      </div>
    </motion.button>
  )
}

// â”€â”€ Create Project Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// (Remaining CreateProjectModal code remains unchanged from your snippet)
