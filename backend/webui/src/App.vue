<template>
  <div class="app-container">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <h1 class="app-title">
          <el-icon :size="28" color="#409eff"><TrendCharts /></el-icon>
          Trend Pipeline Console
        </h1>
        <span class="app-subtitle">Multi-Agent Trend Pipeline</span>
      </div>
      <div class="header-right">
        <DomainSwitcher />
        <el-button :icon="Setting" size="small" @click="showDomainManagement = true">Domains</el-button>
        <el-tag :type="wsConnected ? 'success' : 'danger'" effect="plain" round>
          <el-icon><Connection /></el-icon>
          {{ wsConnected ? 'WebSocket Connected' : 'WebSocket Disconnected' }}
        </el-tag>
      </div>
    </header>

    <!-- Status Bar -->
    <StatusBar :statusDetail="pipelineStatus" />

    <!-- Main Content -->
    <div class="main-layout">
      <!-- Left: Config Panel -->
      <div class="left-panel">
        <PipelineConfig
          :disabled="isRunning"
          :isRunning="isRunning"
          :starting="starting"
          :stopping="stopping"
          :initialParams="pipelineStatus.params as any"
          @start="handleStart"
          @stop="handleStop"
          @refreshStatus="fetchStatus"
          @previewData="showDataPreview = true"
        />

        <!-- Quick Info -->
        <div class="info-card" v-if="isRunning">
          <h4><el-icon><InfoFilled /></el-icon> Run Info</h4>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Mode</span>
              <span class="info-value">{{ (pipelineStatus.params as any)?.mode === 'test' ? 'Test' : 'Production' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Platform</span>
              <span class="info-value">{{ formatPlatforms((pipelineStatus.params as any)?.platforms) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Login</span>
              <span class="info-value">{{ loginTypeLabel((pipelineStatus.params as any)?.login_type) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Schedule</span>
              <span class="info-value">{{ scheduleLabel((pipelineStatus.params as any)?.schedule) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Terminal -->
      <div class="right-panel">
        <TerminalLog :logs="logLines" />
      </div>
    </div>

    <!-- Data Preview Dialog -->
    <DataPreview v-model="showDataPreview" />

    <!-- Domain Management Dialog -->
    <el-dialog v-model="showDomainManagement" title="Domain Management" width="900px" :close-on-click-modal="false">
      <DomainManagement />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { TrendCharts, Connection, InfoFilled, Setting } from '@element-plus/icons-vue'
import StatusBar from './components/StatusBar.vue'
import DomainSwitcher from './components/DomainSwitcher.vue'
import DomainManagement from './components/DomainManagement.vue'
import PipelineConfig from './components/PipelineConfig.vue'
import TerminalLog from './components/TerminalLog.vue'
import DataPreview from './components/DataPreview.vue'
import {
  startPipeline,
  stopPipeline,
  getPipelineStatus,
  getLogWsUrl,
  type PipelineStartParams,
  type PipelineStatusResult,
} from './api/pipeline'

// ── State ──────────────────────────────────────────────────────

const pipelineStatus = ref<PipelineStatusResult>({
  status: 'idle',
  started_at: null,
  completed_at: null,
  params: {},
  exit_code: null,
  log_line_count: 0,
})

const logLines = ref<string[]>([])
const starting = ref(false)
const stopping = ref(false)
const wsConnected = ref(false)
const showDataPreview = ref(false)
const showDomainManagement = ref(false)

// Shared refresh trigger for domain list changes across sibling components
const domainRefreshKey = ref(0)
provide('domainRefreshKey', domainRefreshKey)

let ws: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let pingTimer: ReturnType<typeof setInterval> | null = null

// ── Computed ───────────────────────────────────────────────────

const isRunning = computed(() =>
  pipelineStatus.value.status === 'running' || pipelineStatus.value.status === 'stopping'
)

// ── API Actions ────────────────────────────────────────────────

async function fetchStatus() {
  try {
    pipelineStatus.value = await getPipelineStatus()
  } catch {
    // Backend may not be running yet
  }
}

async function handleStart(params: PipelineStartParams) {
  if (params.platforms.length === 0) {
    ElMessage.warning('Please select at least one platform')
    return
  }

  try {
    await ElMessageBox.confirm(
      `About to start pipeline in ${params.mode === 'test' ? 'Test' : 'Production'} mode, ` +
      `Platforms: ${formatPlatforms(params.platforms)}, ` +
      `Login: ${loginTypeLabel(params.login_type)}. ` +
      (params.mode === 'test' ? '' : 'Production mode will process all keywords.'),
      'Confirm Start',
      { confirmButtonText: 'Start', cancelButtonText: 'Cancel', type: 'info' }
    )
  } catch {
    return // User cancelled
  }

  starting.value = true
  logLines.value = []

  try {
    const result = await startPipeline(params)
    ElMessage.success(`Pipeline started (PID: ${result.pid})`)
    // Ensure WebSocket is connected — reconnect if needed
    if (!wsConnected.value) {
      connectWebSocket()
    } else if (ws && ws.readyState !== WebSocket.OPEN) {
      // Connection stale, reconnect
      disconnectWebSocket()
      connectWebSocket()
    }
    await fetchStatus()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.response?.data?.error || err.message || 'Start failed'
    ElMessage.error(msg)
  } finally {
    starting.value = false
  }
}

async function handleStop() {
  try {
    await ElMessageBox.confirm(
      'Are you sure you want to stop the running pipeline? Active crawl tasks will be terminated.',
      'Confirm Stop',
      { confirmButtonText: 'Stop', cancelButtonText: 'Cancel', type: 'warning' }
    )
  } catch {
    return
  }

  stopping.value = true
  try {
    await stopPipeline()
    ElMessage.success('Pipeline stopped')
    await fetchStatus()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.response?.data?.error || err.message || 'Stop failed'
    ElMessage.error(msg)
  } finally {
    stopping.value = false
  }
}

// ── WebSocket ──────────────────────────────────────────────────

function connectWebSocket() {
  if (ws && ws.readyState === WebSocket.OPEN) return

  const url = getLogWsUrl()
  ws = new WebSocket(url)

  ws.onopen = () => {
    wsConnected.value = true
    // Send periodic pings
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000)
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      if (msg.type === 'log') {
        logLines.value.push(msg.line)
        // Keep buffer bounded
        if (logLines.value.length > 5000) {
          logLines.value = logLines.value.slice(-3000)
        }
      } else if (msg.type === 'status') {
        fetchStatus()
        if (msg.status === 'completed') {
          ElMessage.success('Pipeline completed')
        } else if (msg.status === 'failed') {
          ElMessage.error(`Pipeline failed${msg.message ? ': ' + msg.message : ''}`)
        } else if (msg.status === 'stopped') {
          ElMessage.warning('Pipeline stopped by user')
        }
      }
    } catch {
      // Non-JSON message, treat as raw log
      logLines.value.push(event.data)
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    if (pingTimer) clearInterval(pingTimer)
    // Auto-reconnect after 3 seconds
    reconnectTimer = setTimeout(() => {
      if (isRunning.value) {
        connectWebSocket()
      }
    }, 3000)
  }

  ws.onerror = () => {
    wsConnected.value = false
  }
}

function disconnectWebSocket() {
  if (reconnectTimer) clearTimeout(reconnectTimer)
  if (pingTimer) clearInterval(pingTimer)
  if (ws) {
    ws.onclose = null // Prevent auto-reconnect
    ws.close()
    ws = null
  }
  wsConnected.value = false
}

// ── Formatters ─────────────────────────────────────────────────

const PLATFORM_NAMES: Record<string, string> = {
  xhs: 'Xiaohongshu',
  dy: 'Douyin',
  bili: 'Bilibili',
  wb: 'Weibo',
}

function formatPlatforms(platforms?: string[]): string {
  if (!platforms || platforms.length === 0) return '-'
  return platforms.map(p => PLATFORM_NAMES[p] || p).join(', ')
}

function loginTypeLabel(type?: string): string {
  const map: Record<string, string> = {
    qrcode: 'QR Code',
    phone: 'Phone',
    cookie: 'Cookie',
  }
  return map[type || ''] || type || '-'
}

function scheduleLabel(schedule?: string | null): string {
  if (!schedule) return 'Once'
  const map: Record<string, string> = {
    daily: 'Daily',
    weekly: 'Weekly',
    monthly: 'Monthly',
  }
  return map[schedule] || schedule
}

// ── Lifecycle ──────────────────────────────────────────────────

onMounted(async () => {
  await fetchStatus()
  connectWebSocket()
})

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style>
/* Global styles */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial,
    sans-serif;
  background: #f5f7fa;
  color: #303133;
  -webkit-font-smoothing: antialiased;
}
</style>

<style scoped>
.app-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100vh;
}

/* Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.app-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  letter-spacing: -0.02em;
}

.app-subtitle {
  font-size: 13px;
  color: #909399;
  font-weight: 400;
}

.header-right :deep(.el-tag) {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Main Layout */
.main-layout {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

@media (max-width: 1024px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
}

/* Info Card */
.info-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid #ebeef5;
  margin-top: 16px;
}

.info-card h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  color: #606266;
  margin: 0 0 12px 0;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.info-label {
  font-size: 12px;
  color: #909399;
}

.info-value {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}
</style>
