<template>
  <el-dropdown @command="handleActivate" trigger="click">
    <el-button :icon="Grid" size="small" type="primary" plain>
      {{ activeDomainName || 'Select Domain' }}
      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
    </el-button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item
          v-for="d in activeDomains"
          :key="d.id"
          :command="d.id"
          :class="{ 'is-active': d.id === activeDomainId }"
        >
          <el-icon v-if="d.id === activeDomainId"><Check /></el-icon>
          <span>{{ d.display_name }} ({{ d.domain }})</span>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, inject, watch } from 'vue'
import type { Ref } from 'vue'
import { Grid, ArrowDown, Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listDomains, activateDomain, getActiveDomain, type DomainConfig } from '../api/domain'

const domains = ref<DomainConfig[]>([])
const activeDomainId = ref<number | null>(null)

// Listen for domain changes from sibling components
const domainRefreshKey = inject<Ref<number>>('domainRefreshKey', ref(0))
watch(domainRefreshKey, () => {
  fetchDomains()
  fetchActiveDomain()
})

const activeDomains = computed(() => domains.value.filter(d => d.status === 'active'))
const activeDomainName = computed(() => {
  const d = domains.value.find(d => d.id === activeDomainId.value)
  return d ? d.display_name : ''
})

async function fetchDomains() {
  try {
    domains.value = await listDomains('active')
  } catch (e) {
    console.error('Failed to load domains', e)
  }
}

async function fetchActiveDomain() {
  try {
    const result = await getActiveDomain()
    activeDomainId.value = result.active_domain_id
  } catch (e) {
    console.error('Failed to get active domain', e)
  }
}

async function handleActivate(domainId: number) {
  try {
    const result = await activateDomain(domainId)
    activeDomainId.value = result.active_domain_id
    ElMessage.success('Domain switched')
  } catch (e) {
    ElMessage.error('Failed to switch domain')
  }
}

onMounted(async () => {
  await Promise.all([fetchDomains(), fetchActiveDomain()])
})
</script>
