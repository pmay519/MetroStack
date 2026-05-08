import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Play, Loader2, Info, Eye, EyeOff } from 'lucide-react'
import { analysisAPI, jobsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { clsx } from 'clsx'

export default function WallThicknessPanel() {
  const { currentProject, showWallThickness, setShowWallThickness } = useAppStore()
  const [sampleCount, setSampleCount] = useState(20000)
  const queryClient = useQueryClient()

  const { data: wallThicknessData } = useQuery({
    queryKey: ['wall-thickness-results', currentProject?.id],
    queryFn: () => analysisAPI.getWallThicknessResults(currentProject!.id),
    enabled: !!currentProject,
    retry: false,
  })

  const analyzeMutation = useMutation({
    mutationFn: () =>
      analysisAPI.analyzeWallThickness(currentProject!.id, { sample_count: sampleCount }),
    onSuccess: (data) => {
      const pollInterval = setInterval(async () => {
        const job = await jobsAPI.get(currentProject!.id, data.job_id)
        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(pollInterval)
          queryClient.invalidateQueries({
            queryKey: ['wall-thickness-results', currentProject!.id],
          })
          setShowWallThickness(true)
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
      <div>
        <h3 className="font-display text-lg text-neon-cyan mb-2 tracking-wider">
          WALL THICKNESS
        </h3>
        <p className="text-sm text-industrial-400 font-mono">Ray-cast thickness measurement</p>
      </div>

      {/* Sample Count Control */}
      <div>
        <label className="block text-xs font-mono text-industrial-300 mb-2">
          SAMPLE COUNT
        </label>
        <input
          type="number"
          value={sampleCount}
          onChange={(e) => setSampleCount(parseInt(e.target.value))}
          step="1000"
          min="1000"
          max="100000"
          disabled={!!wallThicknessData}
          className="w-full px-3 py-2 bg-industrial-950 border border-industrial-700
                   rounded font-mono text-sm text-industrial-100
                   focus:border-neon-cyan focus:outline-none
                   disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <p className="text-xs text-industrial-500 font-mono mt-1">
          Ray-cast sample points on surface
        </p>
      </div>

      {/* Run Analysis Button */}
      <button
        onClick={() => analyzeMutation.mutate()}
        disabled={analyzeMutation.isPending || !!wallThicknessData}
        className="w-full py-3 bg-neon-cyan hover:bg-neon-cyan/90 text-industrial-950
                 rounded font-mono font-semibold transition-all
                 disabled:opacity-50 disabled:cursor-not-allowed
                 hover:shadow-neon flex items-center justify-center gap-2"
      >
        {analyzeMutation.isPending ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            RAY-CASTING...
          </>
        ) : wallThicknessData ? (
          'ANALYSIS COMPLETE'
        ) : (
          <>
            <Play size={18} />
            RUN THICKNESS ANALYSIS
          </>
        )}
      </button>

      {/* Results */}
      {wallThicknessData && (
        <>
          {/* Visibility Toggle */}
          <button
            onClick={() => setShowWallThickness(!showWallThickness)}
            className={clsx(
              'w-full py-2 rounded font-mono text-sm transition-all flex items-center justify-center gap-2',
              showWallThickness
                ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50'
                : 'bg-industrial-800 text-industrial-300 border border-industrial-700 hover:border-industrial-600'
            )}
          >
            {showWallThickness ? <Eye size={16} /> : <EyeOff size={16} />}
            {showWallThickness ? 'THICKNESS MAP VISIBLE' : 'SHOW THICKNESS MAP'}
          </button>

          {/* Statistics */}
          <ThicknessStats stats={wallThicknessData.stats} />

          {/* Color Legend */}
          <ColorLegend
            min={wallThicknessData.stats.min_mm}
            max={wallThicknessData.stats.max_mm}
          />
        </>
      )}

      {/* Info Box */}
      <div className="p-4 bg-neon-blue/5 border border-neon-blue/20 rounded">
        <div className="flex gap-3">
          <Info className="text-neon-blue flex-shrink-0" size={16} />
          <div className="text-xs font-mono text-industrial-300 space-y-1">
            <p>Wall thickness measured via inward ray-casting from surface normals.</p>
            <p className="text-neon-amber">
              NOTE: Requires watertight CAD mesh for accurate results.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Thickness Statistics ──────────────────────────────────────────────────────

function ThicknessStats({ stats }: { stats: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 bg-industrial-900 border border-industrial-700 rounded space-y-3"
    >
      <div className="font-mono text-xs text-industrial-400 mb-3">STATISTICS</div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <StatItem label="SAMPLE COUNT" value={stats.sample_count.toLocaleString()} />

        <StatItem
          label="MEAN"
          value={`${stats.mean_mm.toFixed(3)} mm`}
          valueClass="text-neon-green"
        />

        <StatItem
          label="MIN"
          value={`${stats.min_mm.toFixed(3)} mm`}
          valueClass="text-neon-purple"
        />

        <StatItem label="MAX" value={`${stats.max_mm.toFixed(3)} mm`} valueClass="text-neon-amber" />

        <StatItem label="STD DEV" value={`${stats.std_mm.toFixed(3)} mm`} />

        <StatItem
          label="RANGE"
          value={`${(stats.max_mm - stats.min_mm).toFixed(3)} mm`}
          valueClass="text-industrial-200"
        />
      </div>

      {/* Thickness distribution indicator */}
      <div className="pt-3 border-t border-industrial-800">
        <div className="text-xs text-industrial-500 mb-2">THICKNESS DISTRIBUTION</div>
        <div className="relative h-2 bg-industrial-950 rounded overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${(stats.mean_mm / stats.max_mm) * 100}%` }}
            className="absolute left-0 top-0 h-full bg-gradient-to-r from-purple-600 via-green-500 to-yellow-400"
          />
        </div>
        <div className="flex justify-between text-xs font-mono text-industrial-500 mt-1">
          <span>THIN</span>
          <span>THICK</span>
        </div>
      </div>
    </motion.div>
  )
}

function StatItem({
  label,
  value,
  valueClass = 'text-industrial-200',
}: {
  label: string
  value: string
  valueClass?: string
}) {
  return (
    <div>
      <div className="text-industrial-500 mb-1">{label}</div>
      <div className={clsx('font-semibold', valueClass)}>{value}</div>
    </div>
  )
}

// ── Color Legend ──────────────────────────────────────────────────────────────

function ColorLegend({ min, max }: { min: number; max: number }) {
  return (
    <div className="p-4 bg-industrial-900 border border-industrial-700 rounded">
      <div className="font-mono text-xs text-industrial-400 mb-3">VIRIDIS SCALE</div>

      {/* Gradient bar */}
      <div className="relative h-6 rounded overflow-hidden mb-2">
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to right, #440154, #3b528b, #21918c, #5ec962, #fde725)',
          }}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between font-mono text-xs">
        <span className="text-purple-400">{min.toFixed(2)} mm</span>
        <span className="text-green-400">{((min + max) / 2).toFixed(2)} mm</span>
        <span className="text-yellow-400">{max.toFixed(2)} mm</span>
      </div>
    </div>
  )
}
