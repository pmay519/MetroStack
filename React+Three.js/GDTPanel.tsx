import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Play, CheckCircle2, XCircle, Trash2, Loader2 } from 'lucide-react'
import { analysisAPI, jobsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import type { GDTFeatureType, CreateGDTFeatureRequest } from '@/types/api'
import { clsx } from 'clsx'

const GDT_FEATURE_TYPES: { value: GDTFeatureType; label: string }[] = [
  { value: 'flatness', label: 'Flatness' },
  { value: 'straightness', label: 'Straightness' },
  { value: 'circularity', label: 'Circularity' },
  { value: 'cylindricity', label: 'Cylindricity' },
  { value: 'position', label: 'Position' },
  { value: 'parallelism', label: 'Parallelism' },
  { value: 'perpendicularity', label: 'Perpendicularity' },
  { value: 'angularity', label: 'Angularity' },
  { value: 'profile_surface', label: 'Profile of Surface' },
  { value: 'runout', label: 'Circular Runout' },
  { value: 'total_runout', label: 'Total Runout' },
]

export default function GDTPanel() {
  const { currentProject } = useAppStore()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const queryClient = useQueryClient()

  const { data: features } = useQuery({
    queryKey: ['gdt-features', currentProject?.id],
    queryFn: () => analysisAPI.listGDTFeatures(currentProject!.id),
    enabled: !!currentProject,
  })

  const { data: results } = useQuery({
    queryKey: ['gdt-results', currentProject?.id],
    queryFn: () => analysisAPI.getGDTResults(currentProject!.id),
    enabled: !!currentProject,
    retry: false,
  })

  const analyzeMutation = useMutation({
    mutationFn: () => analysisAPI.analyzeGDT(currentProject!.id),
    onSuccess: (data) => {
      const pollInterval = setInterval(async () => {
        const job = await jobsAPI.get(currentProject!.id, data.job_id)
        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(pollInterval)
          queryClient.invalidateQueries({ queryKey: ['gdt-results', currentProject!.id] })
        }
      }, 3000)
    },
  })

  if (!currentProject) {
    return (
      <div className="flex items-center justify-center h-full text-industrial-500 font-mono text-sm">
        SELECT A PROJECT
      </div>
    )
  }

  return (
    <div className="h-full p-6 space-y-6 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-lg text-neon-cyan mb-1 tracking-wider">
            GD&T ANALYSIS
          </h3>
          <p className="text-sm text-industrial-400 font-mono">
            Geometric dimensioning & tolerancing
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="p-2 rounded bg-industrial-800 hover:bg-industrial-700 
                   text-neon-cyan transition-all hover:shadow-neon-sm"
        >
          <Plus size={18} />
        </button>
      </div>

      {/* Features List */}
      {features && features.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-mono text-industrial-400">
            DEFINED FEATURES ({features.length})
          </div>
          {features.map((feature) => (
            <FeatureCard key={feature.id} feature={feature} />
          ))}
        </div>
      )}

      {/* Run Analysis */}
      {features && features.length > 0 && (
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending || !!results}
          className="w-full py-3 bg-neon-cyan hover:bg-neon-cyan/90 text-industrial-950
                   rounded font-mono font-semibold transition-all
                   disabled:opacity-50 disabled:cursor-not-allowed
                   hover:shadow-neon flex items-center justify-center gap-2"
        >
          {analyzeMutation.isPending ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              ANALYZING...
            </>
          ) : results ? (
            <>
              <CheckCircle2 size={18} />
              ANALYSIS COMPLETE
            </>
          ) : (
            <>
              <Play size={18} />
              RUN GD&T ANALYSIS
            </>
          )}
        </button>
      )}

      {/* Results Table */}
      {results && results.length > 0 && <ResultsTable results={results} />}

      {/* Empty State */}
      {(!features || features.length === 0) && (
        <div className="text-center py-12 text-industrial-500 text-sm font-mono">
          NO FEATURES DEFINED
          <br />
          ADD A FEATURE TO START
        </div>
      )}

      {/* Create Feature Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <CreateFeatureModal
            projectId={currentProject.id}
            onClose={() => setShowCreateModal(false)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Feature Card ──────────────────────────────────────────────────────────────

function FeatureCard({ feature }: { feature: any }) {
  const queryClient = useQueryClient()

  const deleteMutation = useMutation({
    mutationFn: () => analysisAPI.deleteGDTFeature(feature.project_id, feature.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gdt-features', feature.project_id] })
    },
  })

  return (
    <div className="p-3 bg-industrial-900 border border-industrial-700 rounded">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="font-mono text-sm text-industrial-100 mb-1">{feature.name}</div>
          <div className="text-xs text-industrial-400">
            {GDT_FEATURE_TYPES.find((t) => t.value === feature.feature_type)?.label}
          </div>
        </div>
        <button
          onClick={() => deleteMutation.mutate()}
          disabled={deleteMutation.isPending}
          className="p-1.5 rounded hover:bg-industrial-800 text-industrial-500 
                   hover:text-neon-red transition-colors"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {feature.tolerance_upper_mm !== null && (
        <div className="mt-2 pt-2 border-t border-industrial-800 text-xs font-mono">
          <span className="text-industrial-500">TOLERANCE: </span>
          <span className="text-industrial-200">
            ±{feature.tolerance_upper_mm.toFixed(3)} mm
          </span>
        </div>
      )}
    </div>
  )
}

// ── Results Table ─────────────────────────────────────────────────────────────

function ResultsTable({ results }: { results: any[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="border border-industrial-700 rounded overflow-hidden"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead className="bg-industrial-800 text-industrial-300">
            <tr>
              <th className="px-3 py-2 text-left">FEATURE</th>
              <th className="px-3 py-2 text-left">TYPE</th>
              <th className="px-3 py-2 text-right">ACTUAL</th>
              <th className="px-3 py-2 text-right">TOLERANCE</th>
              <th className="px-3 py-2 text-center">STATUS</th>
            </tr>
          </thead>
          <tbody className="bg-industrial-900">
            {results.map((result, i) => (
              <tr
                key={result.id}
                className={clsx(
                  'border-t border-industrial-800',
                  i % 2 === 0 ? 'bg-industrial-900' : 'bg-industrial-900/50'
                )}
              >
                <td className="px-3 py-2 text-industrial-100">{result.feature_name}</td>
                <td className="px-3 py-2 text-industrial-400">
                  {GDT_FEATURE_TYPES.find((t) => t.value === result.feature_type)?.label}
                </td>
                <td className="px-3 py-2 text-right text-industrial-200">
                  {result.actual_value_mm.toFixed(4)} mm
                </td>
                <td className="px-3 py-2 text-right text-industrial-400">
                  ±{result.tolerance_upper_mm?.toFixed(3)} mm
                </td>
                <td className="px-3 py-2 text-center">
                  {result.in_tolerance ? (
                    <CheckCircle2 className="inline text-neon-green" size={16} />
                  ) : (
                    <XCircle className="inline text-neon-red" size={16} />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  )
}

// ── Create Feature Modal ──────────────────────────────────────────────────────

function CreateFeatureModal({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const [formData, setFormData] = useState<CreateGDTFeatureRequest>({
    name: '',
    feature_type: 'flatness',
    tolerance_upper_mm: 0.05,
  })

  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: (data: CreateGDTFeatureRequest) =>
      analysisAPI.createGDTFeature(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gdt-features', projectId] })
      onClose()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name.trim()) return
    createMutation.mutate(formData)
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
                   shadow-2xl shadow-neon-cyan/10 max-h-[90vh] overflow-y-auto"
      >
        <h3 className="font-display text-xl text-neon-cyan mb-6 tracking-wider">
          NEW GD&T FEATURE
        </h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              FEATURE NAME *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Datum A"
              autoFocus
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              CHARACTERISTIC TYPE *
            </label>
            <select
              value={formData.feature_type}
              onChange={(e) =>
                setFormData({ ...formData, feature_type: e.target.value as GDTFeatureType })
              }
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            >
              {GDT_FEATURE_TYPES.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              TOLERANCE (mm)
            </label>
            <input
              type="number"
              value={formData.tolerance_upper_mm ?? ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  tolerance_upper_mm: parseFloat(e.target.value),
                })
              }
              step="0.001"
              placeholder="0.050"
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            />
          </div>

          {/* ROI Bounding Box (optional) */}
          <details className="p-3 bg-industrial-950 border border-industrial-800 rounded">
            <summary className="cursor-pointer text-xs font-mono text-industrial-400 hover:text-industrial-300">
              REGION OF INTEREST (OPTIONAL)
            </summary>
            <div className="mt-3 space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="number"
                  placeholder="MIN X"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_min_x: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
                <input
                  type="number"
                  placeholder="MIN Y"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_min_y: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
                <input
                  type="number"
                  placeholder="MIN Z"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_min_z: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <input
                  type="number"
                  placeholder="MAX X"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_max_x: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
                <input
                  type="number"
                  placeholder="MAX Y"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_max_y: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
                <input
                  type="number"
                  placeholder="MAX Z"
                  onChange={(e) =>
                    setFormData({ ...formData, roi_max_z: parseFloat(e.target.value) })
                  }
                  className="px-2 py-1.5 bg-industrial-900 border border-industrial-700
                           rounded font-mono text-xs text-industrial-100"
                />
              </div>
            </div>
          </details>

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
              disabled={!formData.name.trim() || createMutation.isPending}
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
                'CREATE FEATURE'
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}
