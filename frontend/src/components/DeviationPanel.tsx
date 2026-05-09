import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Play, TrendingUp, Loader2, Info, Eye, EyeOff } from 'lucide-react'
import { analysisAPI, jobsAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { formatDeviation, getDeviationColorClass } from '@/lib/colormap'
import { clsx } from 'clsx'

export default function DeviationPanel() {
  const { currentProject, showDeviation, setShowDeviation, setDeviationScale } = useAppStore()
  const queryClient = useQueryClient()

  const { data: deviationData } = useQuery({
    queryKey: ['deviation-results', currentProject?.id],
    queryFn: () => analysisAPI.getDeviationResults(currentProject!.id),
    enabled: !!currentProject,
    retry: false,
  })

  const analyzeMutation = useMutation({
    mutationFn: () => analysisAPI.analyzeDeviation(currentProject!.id),
    onSuccess: (data) => {
      // Poll job status
      const pollInterval = setInterval(async () => {
        const job = await jobsAPI.get(currentProject!.id, data.job_id)
        if (job.status === 'complete' || job.status === 'failed') {
          clearInterval(pollInterval)
          queryClient.invalidateQueries({ queryKey: ['deviation-results', currentProject!.id] })
          setShowDeviation(true)
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
          DEVIATION ANALYSIS
        </h3>
        <p className="text-sm text-industrial-400 font-mono">
          Point-to-CAD signed distance heatmap
        </p>
      </div>

      {/* Run Analysis Button */}
      <button
        onClick={() => analyzeMutation.mutate()}
        disabled={analyzeMutation.isPending || !!deviationData}
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
        ) : deviationData ? (
          <>
            <TrendingUp size={18} />
            ANALYSIS COMPLETE
          </>
        ) : (
          <>
            <Play size={18} />
            RUN DEVIATION ANALYSIS
          </>
        )}
      </button>

      {/* Results */}
      {deviationData && (
        <>
          {/* Visibility Toggle */}
          <button
            onClick={() => setShowDeviation(!showDeviation)}
            className={clsx(
              'w-full py-2 rounded font-mono text-sm transition-all flex items-center justify-center gap-2',
              showDeviation
                ? 'bg-neon-cyan/20 text-neon-cyan border border-neon-cyan/50'
                : 'bg-industrial-800 text-industrial-300 border border-industrial-700 hover:border-industrial-600'
            )}
          >
            {showDeviation ? <Eye size={16} /> : <EyeOff size={16} />}
            {showDeviation ? 'HEATMAP VISIBLE' : 'SHOW HEATMAP'}
          </button>

          {/* Statistics */}
          <DeviationStats stats={deviationData.stats} />

          {/* Color Scale Control */}
          <ColorScaleControl
            currentMin={deviationData.stats.scale_min_mm}
            currentMax={deviationData.stats.scale_max_mm}
            dataMin={deviationData.stats.min_mm}
            dataMax={deviationData.stats.max_mm}
            onChange={(min, max) => setDeviationScale(min, max)}
          />

          {/* Color Legend */}
          <ColorLegend
            min={deviationData.stats.scale_min_mm}
            max={deviationData.stats.scale_max_mm}
          />
        </>
      )}

      {/* Info Box */}
      <div className="p-4 bg-neon-blue/5 border border-neon-blue/20 rounded">
        <div className="flex gap-3">
          <Info className="text-neon-blue flex-shrink-0" size={16} />
          <div className="text-xs font-mono text-industrial-300 space-y-1">
            <p>
              <span className="text-neon-blue">BLUE:</span> Inside CAD (material missing)
            </p>
            <p>
              <span className="text-white">WHITE:</span> On CAD surface (nominal)
            </p>
            <p>
              <span className="text-neon-red">RED:</span> Outside CAD (material excess)
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Deviation Statistics ──────────────────────────────────────────────────────

function DeviationStats({ stats }: { stats: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 bg-industrial-900 border border-industrial-700 rounded space-y-3"
    >
      <div className="font-mono text-xs text-industrial-400 mb-3">STATISTICS</div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <StatItem label="POINT COUNT" value={stats.point_count.toLocaleString()} />
        
        <StatItem
          label="RMS"
          value={`${stats.rms_mm.toFixed(3)} mm`}
          valueClass="text-neon-amber"
        />

        <StatItem
          label="MIN"
          value={formatDeviation(stats.min_mm) + ' mm'}
          valueClass={getDeviationColorClass(stats.min_mm)}
        />

        <StatItem
          label="MAX"
          value={formatDeviation(stats.max_mm) + ' mm'}
          valueClass={getDeviationColorClass(stats.max_mm)}
        />

        <StatItem
          label="MEAN"
          value={formatDeviation(stats.mean_mm) + ' mm'}
          valueClass={getDeviationColorClass(stats.mean_mm)}
        />

        <StatItem label="P95" value={`${stats.p95_mm.toFixed(3)} mm`} />
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

// ── Color Scale Control ───────────────────────────────────────────────────────

function ColorScaleControl({
  currentMin,
  currentMax,
  dataMin,
  dataMax,
  onChange,
}: {
  currentMin: number
  currentMax: number
  dataMin: number
  dataMax: number
  onChange: (min: number, max: number) => void
}) {
  const [min, setMin] = useState(currentMin)
  const [max, setMax] = useState(currentMax)

  const handleApply = () => {
    onChange(min, max)
  }

  const handleReset = () => {
    const absMax = Math.max(Math.abs(dataMin), Math.abs(dataMax))
    const symmetric = Math.ceil(absMax * 100) / 100
    setMin(-symmetric)
    setMax(symmetric)
    onChange(-symmetric, symmetric)
  }

  return (
    <div className="p-4 bg-industrial-900/50 border border-industrial-800 rounded space-y-3">
      <div className="font-mono text-xs text-industrial-400">COLOR SCALE BOUNDS</div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-mono text-industrial-500 mb-1">MIN (mm)</label>
          <input
            type="number"
            value={min}
            onChange={(e) => setMin(parseFloat(e.target.value))}
            step="0.01"
            className="w-full px-2 py-1.5 bg-industrial-950 border border-industrial-700
                     rounded font-mono text-xs text-industrial-100
                     focus:border-neon-cyan focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-xs font-mono text-industrial-500 mb-1">MAX (mm)</label>
          <input
            type="number"
            value={max}
            onChange={(e) => setMax(parseFloat(e.target.value))}
            step="0.01"
            className="w-full px-2 py-1.5 bg-industrial-950 border border-industrial-700
                     rounded font-mono text-xs text-industrial-100
                     focus:border-neon-cyan focus:outline-none"
          />
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleReset}
          className="flex-1 px-3 py-1.5 bg-industrial-800 hover:bg-industrial-700
                   text-industrial-300 rounded font-mono text-xs transition-colors"
        >
          RESET
        </button>
        <button
          onClick={handleApply}
          className="flex-1 px-3 py-1.5 bg-neon-cyan/20 hover:bg-neon-cyan/30
                   text-neon-cyan rounded font-mono text-xs transition-colors
                   border border-neon-cyan/50"
        >
          APPLY
        </button>
      </div>
    </div>
  )
}

// ── Color Legend ──────────────────────────────────────────────────────────────

function ColorLegend({ min, max }: { min: number; max: number }) {
  return (
    <div className="p-4 bg-industrial-900 border border-industrial-700 rounded">
      <div className="font-mono text-xs text-industrial-400 mb-3">HEATMAP SCALE</div>

      {/* Gradient bar */}
      <div className="relative h-6 rounded overflow-hidden mb-2">
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(to right, rgb(59, 130, 246), rgb(255, 255, 255), rgb(239, 68, 68))',
          }}
        />
      </div>

      {/* Labels */}
      <div className="flex justify-between font-mono text-xs">
        <span className="text-blue-400">{formatDeviation(min)} mm</span>
        <span className="text-gray-300">0.000 mm</span>
        <span className="text-red-400">{formatDeviation(max)} mm</span>
      </div>
    </div>
  )
}
