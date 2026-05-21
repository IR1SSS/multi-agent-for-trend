<template>
  <div class="status-bar" :class="`status-${status}`">
    <div class="status-indicator">
      <span class="status-dot"></span>
      <span class="status-text">{{ statusLabel }}</span>
    </div>
    <div class="status-meta" v-if="statusDetail.started_at">
      <span class="meta-item">
        <el-icon><Clock /></el-icon>
        {{ startedAt }}
      </span>
      <span class="meta-item" v-if="statusDetail.completed_at">
        <el-icon><CircleCheck /></el-icon>
        {{ duration }}
      </span>
      <span class="meta-item" v-if="statusDetail.exit_code !== null">
        <el-icon><Document /></el-icon>
        Exit: {{ statusDetail.exit_code }}
      </span>
      <span class="meta-item">
        <el-icon><Memo /></el-icon>
        {{ statusDetail.log_line_count }} log lines
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Clock, CircleCheck, Document, Memo } from '@element-plus/icons-vue'
import type { PipelineStatusResult } from '../api/pipeline'

const props = defineProps<{
  statusDetail: PipelineStatusResult
}>()

const status = computed(() => props.statusDetail.status)

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    idle: 'Idle',
    running: 'Running',
    stopping: 'Stopping',
    completed: 'Completed',
    failed: 'Failed',
  }
  return map[status.value] || status.value
})

const startedAt = computed(() => {
  if (!props.statusDetail.started_at) return ''
  return new Date(props.statusDetail.started_at).toLocaleString('en-US')
})

const duration = computed(() => {
  const start = props.statusDetail.started_at
  const end = props.statusDetail.completed_at
  if (!start || !end) return ''
  const ms = new Date(end).getTime() - new Date(start).getTime()
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainSec = seconds % 60
  return `${minutes}m ${remainSec}s`
})
</script>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-radius: 8px;
  border: 1px solid;
  transition: all 0.3s ease;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: background-color 0.3s ease;
}

.status-text {
  font-weight: 600;
  font-size: 14px;
}

.status-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #606266;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Status-specific styles */
.status-idle {
  background: #f4f4f5;
  border-color: #d3d4d6;
}
.status-idle .status-dot { background: #909399; }
.status-idle .status-text { color: #606266; }

.status-running {
  background: #ecf5ff;
  border-color: #b3d8ff;
  animation: pulse 2s ease-in-out infinite;
}
.status-running .status-dot {
  background: #409eff;
  animation: blink 1s ease-in-out infinite;
}
.status-running .status-text { color: #409eff; }

.status-stopping {
  background: #fdf6ec;
  border-color: #faecd8;
}
.status-stopping .status-dot { background: #e6a23c; }
.status-stopping .status-text { color: #e6a23c; }

.status-completed {
  background: #f0f9eb;
  border-color: #c2e7b0;
}
.status-completed .status-dot { background: #67c23a; }
.status-completed .status-text { color: #67c23a; }

.status-failed {
  background: #fef0f0;
  border-color: #fbc4c4;
}
.status-failed .status-dot { background: #f56c6c; }
.status-failed .status-text { color: #f56c6c; }

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(64, 158, 255, 0.1); }
  50% { box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.1); }
}
</style>
