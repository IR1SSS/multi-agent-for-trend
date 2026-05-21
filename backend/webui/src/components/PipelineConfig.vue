<template>
  <div class="config-panel">
    <h3 class="panel-title">
      <el-icon><Setting /></el-icon>
      Pipeline Configuration
    </h3>

    <el-form
      :model="form"
      label-width="100px"
      label-position="right"
      :disabled="disabled"
      class="config-form"
    >
      <!-- 运行模式 -->
      <el-form-item label="Run Mode">
        <el-radio-group v-model="form.mode" @change="onModeChange">
          <el-radio-button value="test">
            <el-icon><Monitor /></el-icon> Test
          </el-radio-button>
          <el-radio-button value="prod">
            <el-icon><Cpu /></el-icon> Production
          </el-radio-button>
        </el-radio-group>
        <div class="form-hint">
          {{ form.mode === 'test' ? 'Process first 5 keywords only' : 'Process all keywords' }}
        </div>
      </el-form-item>

      <!-- 目标平台 -->
      <el-form-item label="Platforms">
        <el-checkbox-group v-model="form.platforms">
          <el-checkbox value="dy" border>
            <el-icon><VideoCamera /></el-icon> Douyin
          </el-checkbox>
          <el-checkbox value="bili" border>
            <el-icon><VideoPlay /></el-icon> Bilibili
          </el-checkbox>
          <el-checkbox value="wb" border>
            <el-icon><ChatLineSquare /></el-icon> Weibo
          </el-checkbox>
          <el-checkbox value="xhs" border>
            <el-icon><ChatDotRound /></el-icon> Xiaohongshu
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <!-- 登录方式 -->
      <el-form-item label="Login Method">
        <el-select v-model="form.login_type" placeholder="Select login method">
          <el-option label="QR Code (Recommended)" value="qrcode">
            <el-icon><Iphone /></el-icon> QR Code
          </el-option>
          <el-option label="Phone Number" value="phone">
            <el-icon><Phone /></el-icon> Phone Number
          </el-option>
          <el-option label="Cookie" value="cookie">
            <el-icon><Key /></el-icon> Cookie
          </el-option>
        </el-select>
        <div class="form-hint">
          First keyword uses selected method, subsequent keywords auto-switch to Cookie session reuse
        </div>
      </el-form-item>

      <!-- 爬取周期 -->
      <el-form-item label="Schedule">
        <el-select
          v-model="form.schedule"
          placeholder="Run Once"
          :disabled="form.mode === 'test'"
          clearable
        >
          <el-option label="Run Once" :value="null" />
          <el-option label="Daily" value="daily" />
          <el-option label="Weekly" value="weekly" />
          <el-option label="Monthly" value="monthly" />
        </el-select>
        <div class="form-hint" v-if="form.mode === 'test'">
          Test mode runs once only, scheduling not supported
        </div>
      </el-form-item>

      <!-- 无头模式 -->
      <el-form-item label="Browser Mode">
        <el-switch
          v-model="form.headless"
          active-text="Headless"
          inactive-text="Windowed"
          inactive-color="#409eff"
        />
        <div class="form-hint">
          {{ form.headless ? 'Run in background without browser window' : 'Show browser window to observe crawling' }}
        </div>
      </el-form-item>
    </el-form>

    <!-- 控制按钮 -->
    <div class="control-buttons">
      <el-button
        type="primary"
        :icon="VideoPlay"
        :loading="starting"
        :disabled="disabled || isRunning"
        @click="$emit('start', getParams())"
      >
        {{ starting ? 'Starting...' : 'Start' }}
      </el-button>

      <el-button
        type="danger"
        :icon="VideoPause"
        :loading="stopping"
        :disabled="!isRunning"
        @click="$emit('stop')"
      >
        Stop
      </el-button>

      <el-button
        :icon="RefreshRight"
        @click="$emit('refreshStatus')"
      >
        Refresh
      </el-button>

      <el-button
        :icon="FolderOpened"
        @click="$emit('previewData')"
      >
        Data
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import {
  Setting, Monitor, Cpu, ChatDotRound, VideoCamera,
  VideoPlay, ChatLineSquare, Iphone, Phone, Key,
  VideoPause, RefreshRight, FolderOpened,
} from '@element-plus/icons-vue'
import type { PipelineStartParams } from '../api/pipeline'

const props = defineProps<{
  disabled: boolean
  isRunning: boolean
  starting: boolean
  stopping: boolean
  initialParams?: Partial<PipelineStartParams>
}>()

const emit = defineEmits<{
  start: [params: PipelineStartParams]
  stop: []
  refreshStatus: []
  previewData: []
}>()

const form = reactive({
  mode: 'test' as 'test' | 'prod',
  platforms: ['dy'] as string[],
  login_type: 'qrcode' as 'qrcode' | 'phone' | 'cookie',
  headless: false,
  schedule: null as string | null,
})

// Load initial params if provided (e.g., from current running pipeline)
watch(() => props.initialParams, (params) => {
  if (params) {
    if (params.mode) form.mode = params.mode
    if (params.platforms) form.platforms = [...params.platforms]
    if (params.login_type) form.login_type = params.login_type
    if (params.headless !== undefined) form.headless = params.headless
    if (params.schedule !== undefined) form.schedule = params.schedule
  }
}, { immediate: true })

function onModeChange(mode: string) {
  if (mode === 'test') {
    form.schedule = null
  }
}

function getParams(): PipelineStartParams {
  return {
    mode: form.mode,
    platforms: form.platforms,
    login_type: form.login_type,
    headless: form.headless,
    schedule: form.schedule,
  }
}
</script>

<style scoped>
.config-panel {
  background: #ffffff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  border: 1px solid #ebeef5;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #303133;
}

.config-form {
  max-width: 600px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.control-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}
</style>
