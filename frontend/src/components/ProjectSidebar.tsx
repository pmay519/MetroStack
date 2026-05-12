import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, FolderOpen, ChevronRight, Loader2 } from 'lucide-react'
import { projectsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import type { Project } from '@/types/api'
import { clsx } from 'clsx'

export default function ProjectSidebar() {
  const [isCreating, setIsCreating] = useState(false)
  const { currentProject, setCurrentProject } = useAppStore()

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

        {/* Search/Filter placeholder */}
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
}

function ProjectItem({ project, isActive, onClick }: ProjectItemProps) {
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
        'w-full p-3 rounded text-left transition-all',
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

        {isActive && (
          <ChevronRight className="text-neon-cyan flex-shrink-0" size={16} />
        )}
      </div>
    </motion.button>
  )
}

// â”€â”€ Create Project Modal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function CreateProjectModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [partNumber, setPartNumber] = useState('')
  const [revision, setRevision] = useState('')
  const [description, setDescription] = useState('')

  const queryClient = useQueryClient()
  const { setCurrentProject } = useAppStore()

  const createMutation = useMutation({
    mutationFn: projectsAPI.create,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setCurrentProject(project)
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    createMutation.mutate({
      name: name.trim(),
      part_number: partNumber.trim() || undefined,
      revision: revision.trim() || undefined,
      description: description.trim() || undefined,
    })
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="bg-industrial-900 border border-neon-cyan/30 rounded-lg p-6 w-full max-w-md
                   shadow-2xl shadow-neon-cyan/10"
      >
        <h3 className="font-display text-xl text-neon-cyan mb-6 tracking-wider">
          NEW PROJECT
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              PROJECT NAME *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Giga Press Mold Analysis"
              autoFocus
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-mono text-industrial-300 mb-2">
                PART NUMBER
              </label>
              <input
                type="text"
                value={partNumber}
                onChange={(e) => setPartNumber(e.target.value)}
                placeholder="PN-12345"
                className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                         rounded font-mono text-sm text-industrial-100
                         focus:border-neon-cyan focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-mono text-industrial-300 mb-2">
                REVISION
              </label>
              <input
                type="text"
                value={revision}
                onChange={(e) => setRevision(e.target.value)}
                placeholder="A"
                className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                         rounded font-mono text-sm text-industrial-100
                         focus:border-neon-cyan focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              DESCRIPTION
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional notes..."
              rows={3}
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100 resize-none
                       focus:border-neon-cyan focus:outline-none"
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-industrial-800 hover:bg-industrial-700
                       text-industrial-300 rounded font-mono text-sm transition-colors"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={!name.trim() || createMutation.isPending}
              className="flex-1 px-4 py-2 bg-neon-cyan hover:bg-neon-cyan/90
                       text-industrial-950 rounded font-mono text-sm font-semibold
                       transition-all disabled:opacity-50 disabled:cursor-not-allowed
                       hover:shadow-neon-sm"
            >
              {createMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={14} className="animate-spin" />
                  CREATING...
                </span>
              ) : (
                'CREATE'
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}
