import axios from 'axios'

const domainApi = axios.create({
  baseURL: '/api/v1/domains',
  timeout: 15000,
})

export interface SkillConfig {
  [key: string]: any
}

export interface DomainConfig {
  id: number
  domain: string
  display_name: string
  domain_description: string
  status: 'active' | 'archived'
  expander_skill: SkillConfig
  cleaning_skill: SkillConfig
  insight_skill: SkillConfig
  created_at: string
  updated_at: string
}

export interface DomainCreateRequest {
  domain: string
  display_name: string
  domain_description?: string
  status?: 'active' | 'archived'
  expander_skill?: SkillConfig
  cleaning_skill?: SkillConfig
  insight_skill?: SkillConfig
}

export interface ActiveDomainResult {
  active_domain_id: number | null
}

/** List all domains */
export async function listDomains(status?: string): Promise<DomainConfig[]> {
  const params: Record<string, string> = {}
  if (status) params.status = status
  const { data } = await domainApi.get('', { params })
  return data
}

/** Get a single domain by ID */
export async function getDomain(domainId: number): Promise<DomainConfig> {
  const { data } = await domainApi.get(`/${domainId}`)
  return data
}

/** Create a new domain */
export async function createDomain(
  body: DomainCreateRequest,
  autoGenerateKeywords = true,
): Promise<DomainConfig> {
  const { data } = await domainApi.post('', body, {
    params: { auto_generate_keywords: autoGenerateKeywords },
  })
  return data
}

/** Update a domain */
export async function updateDomain(
  domainId: number,
  body: Partial<DomainCreateRequest>,
): Promise<DomainConfig> {
  const { data } = await domainApi.put(`/${domainId}`, body)
  return data
}

/** Archive (soft-delete) a domain */
export async function archiveDomain(domainId: number): Promise<void> {
  await domainApi.delete(`/${domainId}`)
}

/** Activate a domain as the current active domain */
export async function activateDomain(domainId: number): Promise<ActiveDomainResult> {
  const { data } = await domainApi.post(`/${domainId}/activate`)
  return data
}

/** Get the currently active domain */
export async function getActiveDomain(): Promise<ActiveDomainResult> {
  const { data } = await domainApi.get('/active')
  return data
}

/** Generate keywords for a domain via LLM */
export async function generateKeywords(
  domainId: number,
  numKeywords = 15,
): Promise<{ success: boolean; keywords_generated: number; keywords: any[] }> {
  const { data } = await domainApi.post(
    `/${domainId}/generate-keywords`,
    null,
    { params: { num_keywords: numKeywords } },
  )
  return data
}

/** Import keywords from CSV file */
export async function importKeywords(
  domainId: number,
  file: File,
): Promise<{ success: boolean; keywords_imported: number; keywords: any[] }> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await domainApi.post(
    `/${domainId}/import-keywords`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 30000 },
  )
  return data
}

/** Get keywords for a domain */
export async function getDomainKeywords(
  domainId: number,
  activeOnly = true,
): Promise<{ domain_id: number; keywords: any[]; total: number }> {
  const { data } = await domainApi.get(`/${domainId}/keywords`, {
    params: { active_only: activeOnly },
  })
  return data
}
