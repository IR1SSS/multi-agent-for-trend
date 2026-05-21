<template>
  <el-dialog
    v-model="visible"
    title="Cleaned Data Preview"
    width="75%"
    top="5vh"
    :close-on-click-modal="false"
    destroy-on-close
    class="data-preview-dialog"
  >
    <!-- Filters -->
    <div class="filter-bar">
      <el-select
        v-model="selectedPlatform"
        placeholder="All Platforms"
        clearable
        style="width: 160px"
        @change="fetchFiles"
      >
        <el-option
          v-for="p in platformOptions"
          :key="p.value"
          :label="`${p.label} (${p.count})`"
          :value="p.value"
        />
      </el-select>
      <el-input
        v-model="keywordFilter"
        placeholder="Search keyword"
        clearable
        style="width: 200px"
        :prefix-icon="Search"
        @input="debouncedFetch"
      />
      <span class="total-label">{{ total }} file(s)</span>
    </div>

    <!-- File List -->
    <el-table
      v-loading="loading"
      :data="files"
      highlight-current-row
      max-height="320"
      @row-click="handleRowClick"
      style="width: 100%"
    >
      <el-table-column label="Platform" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="platformTagType(row.platform)" size="small" effect="plain">
            {{ row.platform_label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="keyword" label="Keyword" min-width="120" show-overflow-tooltip />
      <el-table-column label="Count" width="90" align="center">
        <template #default="{ row }">
          {{ row.cleaned_count ?? '-' }}
        </template>
      </el-table-column>
      <el-table-column label="Size" width="90" align="center">
        <template #default="{ row }">
          {{ formatSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column label="Generated" width="170">
        <template #default="{ row }">
          {{ formatTime(row.generated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="Action" width="100" align="center">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click.stop="previewFile(row)">
            View
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- File Content Preview -->
    <div v-if="previewData" class="preview-section">
      <div class="preview-header">
        <h4>
          <el-icon><Document /></el-icon>
          {{ previewMeta.keyword }}
          <el-tag size="small" effect="plain" style="margin-left: 8px">
            {{ previewMeta.platform_label }}
          </el-tag>
        </h4>
        <span class="preview-info">
          {{ previewMeta.cleaned_count }} records · {{ formatTime(previewMeta.generated_at) }}
        </span>
      </div>

      <!-- Tab view: Table / JSON -->
      <el-tabs v-model="previewTab">
        <el-tab-pane label="Structured View" name="table">
          <el-table :data="previewData.data" max-height="360" stripe style="width: 100%">
            <el-table-column type="index" label="#" width="40" />
            <el-table-column prop="source_type" label="Type" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.source_type === 'video' ? 'danger' : 'primary'">
                  {{ row.source_type === 'video' ? 'Video' : 'Post' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="Title" min-width="220" show-overflow-tooltip />
            <el-table-column prop="summary" label="Summary" min-width="200" show-overflow-tooltip />
            <el-table-column prop="sentiment" label="Sentiment" width="80" align="center">
              <template #default="{ row }">
                <span :class="sentimentClass(row.sentiment)">{{ sentimentLabel(row.sentiment) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="trend_score" label="Score" width="90" align="right">
              <template #default="{ row }">
                {{ row.trend_score?.toLocaleString() ?? '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="topics" label="Topics" min-width="150" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="Raw JSON" name="json">
          <pre class="json-preview">{{ formatJson(previewData) }}</pre>
        </el-tab-pane>
      </el-tabs>
    </div>

    <div v-else-if="!loading" class="empty-hint">
      Click a row or the "View" button to preview data
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, Document } from '@element-plus/icons-vue'
import {
  listCleanedFiles,
  getCleanedFileContent,
  type CleanedFileInfo,
  type CleanedFileListResult,
} from '../api/pipeline'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [val: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

import { computed } from 'vue'

// ── State ─────────────────────────────────────────────────────
const loading = ref(false)
const files = ref<CleanedFileInfo[]>([])
const total = ref(0)
const platformOptions = ref<{ value: string; label: string; count: number }[]>([])
const selectedPlatform = ref<string | undefined>(undefined)
const keywordFilter = ref('')
const previewData = ref<any>(null)
const previewMeta = ref<any>({})
const previewTab = ref('table')

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function debouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchFiles, 300)
}

// ── Fetch file list ──────────────────────────────────────────
async function fetchFiles() {
  loading.value = true
  try {
    const result: CleanedFileListResult = await listCleanedFiles(
      selectedPlatform.value || undefined,
      keywordFilter.value || undefined,
    )
    files.value = result.files
    total.value = result.total
    if (result.platforms.length && !platformOptions.value.length) {
      platformOptions.value = result.platforms
    }
    // Always refresh platform counts
    platformOptions.value = result.platforms
  } catch {
    // ignore
  } finally {
    loading.value = false
  }
}

// ── Preview a file ───────────────────────────────────────────
async function previewFile(row: CleanedFileInfo) {
  try {
    const content = await getCleanedFileContent(row.platform, row.filename)
    previewData.value = content
    previewMeta.value = row
    previewTab.value = 'table'
  } catch {
    previewData.value = null
  }
}

function handleRowClick(row: CleanedFileInfo) {
  previewFile(row)
}

// ── Formatters ───────────────────────────────────────────────

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(iso?: string | null): string {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleString('en-US', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatJson(obj: any): string {
  return JSON.stringify(obj, null, 2)
}

function platformTagType(p: string): string {
  const map: Record<string, string> = { dy: 'danger', xhs: 'warning', bili: 'primary', wb: 'success' }
  return map[p] || 'info'
}

function sentimentLabel(s: string): string {
  const map: Record<string, string> = { positive: 'Positive', neutral: 'Neutral', negative: 'Negative' }
  return map[s] || s
}

function sentimentClass(s: string): string {
  const map: Record<string, string> = { positive: 'sentiment-positive', neutral: 'sentiment-neutral', negative: 'sentiment-negative' }
  return map[s] || ''
}

// ── Lifecycle ────────────────────────────────────────────────

watch(visible, (v) => {
  if (v) {
    selectedPlatform.value = undefined
    keywordFilter.value = ''
    previewData.value = null
    fetchFiles()
  }
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.total-label {
  font-size: 13px;
  color: #909399;
  margin-left: auto;
}

.preview-section {
  margin-top: 20px;
  border-top: 1px solid #ebeef5;
  padding-top: 16px;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.preview-header h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 16px;
  color: #303133;
}

.preview-info {
  font-size: 13px;
  color: #909399;
}

.json-preview {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 16px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.empty-hint {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
  font-size: 14px;
}

.sentiment-positive { color: #67c23a; font-weight: 500; }
.sentiment-neutral { color: #909399; }
.sentiment-negative { color: #f56c6c; font-weight: 500; }
</style>
