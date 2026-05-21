<template>
  <div class="domain-management">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: 600;">Domain Management</span>
          <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
            New Domain
          </el-button>
        </div>
      </template>

      <el-table :data="domains" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="domain" label="Domain" width="180" />
        <el-table-column prop="display_name" label="Display Name" width="150" />
        <el-table-column label="Description" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.domain_description || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="Status" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Expander" width="120">
          <template #default="{ row }">
            {{ row.expander_skill?.strategy || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Cleaning" width="120">
          <template #default="{ row }">
            {{ row.cleaning_skill?.strategy || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Insight" width="120">
          <template #default="{ row }">
            {{ row.insight_skill?.strategy || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="Actions" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openDetail(row)">Detail</el-button>
            <el-button size="small" type="success" @click="handleActivate(row.id)" :disabled="row.id === activeDomainId">
              Activate
            </el-button>
            <el-button size="small" type="danger" @click="handleArchive(row)" :disabled="row.id === activeDomainId">
              Archive
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create Domain Dialog -->
    <el-dialog v-model="showCreateDialog" title="Create Domain" width="650px">
      <el-form :model="createForm" label-width="150px">
        <el-form-item label="Domain ID">
          <el-input v-model="createForm.domain" placeholder="e.g. new_energy_vehicle" />
        </el-form-item>
        <el-form-item label="Display Name">
          <el-input v-model="createForm.display_name" placeholder="e.g. New Energy Vehicle" />
        </el-form-item>
        <el-form-item label="Domain Description">
          <el-input
            v-model="createForm.domain_description"
            type="textarea"
            :rows="3"
            placeholder="Describe the domain for LLM-based skill inference, e.g. '新能源汽车行业，关注电池技术、智能驾驶、充电基础设施'"
          />
        </el-form-item>
        <el-form-item label="Expander Strategy">
          <el-select v-model="createForm.expander_skill.strategy">
            <el-option label="Adaptive (Auto-infer levels)" value="adaptive" />
            <el-option label="Hierarchical (Mature industries)" value="hierarchical" />
            <el-option label="Tech Term (Emerging industries)" value="tech_term" />
          </el-select>
        </el-form-item>
        <el-form-item label="Cleaning Strategy">
          <el-select v-model="createForm.cleaning_skill.strategy">
            <el-option label="Adaptive (Auto-infer entities)" value="adaptive" />
            <el-option label="Ontology Cleaner (Pre-defined entities)" value="ontology_cleaner" />
          </el-select>
        </el-form-item>
        <el-form-item label="Insight Strategy">
          <el-select v-model="createForm.insight_skill.strategy">
            <el-option label="Adaptive (Auto-infer report)" value="adaptive" />
            <el-option label="Report Generator" value="report_generator" />
            <el-option label="Statistics" value="statistics" />
          </el-select>
        </el-form-item>
        <el-form-item label="Auto-generate Keywords">
          <el-switch v-model="createForm.auto_generate_keywords" />
          <span style="margin-left: 8px; color: #909399; font-size: 13px;">
            Generate seed keywords via LLM after creation
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">Cancel</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">Create</el-button>
      </template>
    </el-dialog>

    <!-- Domain Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="Domain Detail" width="750px">
      <template v-if="selectedDomain">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ selectedDomain.id }}</el-descriptions-item>
          <el-descriptions-item label="Domain">{{ selectedDomain.domain }}</el-descriptions-item>
          <el-descriptions-item label="Display Name">{{ selectedDomain.display_name }}</el-descriptions-item>
          <el-descriptions-item label="Status">{{ selectedDomain.status }}</el-descriptions-item>
          <el-descriptions-item label="Description" :span="2">
            {{ selectedDomain.domain_description || 'No description' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-tabs style="margin-top: 16px;">
          <el-tab-pane label="Keywords">
            <div style="margin-bottom: 12px; display: flex; gap: 8px;">
              <el-button type="primary" size="small" :loading="generatingKeywords" @click="handleGenerateKeywords">
                Generate Keywords
              </el-button>
              <el-upload
                :auto-upload="false"
                :show-file-list="false"
                accept=".csv"
                :on-change="handleImportCSV"
              >
                <el-button type="warning" size="small" :loading="importingKeywords">Import CSV</el-button>
              </el-upload>
              <el-button size="small" @click="fetchKeywords">Refresh</el-button>
            </div>
            <el-table :data="keywords" stripe max-height="300" size="small">
              <el-table-column prop="keyword_id" label="ID" width="100" />
              <el-table-column prop="keyword" label="Keyword" min-width="150" />
              <el-table-column prop="topic_cluster" label="Cluster" width="140" />
              <el-table-column prop="trend_type" label="Type" width="100" />
              <el-table-column prop="suggested_platforms" label="Platforms" width="140" />
              <el-table-column prop="source_scope" label="Source" width="100" />
            </el-table>
            <div style="margin-top: 8px; color: #909399; font-size: 13px;">
              Total: {{ keywords.length }} keywords
            </div>
          </el-tab-pane>
          <el-tab-pane label="Expander Skill">
            <pre class="skill-json">{{ JSON.stringify(selectedDomain.expander_skill, null, 2) }}</pre>
          </el-tab-pane>
          <el-tab-pane label="Cleaning Skill">
            <pre class="skill-json">{{ JSON.stringify(selectedDomain.cleaning_skill, null, 2) }}</pre>
          </el-tab-pane>
          <el-tab-pane label="Insight Skill">
            <pre class="skill-json">{{ JSON.stringify(selectedDomain.insight_skill, null, 2) }}</pre>
          </el-tab-pane>
        </el-tabs>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, inject } from 'vue'
import type { Ref } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import {
  listDomains,
  createDomain,
  activateDomain,
  archiveDomain,
  getActiveDomain,
  generateKeywords,
  importKeywords,
  getDomainKeywords,
  type DomainConfig,
} from '../api/domain'

const domains = ref<DomainConfig[]>([])
const activeDomainId = ref<number | null>(null)
const showCreateDialog = ref(false)
const showDetailDialog = ref(false)
const selectedDomain = ref<DomainConfig | null>(null)
const creating = ref(false)
const generatingKeywords = ref(false)
const importingKeywords = ref(false)
const keywords = ref<any[]>([])

// Notify sibling DomainSwitcher to refresh
const domainRefreshKey = inject<Ref<number>>('domainRefreshKey', ref(0))
function notifyDomainChange() {
  domainRefreshKey.value++
}

const createForm = reactive({
  domain: '',
  display_name: '',
  domain_description: '',
  expander_skill: { strategy: 'adaptive' as string },
  cleaning_skill: { strategy: 'adaptive' as string },
  insight_skill: { strategy: 'adaptive' as string },
  auto_generate_keywords: true,
})

async function fetchDomains() {
  try {
    domains.value = await listDomains()
  } catch (e) {
    ElMessage.error('Failed to load domains')
  }
}

async function fetchActiveDomain() {
  try {
    const result = await getActiveDomain()
    activeDomainId.value = result.active_domain_id
  } catch (e) {
    // Ignore - Redis may not be configured yet
  }
}

async function fetchKeywords() {
  if (!selectedDomain.value) return
  try {
    const result = await getDomainKeywords(selectedDomain.value.id)
    keywords.value = result.keywords
  } catch (e) {
    ElMessage.error('Failed to load keywords')
  }
}

async function handleCreate() {
  if (!createForm.domain || !createForm.display_name) {
    ElMessage.warning('Domain ID and Display Name are required')
    return
  }
  creating.value = true
  try {
    await createDomain(
      {
        domain: createForm.domain,
        display_name: createForm.display_name,
        domain_description: createForm.domain_description,
        expander_skill: createForm.expander_skill,
        cleaning_skill: createForm.cleaning_skill,
        insight_skill: createForm.insight_skill,
      },
      createForm.auto_generate_keywords,
    )
    ElMessage.success('Domain created')
    showCreateDialog.value = false
    // Reset form
    createForm.domain = ''
    createForm.display_name = ''
    createForm.domain_description = ''
    createForm.expander_skill.strategy = 'adaptive'
    createForm.cleaning_skill.strategy = 'adaptive'
    createForm.insight_skill.strategy = 'adaptive'
    createForm.auto_generate_keywords = true
    await fetchDomains()
    notifyDomainChange()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to create domain')
  } finally {
    creating.value = false
  }
}

async function handleActivate(domainId: number) {
  try {
    await activateDomain(domainId)
    activeDomainId.value = domainId
    ElMessage.success('Domain activated')
  } catch (e) {
    ElMessage.error('Failed to activate domain')
  }
}

async function handleArchive(domain: DomainConfig) {
  try {
    await ElMessageBox.confirm(
      `Archive domain "${domain.display_name}"? This is a soft delete.`,
      'Confirm Archive',
    )
    await archiveDomain(domain.id)
    ElMessage.success('Domain archived')
    await fetchDomains()
    notifyDomainChange()
  } catch {
    // User cancelled
  }
}

async function handleGenerateKeywords() {
  if (!selectedDomain.value) return
  generatingKeywords.value = true
  try {
    const result = await generateKeywords(selectedDomain.value.id)
    ElMessage.success(`Generated ${result.keywords_generated} keywords`)
    await fetchKeywords()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to generate keywords')
  } finally {
    generatingKeywords.value = false
  }
}

async function handleImportCSV(uploadFile: UploadFile) {
  if (!selectedDomain.value || !uploadFile.raw) return
  importingKeywords.value = true
  try {
    const result = await importKeywords(selectedDomain.value.id, uploadFile.raw)
    ElMessage.success(`Imported ${result.keywords_imported} keywords`)
    await fetchKeywords()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || 'Failed to import keywords')
  } finally {
    importingKeywords.value = false
  }
}

function openDetail(domain: DomainConfig) {
  selectedDomain.value = domain
  showDetailDialog.value = true
  keywords.value = []
  fetchKeywords()
}

onMounted(async () => {
  await Promise.all([fetchDomains(), fetchActiveDomain()])
})
</script>

<style scoped>
.domain-management {
  padding: 20px;
}
.skill-json {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.5;
  overflow-x: auto;
}
</style>