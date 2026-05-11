import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Upload, FileCode, Scan, CheckCircle2, AlertCircle, Loader2, X } from 'lucide-react'
import { uploadAPI } from '@/lib/api'
import { useAppStore } from '@/lib/store'
import { clsx } from 'clsx'

const CAD_FORMATS = ['.stl', '.obj', '.ply', '.step', '.stp', '.iges', '.igs']
const SCAN_FORMATS = ['.ply', '.pcd', '.xyz', '.e57', '.las', '.laz', '.pts', '.csv']

export default function UploadPanel() {
  const { currentProject } = useAppStore()

  if (!currentProject) {
    return (
      <div className="flex items-center justify-center h-full text-industrial-500 font-mono text-sm">
        SELECT A PROJECT TO UPLOAD FILES
      </div>
    )
  }

  return (
    <div className="h-full p-6 space-y-6 overflow-y-auto">
      <div>
        <h3 className="font-display text-lg text-neon-cyan mb-2 tracking-wider">
          FILE UPLOAD
        </h3>
        <p className="text-sm text-industrial-400 font-mono">
          Upload CAD reference and scan point cloud
        </p>
      </div>

      <CADUploadZone projectId={currentProject.id} />
      <ScanUploadZone projectId={currentProject.id} />
    </div>
  )
}

// â”€â”€ CAD Upload Zone â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function CADUploadZone({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const { setShowCAD, setLastDeletedFile } = useAppStore()

  const { data: cadInfo } = useQuery({
    queryKey: ['cad-info', projectId],
    queryFn: () => uploadAPI.getCADInfo(projectId),
    retry: false,
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAPI.uploadCAD(projectId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cad-info', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCAD(true)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => uploadAPI.deleteCAD(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cad-info', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      // Signal 3D scene cleanup and hide visibility
      setLastDeletedFile({ id: projectId, type: 'CAD' })
      setShowCAD(false)
    },
  })

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        uploadMutation.mutate(acceptedFiles[0])
      }
    },
    [uploadMutation]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {'application/octet-stream': ['.stl', '.obj', '.ply', '.step', '.stp', '.iges', '.igs']},
    maxFiles: 1,
    disabled: uploadMutation.isPending || !!cadInfo,
  })

  if (cadInfo) {
    return (
      <FileInfoCard
        icon={<FileCode className="text-neon-blue" size={20} />}
        title="CAD REFERENCE"
        file={cadInfo}
        onDelete={() => deleteMutation.mutate()}
        isDeleting={deleteMutation.isPending}
      />
    )
  }

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'border-2 border-dashed rounded-lg p-8 transition-all cursor-pointer',
        isDragActive
          ? 'border-neon-cyan bg-neon-cyan/5'
          : 'border-industrial-700 hover:border-industrial-600 bg-industrial-900/50'
      )}
    >
      <input {...getInputProps()} />

      {uploadMutation.isPending ? (
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin text-neon-cyan" size={32} />
          <span className="font-mono text-sm text-industrial-300">UPLOADING CAD...</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <FileCode className="text-industrial-500" size={32} />
          <div className="text-center">
            <p className="font-mono text-sm text-industrial-300 mb-1">
              {isDragActive ? 'DROP CAD FILE HERE' : 'DRAG CAD FILE OR CLICK TO BROWSE'}
            </p>
            <p className="text-xs text-industrial-500 font-mono">
              {CAD_FORMATS.join(', ').toUpperCase()}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// â”€â”€ Scan Upload Zone â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function ScanUploadZone({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient()
  const { setShowScan, setLastDeletedFile } = useAppStore()

  const { data: scanInfo } = useQuery({
    queryKey: ['scan-info', projectId],
    queryFn: () => uploadAPI.getScanInfo(projectId),
    retry: false,
  })

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadAPI.uploadScan(projectId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan-info', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowScan(true)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => uploadAPI.deleteScan(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scan-info', projectId] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setLastDeletedFile({ id: projectId, type: 'SCAN' })
      setShowScan(false)
      // Signal 3D scene cleanup and hide visibility
      setLastDeletedFile({ id: projectId, type: 'SCAN' })
      setShowScan(false)
    },
  })

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        uploadMutation.mutate(acceptedFiles[0])
      }
    },
    [uploadMutation]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {'application/octet-stream': ['.ply', '.pcd', '.xyz', '.e57', '.las', '.laz', '.csv']},
    maxFiles: 1,
    disabled: uploadMutation.isPending || !!scanInfo,
  })

  if (scanInfo) {
    return (
      <FileInfoCard
        icon={<Scan className="text-neon-purple" size={20} />}
        title="SCAN CLOUD"
        file={scanInfo}
        onDelete={() => deleteMutation.mutate()}
        isDeleting={deleteMutation.isPending}
      />
    )
  }

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'border-2 border-dashed rounded-lg p-8 transition-all cursor-pointer',
        isDragActive
          ? 'border-neon-cyan bg-neon-cyan/5'
          : 'border-industrial-700 hover:border-industrial-600 bg-industrial-900/50'
      )}
    >
      <input {...getInputProps()} />

      {uploadMutation.isPending ? (
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="animate-spin text-neon-cyan" size={32} />
          <span className="font-mono text-sm text-industrial-300">UPLOADING SCAN...</span>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <Scan className="text-industrial-500" size={32} />
          <div className="text-center">
            <p className="font-mono text-sm text-industrial-300 mb-1">
              {isDragActive ? 'DROP SCAN FILE HERE' : 'DRAG SCAN FILE OR CLICK TO BROWSE'}
            </p>
            <p className="text-xs text-industrial-500 font-mono">
              {SCAN_FORMATS.slice(0, 5).join(', ').toUpperCase()} + MORE
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// â”€â”€ File Info Card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

interface FileInfoCardProps {
  icon: React.ReactNode
  title: string
  file: {
    filename: string
    file_format: string
    file_size_bytes: number
    is_processed: boolean
    vertex_count?: number | null
    face_count?: number | null
    point_count?: number | null
  }
  onDelete: () => void
  isDeleting: boolean
}

function FileInfoCard({ icon, title, file, onDelete, isDeleting }: FileInfoCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-industrial-900 border border-industrial-700 rounded-lg p-4"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          {icon}
          <div>
            <div className="font-mono text-xs text-industrial-400 mb-1">{title}</div>
            <div className="font-mono text-sm text-industrial-100">{file.filename}</div>
          </div>
        </div>

        <button
          onClick={onDelete}
          disabled={isDeleting}
          className="p-1.5 rounded hover:bg-industrial-800 text-industrial-400 
                   hover:text-neon-red transition-colors disabled:opacity-50"
        >
          {isDeleting ? <Loader2 size={16} className="animate-spin" /> : <X size={16} />}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div>
          <span className="text-industrial-500">FORMAT: </span>
          <span className="text-industrial-200">{file.file_format.toUpperCase()}</span>
        </div>
        <div>
          <span className="text-industrial-500">SIZE: </span>
          <span className="text-industrial-200">
            {(file.file_size_bytes / 1024 / 1024).toFixed(1)} MB
          </span>
        </div>

        {'vertex_count' in file && file.vertex_count !== null && (
          <>
            <div>
              <span className="text-industrial-500">VERTICES: </span>
              <span className="text-industrial-200">{file.vertex_count.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-industrial-500">FACES: </span>
              <span className="text-industrial-200">{file.face_count?.toLocaleString()}</span>
            </div>
          </>
        )}

        {'point_count' in file && file.point_count !== null && (
          <div className="col-span-2">
            <span className="text-industrial-500">POINTS: </span>
            <span className="text-industrial-200">{file.point_count.toLocaleString()}</span>
          </div>
        )}
      </div>

      <div className="mt-3 pt-3 border-t border-industrial-800 flex items-center gap-2">
        {file.is_processed ? (
          <>
            <CheckCircle2 className="text-neon-green" size={14} />
            <span className="text-xs font-mono text-neon-green">PROCESSED</span>
          </>
        ) : (
          <>
            <Loader2 className="text-neon-amber animate-spin" size={14} />
            <span className="text-xs font-mono text-neon-amber">PROCESSING...</span>
          </>
        )}
      </div>
    </motion.div>
  )
}
