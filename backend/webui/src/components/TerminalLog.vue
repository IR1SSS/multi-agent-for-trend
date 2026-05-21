<template>
  <div class="terminal" ref="terminalRef">
    <div class="terminal-header">
      <div class="terminal-dots">
        <span class="dot dot-red"></span>
        <span class="dot dot-yellow"></span>
        <span class="dot dot-green"></span>
      </div>
      <span class="terminal-title">Pipeline Output</span>
      <div class="terminal-actions">
        <el-button
          size="small"
          text
          @click="clearLogs"
          title="Clear Logs"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
        <el-button
          size="small"
          text
          @click="scrollToBottom"
          title="Scroll to Bottom"
        >
          <el-icon><Bottom /></el-icon>
        </el-button>
        <el-button
          size="small"
          text
          :type="autoScroll ? 'primary' : 'default'"
          @click="autoScroll = !autoScroll"
          title="Auto Scroll"
        >
          <el-icon><Promotion /></el-icon>
        </el-button>
      </div>
    </div>
    <div class="terminal-body" ref="bodyRef">
      <div v-if="logs.length === 0" class="terminal-empty">
        Waiting for pipeline to start...
      </div>
      <div
        v-for="(log, index) in logs"
        :key="index"
        class="log-line"
        :class="getLogClass(log)"
      >{{ log }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { Delete, Bottom, Promotion } from '@element-plus/icons-vue'

const props = defineProps<{
  logs: string[]
}>()

const bodyRef = ref<HTMLDivElement>()
const autoScroll = ref(true)

function clearLogs() {
  // Emit event to parent to clear logs
  // We'll handle this through the parent component
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) {
      bodyRef.value.scrollTop = bodyRef.value.scrollHeight
    }
  })
}

function getLogClass(line: string): string {
  const lower = line.toLowerCase()
  if (lower.includes('error') || lower.includes('failed') || lower.includes('traceback')) {
    return 'log-error'
  }
  if (lower.includes('warning') || lower.includes('warn')) {
    return 'log-warn'
  }
  if (lower.includes('success') || lower.includes('completed') || lower.includes('ok')) {
    return 'log-success'
  }
  if (lower.includes('[1/3]') || lower.includes('[2/3]') || lower.includes('[3/3]')) {
    return 'log-step'
  }
  return ''
}

watch(() => props.logs.length, () => {
  if (autoScroll.value) {
    scrollToBottom()
  }
})

defineExpose({ scrollToBottom })
</script>

<style scoped>
.terminal {
  border-radius: 8px;
  overflow: hidden;
  background: #1e1e2e;
  border: 1px solid #313244;
  font-family: 'Cascadia Code', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.terminal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: #313244;
  border-bottom: 1px solid #45475a;
}

.terminal-dots {
  display: flex;
  gap: 6px;
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.dot-red { background: #f38ba8; }
.dot-yellow { background: #f9e2af; }
.dot-green { background: #a6e3a1; }

.terminal-title {
  flex: 1;
  color: #cdd6f4;
  font-size: 12px;
  font-weight: 500;
}

.terminal-actions {
  display: flex;
  gap: 4px;
}

.terminal-actions :deep(.el-button) {
  color: #a6adc8;
  padding: 4px;
}

.terminal-actions :deep(.el-button:hover) {
  color: #cdd6f4;
}

.terminal-body {
  padding: 12px 16px;
  height: 420px;
  overflow-y: auto;
  color: #cdd6f4;
}

.terminal-body::-webkit-scrollbar {
  width: 6px;
}

.terminal-body::-webkit-scrollbar-track {
  background: transparent;
}

.terminal-body::-webkit-scrollbar-thumb {
  background: #585b70;
  border-radius: 3px;
}

.terminal-empty {
  color: #6c7086;
  font-style: italic;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-error {
  color: #f38ba8;
}

.log-warn {
  color: #f9e2af;
}

.log-success {
  color: #a6e3a1;
}

.log-step {
  color: #89b4fa;
  font-weight: 600;
}
</style>
