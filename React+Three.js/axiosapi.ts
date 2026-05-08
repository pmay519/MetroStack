import axios from 'axios'
import type * as API from '@/types/api'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// ── Projects ──────────────────────────────────────────────────────────────────

export const projectsAPI = {
  list: async () => {
    const { data } = await api.get<{ items: API.Project[]; total: number }>('/projects')
    return data
  },

  get: async (id: string) => {
    const { data } = await api.get<API.Project>(`/projects/${id}`)
    return data
  },

  create: async (payload: API.CreateProjectRequest) => {
    const { data } = await api.post<API.Project>('/projects', payload)
    return data
  },

  update: async (id: string, payload: Partial<API.CreateProjectRequest>) => {
    const { data } = await api.patch<API.Project>(`/projects/${id}`, payload)
    return data
  },

  delete: async (id: string) => {
    await api.delete(`/projects/${id}`)
  },
}

// ── File Upload ───────────────────────────────────────────────────────────────

export const uploadAPI = {
  uploadCAD: async (projectId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<API.CADModel>(
      `/projects/${projectId}/upload-cad`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    )
    return data
  },

  uploadScan: async (projectId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post<API.ScanCloud>(
      `/projects/${projectId}/upload-scan`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    )
    return data
  },

  getCADInfo: async (projectId: string) => {
    const { data } = await api.get<API.CADModel>(`/projects/${projectId}/cad`)
    return data
  },

  getScanInfo: async (projectId: string) => {
    const { data } = await api.get<API.ScanCloud>(`/projects/${projectId}/scan`)
    return data
  },

  deleteCAD: async (projectId: string) => {
    await api.delete(`/projects/${projectId}/cad`)
  },

  deleteScan: async (projectId: string) => {
    await api.delete(`/projects/${projectId}/scan`)
  },
}

// ── Analysis ──────────────────────────────────────────────────────────────────

export const analysisAPI = {
  // Alignment
  align: async (projectId: string, payload: API.AlignmentRequest) => {
    const { data } = await api.post<API.JobStartedResponse>(
      `/projects/${projectId}/align`,
      payload
    )
    return data
  },

  getAlignment: async (projectId: string) => {
    const { data } = await api.get<API.Alignment>(`/projects/${projectId}/alignment`)
    return data
  },

  // Deviation
  analyzeDeviation: async (projectId: string, payload: API.DeviationRequest = {}) => {
    const { data } = await api.post<API.JobStartedResponse>(
      `/projects/${projectId}/analyze/deviation`,
      payload
    )
    return data
  },

  getDeviationResults: async (projectId: string, downsampleTo = 500_000) => {
    const { data } = await api.get<API.DeviationData>(
      `/projects/${projectId}/results/deviation`,
      { params: { downsample_to: downsampleTo } }
    )
    return data
  },

  // GD&T
  createGDTFeature: async (projectId: string, payload: API.CreateGDTFeatureRequest) => {
    const { data } = await api.post<API.GDTFeature>(
      `/projects/${projectId}/gdt/features`,
      payload
    )
    return data
  },

  listGDTFeatures: async (projectId: string) => {
    const { data } = await api.get<API.GDTFeature[]>(`/projects/${projectId}/gdt/features`)
    return data
  },

  deleteGDTFeature: async (projectId: string, featureId: string) => {
    await api.delete(`/projects/${projectId}/gdt/features/${featureId}`)
  },

  analyzeGDT: async (projectId: string, featureIds?: string[]) => {
    const { data } = await api.post<API.JobStartedResponse>(
      `/projects/${projectId}/analyze/gdt`,
      { feature_ids: featureIds }
    )
    return data
  },

  getGDTResults: async (projectId: string) => {
    const { data } = await api.get<API.GDTResult[]>(`/projects/${projectId}/results/gdt`)
    return data
  },

  // Wall Thickness
  analyzeWallThickness: async (
    projectId: string,
    payload: API.WallThicknessRequest = {}
  ) => {
    const { data } = await api.post<API.JobStartedResponse>(
      `/projects/${projectId}/analyze/wall-thickness`,
      payload
    )
    return data
  },

  getWallThicknessResults: async (projectId: string, downsampleTo = 50_000) => {
    const { data } = await api.get<API.WallThicknessData>(
      `/projects/${projectId}/results/wall-thickness`,
      { params: { downsample_to: downsampleTo } }
    )
    return data
  },
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export const jobsAPI = {
  list: async (projectId: string) => {
    const { data } = await api.get<API.AnalysisJob[]>(`/projects/${projectId}/jobs`)
    return data
  },

  get: async (projectId: string, jobId: string) => {
    const { data } = await api.get<API.AnalysisJob>(`/projects/${projectId}/jobs/${jobId}`)
    return data
  },
}

export default api
