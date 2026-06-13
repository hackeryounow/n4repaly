<template>
  <div class="packet-list">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="filterMsgType"
          placeholder="All Message Types"
          size="small"
          clearable
          style="width: 210px"
          @change="emitRefresh"
        >
          <el-option
            v-for="mt in MESSAGE_TYPES"
            :key="mt.value"
            :label="`${mt.label} (${mt.value})`"
            :value="String(mt.value)"
          />
        </el-select>
        <el-select
          v-model="filterDirection"
          placeholder="All Directions"
          size="small"
          clearable
          style="width: 150px"
          @change="emitRefresh"
        >
          <el-option label="All" value="" />
          <el-option label="SMF → UPF" value="SMF" />
          <el-option label="UPF → SMF" value="UPF" />
        </el-select>
        <div class="filter-toggle">
          <el-switch v-model="filterHeartbeat" size="small" active-color="#909399" @change="emitRefresh" />
          <span class="filter-label">Hide Heartbeat</span>
        </div>
      </div>
      <div class="toolbar-right">
        <span class="packet-count">{{ total }}<span class="packet-count-label"> packets</span></span>
        <el-button size="small" @click="emitRefresh" class="btn-refresh">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button size="small" type="danger" plain @click="$emit('clear')" class="btn-clear">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- Table -->
    <el-table
      :data="packets"
      size="small"
      highlight-current-row
      @current-change="onSelect"
      height="calc(100vh - 160px)"
      style="width: 100%"
      :row-class-name="rowClassName"
      :header-cell-style="{ background: '#0a1628', color: '#8899aa', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', borderColor: '#1a2a4a' }"
      :cell-style="{ borderColor: '#0d1f3c' }"
    >
      <el-table-column prop="id" label="#" width="52" sortable>
        <template #default="{ row }">
          <span class="cell-id">{{ row.id }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="timestamp" label="Time" width="170">
        <template #default="{ row }">
          <span class="mono cell-time">{{ row.timestamp }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="direction" label="Direction" width="120">
        <template #default="{ row }">
          <span class="dir-badge" :class="{
            'dir-smf': row.direction.includes('SMF'),
            'dir-upf': row.direction.includes('UPF') && !row.direction.includes('SMF')
          }">
            {{ row.direction.includes('SMF') ? '▼ DL' : '▲ UL' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="message_type" label="Message Type" min-width="220">
        <template #default="{ row }">
          <span :class="msgTypeClass(row.message_type_id)" class="msg-type-cell">
            <span class="msg-type-id">{{ row.message_type_id }}</span>
            {{ row.message_type }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="seid" label="SEID" width="150">
        <template #default="{ row }">
          <span class="mono seid-cell" v-if="row.seid !== null && row.seid !== undefined">
            0x{{ row.seid.toString(16).padStart(16, '0') }}
          </span>
          <span v-else class="text-muted seid-none">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="sequence_number" label="Seq" width="64">
        <template #default="{ row }">
          <span class="mono cell-seq">{{ row.sequence_number }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="length" label="Len" width="56" />
      <el-table-column label="Path" width="240">
        <template #default="{ row }">
          <div class="addr-cell">
            <span class="mono small path-src">{{ row.logical_src || row.src_addr }}</span>
            <span class="path-arrow">→</span>
            <span class="mono small path-dst">{{ row.logical_dst || row.dst_addr }}</span>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination -->
    <div class="pagination-bar">
      <el-select v-model="localPageSize" size="small" style="width: 90px" @change="onPageSizeChange">
        <el-option :value="20" label="20" />
        <el-option :value="50" label="50" />
        <el-option :value="200" label="200" />
      </el-select>
      <span class="pagination-info">per page</span>
      <div style="flex:1" />
      <el-pagination
        small
        background
        layout="prev, pager, next"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @current-change="onPageChange"
      />
      <span class="pagination-info">{{ packets.length }} / {{ total }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { PacketSummary } from '../types'

const props = defineProps<{
  packets: PacketSummary[]
  total: number
  currentPage: number
  pageSize: number
}>()

const emit = defineEmits<{
  (e: 'select', pkt: PacketSummary): void
  (e: 'clear'): void
  (e: 'refresh', msgType: string, direction: string, excludeHeartbeat: boolean): void
  (e: 'page-change', page: number, pageSize: number): void
}>()

const localPageSize = ref(50)

watch(() => props.pageSize, (val) => { localPageSize.value = val }, { immediate: true })

const filterMsgType = ref('')
const filterDirection = ref('')
const filterHeartbeat = ref(true)

const MESSAGE_TYPES = [
  { value: 1, label: 'Heartbeat Request' },
  { value: 2, label: 'Heartbeat Response' },
  { value: 5, label: 'Association Setup Request' },
  { value: 6, label: 'Association Setup Response' },
  { value: 7, label: 'Association Update Request' },
  { value: 8, label: 'Association Update Response' },
  { value: 9, label: 'Association Release Request' },
  { value: 10, label: 'Association Release Response' },
  { value: 50, label: 'Session Establishment Request' },
  { value: 51, label: 'Session Establishment Response' },
  { value: 52, label: 'Session Modification Request' },
  { value: 53, label: 'Session Modification Response' },
  { value: 54, label: 'Session Deletion Request' },
  { value: 55, label: 'Session Deletion Response' },
  { value: 56, label: 'Session Report Request' },
  { value: 57, label: 'Session Report Response' },
]

function emitRefresh() {
  emit('refresh', filterMsgType.value, filterDirection.value, filterHeartbeat.value)
}

function onPageChange(page: number) {
  emit('page-change', page, props.pageSize)
}

function onPageSizeChange(size: number) {
  emit('page-change', 1, size)
}

function onSelect(row: PacketSummary | null) {
  if (row) emit('select', row)
}

function rowClassName({ row }: { row: PacketSummary }) {
  if (row.message_type_id >= 50) return 'row-session'
  if (row.message_type_id === 1 || row.message_type_id === 2) return 'row-heartbeat'
  return ''
}

function msgTypeClass(typeId: number): string {
  if (typeId >= 50) return 'msg-session'
  if (typeId === 1 || typeId === 2) return 'msg-heartbeat'
  if (typeId >= 5 && typeId <= 10) return 'msg-assoc'
  return ''
}
</script>

<style scoped>
.packet-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #060e1a;
  border-radius: 6px;
  overflow: hidden;
}

/* ── Toolbar ── */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: linear-gradient(180deg, #0a1628 0%, #081220 100%);
  border-bottom: 1px solid #1a2a4a;
  gap: 12px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid #1a3050;
  border-radius: 4px;
  margin-left: 8px;
}

.filter-label {
  font-size: 12px;
  color: #6a8aaa;
  white-space: nowrap;
  user-select: none;
}

.packet-count {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  font-weight: 700;
  color: #409eff;
}

.packet-count-label {
  font-weight: 400;
  font-size: 11px;
  color: #5a7a9a;
  margin-left: 2px;
}

.btn-refresh, .btn-clear {
  font-size: 12px !important;
}

/* ── Table overrides ── */
:deep(.el-table) {
  --el-table-bg-color: #060e1a;
  --el-table-tr-bg-color: #060e1a;
  --el-table-border-color: #0d1f3c;
  --el-table-row-hover-bg-color: rgba(64, 158, 255, 0.06);
  --el-table-current-row-bg-color: rgba(64, 158, 255, 0.1);
  --el-table-text-color: #bcc8d4;
  --el-table-header-text-color: #8899aa;
  background: #060e1a;
  font-size: 12px;
}

:deep(.el-table th.el-table__cell) {
  background: #0a1628 !important;
}

:deep(.el-table__body tr.el-table__row) {
  background: #060e1a;
}

:deep(.el-table__body tr.el-table__row--striped) {
  background: #080f20;
}

:deep(.el-table__body tr:hover > td) {
  background: rgba(64, 158, 255, 0.08) !important;
}

:deep(.el-table__body tr.el-table__row--striped:hover > td) {
  background: rgba(64, 158, 255, 0.1) !important;
}

:deep(.el-table__body tr.current-row > td) {
  background: rgba(64, 158, 255, 0.14) !important;
  box-shadow: inset 3px 0 0 #409eff;
}

/* ── Row variants ── */
:deep(.row-session) {
  background: rgba(0, 100, 200, 0.08) !important;
}
:deep(.el-table__body tr.row-session.el-table__row--striped) {
  background: rgba(0, 100, 200, 0.06) !important;
}
:deep(.row-heartbeat) {
  opacity: 0.55;
}

/* ── Cell styles ── */
.cell-id {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  color: #5a7a9a;
}

.cell-time {
  font-size: 11px;
  color: #8a9ab0;
}

.cell-seq {
  color: #6a8aaa;
}

/* ── Direction badges ── */
.dir-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
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

/* ── Message type ── */
.msg-type-cell {
  font-size: 12px;
}
.msg-type-id {
  display: inline-block;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 10px;
  font-weight: 600;
  margin-right: 6px;
  padding: 1px 5px;
  border-radius: 2px;
  color: #8899aa;
  background: rgba(136, 153, 170, 0.1);
  min-width: 24px;
  text-align: center;
}

.msg-session {
  color: #409eff;
  font-weight: 500;
}
.msg-session .msg-type-id {
  color: #409eff;
  background: rgba(64, 158, 255, 0.12);
}

.msg-heartbeat {
  color: #68768a;
}
.msg-heartbeat .msg-type-id {
  color: #68768a;
  background: rgba(104, 118, 138, 0.1);
}

.msg-assoc {
  color: #67c23a;
}
.msg-assoc .msg-type-id {
  color: #67c23a;
  background: rgba(103, 194, 58, 0.12);
}

/* ── SEID ── */
.seid-cell {
  font-size: 11px;
  color: #e6a23c;
}
.seid-none {
  font-size: 12px;
}

/* ── Path ── */
.addr-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.4;
}
.path-src {
  font-size: 10px;
  color: #409eff;
}
.path-arrow {
  font-size: 10px;
  color: #3a5a7a;
  flex-shrink: 0;
}
.path-dst {
  font-size: 10px;
  color: #67c23a;
}

/* ── Shared ── */
.mono {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}
.small {
  font-size: 11px;
}
.text-muted {
  color: #68768a;
}

:deep(.el-table__row) {
  cursor: pointer;
}

/* scrollbar */
:deep(.el-table__body-wrapper::-webkit-scrollbar) {
  width: 6px;
  height: 6px;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-track) {
  background: #060e1a;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb) {
  background: #1a3050;
  border-radius: 3px;
}
:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb:hover) {
  background: #2a4a6a;
}

/* ── Pagination ── */
.pagination-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #0a1628;
  border-top: 1px solid #1a2a4a;
  flex-shrink: 0;
}

.pagination-info {
  font-size: 11px;
  color: #6a8aaa;
  white-space: nowrap;
}

/* ── Element Plus Overrides ── */
:deep(.el-select .el-select__wrapper) {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
  box-shadow: none !important;
}

:deep(.el-select .el-input__wrapper) {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
  box-shadow: none !important;
}

:deep(.el-select .el-select__selected-item) {
  color: #bcc8d4 !important;
}

:deep(.el-select .el-select__placeholder) {
  color: #bcc8d4 !important;
}

:deep(.el-select .el-select__placeholder.is-transparent) {
  color: #5a7a9a !important;
}

:deep(.el-select .el-input__inner) {
  color: #bcc8d4 !important;
}

:deep(.el-select .el-input__inner::placeholder) {
  color: #5a7a9a !important;
}

:deep(.el-select .el-select__caret) {
  color: #5a7a9a !important;
}

:deep(.el-select .el-select__suffix) {
  color: #5a7a9a !important;
}

:deep(.el-input__suffix .el-icon) {
  color: #5a7a9a;
}

:deep(.btn-refresh) {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
  color: #8899aa !important;
}
:deep(.btn-refresh:hover) {
  background: #142a4a !important;
  color: #409eff !important;
  border-color: #409eff !important;
}

:deep(.btn-clear) {
  background: rgba(245, 108, 108, 0.08) !important;
  border: 1px solid rgba(245, 108, 108, 0.3) !important;
  color: #f56c6c !important;
}
:deep(.btn-clear:hover) {
  background: rgba(245, 108, 108, 0.16) !important;
  color: #ff8080 !important;
}

:deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: #8899aa;
  --el-pagination-button-bg-color: #0d1f3c;
  --el-pagination-hover-color: #409eff;
}

:deep(.el-pagination .is-active) {
  background: #409eff !important;
  color: #fff !important;
}

:deep(.el-pagination button:disabled) {
  background: #0d1f3c !important;
  color: #3a5a7a !important;
}

:deep(.el-pager li) {
  background: #0d1f3c !important;
  color: #8899aa !important;
}

:deep(.el-pager li:hover) {
  color: #409eff !important;
}

:deep(.el-switch) {
  --el-switch-off-color: #3a5a7a;
}
</style>
