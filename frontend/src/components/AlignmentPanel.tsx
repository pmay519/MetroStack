import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Play, CheckCircle2, AlertCircle, Loader2, Info } from 'lucide-react'
import { analysisAPI, jobsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import type { AlignmentMethod } from '@/types/api'
import { clsx } from 'clsx'

export default function AlignmentPanel() {
  const { currentProject } = useAppStore()
  const [method, setMethod] = useState<AlignmentMethod>('icp')
  const [maxDist, setMaxDist] = useState(5.0)
  const [maxIter, setMaxIter] = useState(200)

  const queryClient = useQueryClient()

  const { data: alignment } = useQuery({
    queryKey: ['alignment', currentProject?.id],
    queryFn: () => analysisAPI.getAlignment(currentProject!.id),
    enabled: !!currentProject,
    retry: false,
  })

  const alignMutation = useMutation({
    mutationFn: () =>
      analysisAPI.align(currentProject!.id, {
        method,
        max_correspondence_dist_mm: maxDist,
        max_iterations: maxIter,
      }),
    onSuccess: (data) => {
      // Poll job status
      const pollInterval = setInterval(async () => {
        const job = await jobsAPI.get(currentProject!.id, data.job_id)
        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(pollInterval)
          queryClient.invalidateQueries({ queryKey: ['alignment', currentProject!.id] })
          queryClient.invalidateQueries({ queryKey: ['projects'] })
        }
      }, 2000)
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
      <div>
        <h3 className="font-display text-lg text-neon-cyan mb-2 tracking-wider">ALIGNMENT</h3>
        <p className="text-sm text-industrial-400 font-mono">
          Register scan to CAD reference frame
        </p>
      </div>

      {/* Method Selection */}
      <div>
        <label className="block text-xs font-mono text-industrial-300 mb-2">
          REGISTRATION METHOD
        </label>
        <div className="grid grid-cols-2 gap-2">
          <MethodButton
            active={method === 'icp'}
            onClick={() => setMethod('icp')}
            label="ICP"
            description="Point-to-Plane"
          />
          <MethodButton
            active={method === 'fgr'}
            onClick={() => setMethod('fgr')}
            label="FGR"
            description="Fast Global"
          />
        </div>
      </div>

      {/* ICP Parameters */}
      {method === 'icp' && (
        <div className="space-y-4 p-4 bg-industrial-900/50 border border-industrial-800 rounded">
          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              MAX CORRESPONDENCE DISTANCE (mm)
            </label>
            <input
              type="number"
              value={maxDist}
              onChange={(e) => setMaxDist(parseFloat(e.target.value))}
              step="0.1"
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            />
            <p className="text-xs text-industrial-500 font-mono mt-1">
              Correspondence search radius
            </p>
          </div>

          <div>
            <label className="block text-xs font-mono text-industrial-300 mb-2">
              MAX ITERATIONS
            </label>
            <input
              type="number"
              value={maxIter}
              onChange={(e) => setMaxIter(parseInt(e.target.value))}
              step="10"
              className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                       rounded font-mono text-sm text-industrial-100
                       focus:border-neon-cyan focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Run Button */}
      <button
        onClick={() => alignMutation.mutate()}
        disabled={alignMutation.isPending || !!alignment}
        className="w-full py-3 bg-neon-cyan hover:bg-neon-cyan/90 text-industrial-950
                 rounded font-mono font-semibold transition-all
                 disabled:opacity-50 disabled:cursor-not-allowed
                 hover:shadow-neon flex items-center justify-center gap-2"
      >
        {alignMutation.isPending ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            ALIGNING...
          </>
        ) : alignment ? (
          <>
            <CheckCircle2 size={18} />
            ALIGNED
          </>
        ) : (
          <>
            <Play size={18} />
            RUN ALIGNMENT
          </>
        )}
      </button>

      {/* Alignment Results */}
      {alignment && <AlignmentResults alignment={alignment} />}

      {/* Info Box */}
      <div className="p-4 bg-neon-blue/5 border border-neon-blue/20 rounded">
        <div className="flex gap-3">
          <Info className="text-neon-blue flex-shrink-0" size={16} />
          <div className="text-xs font-mono text-industrial-300 space-y-1">
            <p>
              <span className="text-neon-blue">ICP:</span> Iterative Closest Point — high
              precision, needs good initial guess
            </p>
            <p>
              <span className="text-neon-blue">FGR:</span> Fast Global Registration — automatic
              coarse alignment via FPFH features
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Method Button ─────────────────────────────────────────────────────────────

interface MethodButtonProps {
  active: boolean
  onClick: () => void
  label: string
  description: string
}

function MethodButton({ active, onClick, label, description }: MethodButtonProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'p-3 rounded border transition-all text-left',
        active
          ? 'bg-neon-cyan/10 border-neon-cyan text-neon-cyan shadow-neon-sm'
          : 'bg-industrial-900 border-industrial-700 text-industrial-300 hover:border-industrial-600'
      )}
    >
      <div className="font-mono font-semibold text-sm mb-1">{label}</div>
      <div className="text-xs opacity-70">{description}</div>
    </button>
  )
}

// ── Alignment Results ─────────────────────────────────────────────────────────

function AlignmentResults({ alignment }: { alignment: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 bg-industrial-900 border border-neon-green/30 rounded"
    >
      <div className="flex items-center gap-2 mb-4">
        <CheckCircle2 className="text-neon-green" size={18} />
        <span className="font-mono text-sm text-neon-green">ALIGNMENT COMPLETE</span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div>
          <span className="text-industrial-500">METHOD: </span>
          <span className="text-industrial-200">{alignment.method.toUpperCase()}</span>
        </div>
        <div>
          <span className="text-industrial-500">RMSE: </span>
          <span className="text-neon-green">
            {alignment.inlier_rmse_mm?.toFixed(4)} mm
          </span>
        </div>
        <div>
          <span className="text-industrial-500">FITNESS: </span>
          <span className="text-industrial-200">
            {(alignment.fitness_score * 100).toFixed(1)}%
          </span>
        </div>
        <div>
          <span className="text-industrial-500">INLIERS: </span>
          <span className="text-industrial-200">
            {alignment.inlier_count?.toLocaleString()}
          </span>
        </div>
        <div className="col-span-2">
          <span className="text-industrial-500">ITERATIONS: </span>
          <span className="text-industrial-200">{alignment.iteration_count}</span>
        </div>
      </div>

      {/* Transform Matrix (collapsed by default) */}
      <details className="mt-4 pt-4 border-t border-industrial-800">
        <summary className="cursor-pointer text-xs font-mono text-industrial-400 hover:text-industrial-300">
          TRANSFORM MATRIX
        </summary>
        <pre className="mt-2 p-2 bg-industrial-950 rounded text-xs font-mono text-industrial-300 overflow-x-auto">
          {alignment.transform_matrix
            .split(',')
            .map(parseFloat)
            .reduce((acc: number[][], val: number, i: number) => {
              const row = Math.floor(i / 4)
              if (!acc[row]) acc[row] = []
              acc[row].push(val)
              return acc
            }, [])
            .map((row: number[]) => row.map((v) => v.toFixed(6).padStart(12)).join(' '))
            .join('\n')}
        </pre>
      </details>
    </motion.div>
  )
}
