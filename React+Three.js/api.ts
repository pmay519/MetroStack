// API response types matching backend schemas

export interface Project {
  id: string
  name: string
  description: string | null
  part_number: string | null
  revision: string | null
  status: 'pending' | 'ready' | 'aligned' | 'analyzed' | 'error'
  created_at: string
  updated_at: string
  has_cad: boolean
  has_scan: boolean
  has_alignment: boolean
}

export interface CADModel {
  id: string
  project_id: string
  filename: string
  file_format: string
  file_size_bytes: number
  vertex_count: number | null
  face_count: number | null
  is_watertight: boolean | null
  bbox_min_x: number | null
  bbox_min_y: number | null
  bbox_min_z: number | null
  bbox_max_x: number | null
  bbox_max_y: number | null
  bbox_max_z: number | null
  repair_log: string | null
  is_processed: boolean
  uploaded_at: string
}

export interface ScanCloud {
  id: string
  project_id: string
  filename: string
  file_format: string
  file_size_bytes: number
  point_count: number | null
  has_normals: boolean | null
  has_intensity: boolean | null
  has_rgb: boolean | null
  bbox_min_x: number | null
  bbox_min_y: number | null
  bbox_min_z: number | null
  bbox_max_x: number | null
  bbox_max_y: number | null
  bbox_max_z: number | null
  units: string | null
  is_processed: boolean
  uploaded_at: string
}

export interface Alignment {
  id: string
  project_id: string
  method: 'icp' | 'fgr' | 'datum_locked' | 'manual'
  transform_matrix: string  // 16 comma-separated floats
  inlier_rmse_mm: number | null
  fitness_score: number | null
  inlier_count: number | null
  iteration_count: number | null
  datum_constraints: string | null
  created_at: string
}

export interface AnalysisJob {
  id: string
  project_id: string
  analysis_type: 'deviation' | 'gdt' | 'wall_thickness' | 'cross_section'
  status: 'queued' | 'running' | 'complete' | 'failed'
  celery_task_id: string | null
  progress_pct: number
  progress_msg: string | null
  error_message: string | null
  parameters: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface DeviationStats {
  min_mm: number
  max_mm: number
  mean_mm: number
  rms_mm: number
  p95_mm: number
  p99_mm: number
  point_count: number
  scale_min_mm: number
  scale_max_mm: number
}

export interface DeviationData {
  x: number[]
  y: number[]
  z: number[]
  deviation_mm: number[]
  stats: DeviationStats
}

export type GDTFeatureType =
  | 'flatness'
  | 'straightness'
  | 'circularity'
  | 'cylindricity'
  | 'position'
  | 'parallelism'
  | 'perpendicularity'
  | 'angularity'
  | 'profile_surface'
  | 'runout'
  | 'total_runout'

export interface GDTFeature {
  id: string
  project_id: string
  name: string
  feature_type: GDTFeatureType
  nominal_x: number | null
  nominal_y: number | null
  nominal_z: number | null
  nominal_diameter: number | null
  roi_min_x: number | null
  roi_min_y: number | null
  roi_min_z: number | null
  roi_max_x: number | null
  roi_max_y: number | null
  roi_max_z: number | null
  primary_datum: string | null
  secondary_datum: string | null
  tertiary_datum: string | null
  tolerance_upper_mm: number | null
  tolerance_lower_mm: number | null
  created_at: string
}

export interface GDTResult {
  id: string
  project_id: string
  feature_id: string
  job_id: string
  actual_value_mm: number
  nominal_value_mm: number | null
  deviation_mm: number | null
  in_tolerance: boolean
  fit_center_x: number | null
  fit_center_y: number | null
  fit_center_z: number | null
  fit_normal_x: number | null
  fit_normal_y: number | null
  fit_normal_z: number | null
  fit_radius: number | null
  fit_residual_rms: number | null
  point_count_used: number | null
  created_at: string
  feature_name: string | null
  feature_type: GDTFeatureType | null
  tolerance_upper_mm: number | null
  tolerance_lower_mm: number | null
}

export interface WallThicknessStats {
  min_mm: number
  max_mm: number
  mean_mm: number
  std_mm: number
  sample_count: number
}

export interface WallThicknessData {
  x: number[]
  y: number[]
  z: number[]
  thickness_mm: number[]
  stats: WallThicknessStats
}

// Request types
export interface CreateProjectRequest {
  name: string
  description?: string
  part_number?: string
  revision?: string
}

export interface AlignmentRequest {
  method?: 'icp' | 'fgr' | 'datum_locked' | 'manual'
  manual_matrix?: number[]
  datum_constraints?: Record<string, any>
  max_correspondence_dist_mm?: number
  max_iterations?: number
}

export interface DeviationRequest {
  scale_min_mm?: number
  scale_max_mm?: number
  downsample_to?: number
}

export interface CreateGDTFeatureRequest {
  name: string
  feature_type: GDTFeatureType
  nominal_x?: number
  nominal_y?: number
  nominal_z?: number
  nominal_diameter?: number
  roi_min_x?: number
  roi_min_y?: number
  roi_min_z?: number
  roi_max_x?: number
  roi_max_y?: number
  roi_max_z?: number
  primary_datum?: string
  secondary_datum?: string
  tertiary_datum?: string
  tolerance_upper_mm?: number
  tolerance_lower_mm?: number
}

export interface WallThicknessRequest {
  sample_count?: number
}

export interface JobStartedResponse {
  job_id: string
  status: string
  message: string
}
