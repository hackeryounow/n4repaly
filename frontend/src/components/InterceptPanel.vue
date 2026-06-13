<template>
  <div class="intercept-panel">
    <div class="panel-toolbar">
      <div class="toolbar-left">
        <el-button size="small" class="btn-refresh" @click="$emit('refresh')">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="success" size="small" :disabled="heldCount === 0" @click="$emit('release-all')">
          <el-icon><Promotion /></el-icon> Release All{{ heldCount > 0 ? ` (${heldCount})` : '' }}
        </el-button>
        <el-button type="danger" size="small" :disabled="heldCount === 0" @click="$emit('drop-all')">
          <el-icon><CircleClose /></el-icon> Drop All{{ heldCount > 0 ? ` (${heldCount})` : '' }}
        </el-button>
      </div>
      <el-tag size="small" class="held-tag">{{ heldCount }} held</el-tag>
    </div>

    <el-empty v-if="intercepted.length === 0" description="No intercepted packets" :image-size="60" />

    <div v-else class="intercept-list">
      <div
        v-for="pkt in intercepted"
        :key="pkt.id"
        class="intercept-item"
        @click="$emit('select', pkt.id)"
      >
        <div class="item-header">
          <span class="dir-badge" :class="{
            'dir-smf': pkt.direction.includes('SMF'),
            'dir-upf': pkt.direction.includes('UPF') && !pkt.direction.includes('SMF')
          }">
            {{ pkt.direction }}
          </span>
          <el-tag size="small" :type="statusType(pkt.status)" effect="dark">
            {{ pkt.status }}
          </el-tag>
        </div>
        <div class="item-body">
          <div class="item-title">{{ pkt.message_type }}</div>
          <div class="item-info">
            <span>SEID: {{ pkt.seid !== null ? pkt.seid : 'N/A' }}</span>
            <span>Seq: {{ pkt.sequence_number }}</span>
            <span>{{ pkt.length }}B</span>
          </div>
          <div class="item-time">{{ pkt.timestamp }}</div>
        </div>
        <div class="item-actions" @click.stop>
          <el-button
            type="success"
            size="small"
            :disabled="pkt.status !== 'held'"
            @click="$emit('release', pkt.id)"
          >
            <el-icon><Promotion /></el-icon> Release
          </el-button>
          <el-button
            type="danger"
            size="small"
            :disabled="pkt.status !== 'held'"
            @click="$emit('drop', pkt.id)"
          >
            <el-icon><CircleClose /></el-icon> Drop
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { InterceptedPacket } from '../types'

const props = defineProps<{
  intercepted: InterceptedPacket[]
}>()

const heldCount = computed(() => props.intercepted.filter(p => p.status === 'held').length)

defineEmits<{
  (e: 'release', id: string): void
  (e: 'drop', id: string): void
  (e: 'release-all'): void
  (e: 'drop-all'): void
  (e: 'select', id: string): void
  (e: 'refresh'): void
}>()

function statusType(status: string): string {
  switch (status) {
    case 'held': return 'warning'
    case 'released': return 'success'
    case 'dropped': return 'danger'
    default: return 'info'
  }
}
</script>

<style scoped>
.intercept-panel {
  padding: 4px;
  background: #060e1a;
  min-height: 100%;
}

.panel-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding: 8px 10px;
  background: linear-gradient(180deg, #0a1628 0%, #081220 100%);
  border: 1px solid #1a2a4a;
  border-radius: 4px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.held-tag {
  background: rgba(230, 162, 60, 0.12) !important;
  border: 1px solid rgba(230, 162, 60, 0.3) !important;
  color: #e6a23c !important;
  font-weight: 600;
}

.btn-refresh {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
  color: #8899aa !important;
}
.btn-refresh:hover {
  background: #142a4a !important;
  color: #409eff !important;
  border-color: #409eff !important;
}

.intercept-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.intercept-item {
  border: 1px solid #1a2a4a;
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s;
  background: #0a1628;
}

.intercept-item:hover {
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  border-color: #409EFF;
  background: rgba(64, 158, 255, 0.04);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

/* Direction badges */
.dir-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 3px;
  letter-spacing: 0.3px;
}
.dir-smf {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
  border: 1px solid rgba(64, 158, 255, 0.3);
}
.dir-upf {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.item-body {
  margin-bottom: 8px;
}

.item-title {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
  color: #d0dae6;
}

.item-info {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #8899aa;
}

.item-time {
  font-size: 11px;
  color: #5a7a9a;
  margin-top: 2px;
}

.item-actions {
  display: flex;
  gap: 8px;
}

/* Element Plus overrides */
:deep(.el-empty__description p) {
  color: #6a8aaa;
}

:deep(.el-button--success) {
  background: rgba(103, 194, 58, 0.12) !important;
  border: 1px solid rgba(103, 194, 58, 0.3) !important;
  color: #67c23a !important;
}
:deep(.el-button--success:hover) {
  background: rgba(103, 194, 58, 0.2) !important;
}
:deep(.el-button--success.is-disabled) {
  opacity: 0.5;
}

:deep(.el-button--danger) {
  background: rgba(245, 108, 108, 0.08) !important;
  border: 1px solid rgba(245, 108, 108, 0.3) !important;
  color: #f56c6c !important;
}
:deep(.el-button--danger:hover) {
  background: rgba(245, 108, 108, 0.16) !important;
}
:deep(.el-button--danger.is-disabled) {
  opacity: 0.5;
}

:deep(.el-tag--warning.is-dark) {
  background: rgba(230, 162, 60, 0.15) !important;
  border-color: rgba(230, 162, 60, 0.3) !important;
  color: #e6a23c !important;
}
:deep(.el-tag--success.is-dark) {
  background: rgba(103, 194, 58, 0.15) !important;
  border-color: rgba(103, 194, 58, 0.3) !important;
  color: #67c23a !important;
}
:deep(.el-tag--danger.is-dark) {
  background: rgba(245, 108, 108, 0.15) !important;
  border-color: rgba(245, 108, 108, 0.3) !important;
  color: #f56c6c !important;
}
</style>
