import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1/pipeline',
  timeout: 30000,
})

const dataApi = axios.create({
  baseURL: '/api/v1/data',
  timeout: 30000,
})

export interface PipelineStartParams {
  mode: 'test' | 'prod'
  platforms: string[]
  login_type: 'qrcode' | 'phone' | 'cookie'
  headless: boolean
  schedule: string | null
}

export interface PipelineStatusResult {
  status: 'idle' | 'running' | 'stopping' | 'completed' | 'failed'
  started_at: string | null
  completed_at: string | null
  params: Record<string, unknown>
  exit_code: number | null
  log_line_count: number
}

/** Start the pipeline */
export async function startPipeline(params: PipelineStartParams) {
  const { data } = await api.post('/start', params)
  return data
}

/** Stop the running pipeline */
export async function stopPipeline() {
  const { data } = await api.post('/stop')
  return data
}

/** Get current pipeline status */
export async function getPipelineStatus(): Promise<PipelineStatusResult> {
  const { data } = await api.get('/status')
  return data
}

/** Build WebSocket URL for log streaming */
export function getLogWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/v1/pipeline/ws/logs`
}

// ── Cleaned Data API ──────────────────────────────────────────

export interface CleanedFileInfo {
  filename: string
  platform: string
  platform_label: string
  keyword: string
  task_id: number | null
  cleaned_count: number | null
  generated_at: string | null
  file_size: number
}

export interface CleanedFileListResult {
  platforms: { value: string; label: string; count: number }[]
  files: CleanedFileInfo[]
  total: number
}

/** List cleaned data files with optional filters */
export async function listCleanedFiles(
  platform?: string,
  keyword?: string,
): Promise<CleanedFileListResult> {
  const params: Record<string, string> = {}
  if (platform) params.platform = platform
  if (keyword) params.keyword = keyword
  const { data } = await dataApi.get('/cleaned/files', { params })
  return data
}

/** Get content of a specific cleaned file */
export async function getCleanedFileContent(
  platform: string,
  filename: string,
): Promise<any> {
  const { data } = await dataApi.get('/cleaned/content', {
    params: { platform, filename },
  })
  return data
}
