<template>
  <div class="packet-detail" v-if="packet">
    <!-- Summary Bar -->
    <div class="summary-bar">
      <div class="summary-row">
        <span class="summary-item">
          <el-tag size="small" :type="packet.direction.includes('SMF') ? 'primary' : 'success'" effect="plain">
            {{ packet.direction }}
          </el-tag>
        </span>
        <span class="summary-item msg-type">
          <strong>{{ packet.message_type }}</strong>
          <span class="msg-id">({{ packet.message_type_id }})</span>
        </span>
      </div>
      <div class="summary-row mono small">
        <span class="summary-item">Seq: {{ packet.sequence_number }}</span>
        <span class="summary-item" v-if="packet.seid !== null && packet.seid !== undefined">
          SEID: 0x{{ packet.seid.toString(16).padStart(16, '0') }}
        </span>
        <span class="summary-item">{{ packet.length }} bytes</span>
        <span class="summary-item text-muted">{{ packet.timestamp }}</span>
      </div>
      <div class="summary-row mono small text-muted">
        <span v-if="packet.logical_src || packet.logical_dst">
          {{ packet.logical_src || packet.src_addr }} → via Relay ({{ packet.dst_addr }}) → {{ packet.logical_dst || '' }}
        </span>
        <span v-else>{{ packet.src_addr }} → {{ packet.dst_addr }}</span>
      </div>
    </div>

    <el-alert v-if="packet.parse_error" :title="packet.parse_error" type="error" :closable="false" style="margin: 4px 0" />

    <!-- PFCP Protocol Tree -->
    <div class="protocol-tree">
      <!-- Protocol Title -->
      <div class="tree-root-header">
        <span class="expand-icon" @click="headerExpanded = !headerExpanded">
          {{ headerExpanded ? '▼' : '▶' }}
        </span>
        <span class="protocol-name">Packet Forwarding Control Protocol</span>
      </div>

      <div v-if="headerExpanded" class="tree-root-body">
        <!-- Flags line -->
        <div class="field-row">
          <span class="field-label">Flags</span>
          <span class="field-colon">:</span>
          <span class="field-value mono">
            {{ packet.header.flags_hex }}{{ packet.header.flags_description ? ', ' + packet.header.flags_description : '' }}
          </span>
        </div>

        <!-- Header _fields from parser -->
        <template v-if="headerFields.length > 0">
          <template v-for="(field, idx) in headerFields" :key="idx">
            <FieldRow
              :label="field.label"
              :value="field.value"
              :bits="field.bits"
              :isBits="field.type === 'bits'"
            />
          </template>
        </template>
        <template v-else>
          <FieldRow label="Version" :value="packet.header.version" />
          <FieldRow label="Message Type" :value="`${packet.header.message_type_name} (${packet.header.message_type})`" />
          <FieldRow label="Length" :value="packet.header.length" />
          <FieldRow label="SEID" :value="packet.header.seid_hex || 'N/A'" v-if="packet.header.seid_flag" />
          <FieldRow label="Sequence Number" :value="`${packet.header.sequence_number}`" />
        </template>
      </div>

      <!-- IEs as tree nodes -->
      <template v-for="(ie, idx) in packet.ies" :key="idx">
        <div class="tree-root-header">
          <span class="expand-icon" @click="toggleIE(ie)">
            {{ isIEExpanded(ie) ? '▼' : '▶' }}
          </span>
          <span class="ie-title">{{ ie.type_name }}</span>
          <span class="ie-summary" v-if="ie._summary"> : {{ ie._summary }}</span>
          <span class="ie-meta"> [{{ ie.length }} bytes]</span>
        </div>
        <div v-if="isIEExpanded(ie)" class="tree-root-body">
          <!-- IE Type and Length header -->
          <FieldRow label="IE Type" :value="`${ie.type_name} (${ie.type})`" />
          <FieldRow label="IE Length" :value="ie.length" />
          <!-- Render IE content -->
          <IEViewer :ie="ie" :depth="0" />
        </div>
      </template>
    </div>

    <!-- Raw Hex -->
    <div class="raw-section">
      <div class="tree-root-header" @click="rawExpanded = !rawExpanded">
        <span class="expand-icon">{{ rawExpanded ? '▼' : '▶' }}</span>
        <span>Raw Hex Dump</span>
      </div>
      <pre v-if="rawExpanded" class="hex-dump">{{ formatHex(packet.raw_hex) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import type { PacketDetail, IEItem, DisplayField } from '../types'
import FieldRow from './FieldRow.vue'
import IEViewer from './IEViewer.vue'

const props = defineProps<{
  packet: PacketDetail
}>()

const headerExpanded = ref(true)
const rawExpanded = ref(false)

// Track IE expanded state
const ieExpandedMap = reactive(new WeakMap<object, boolean>())

function isIEExpanded(ie: IEItem): boolean {
  if (ieExpandedMap.has(ie)) return ieExpandedMap.get(ie)!
  // Default: expand first 3 IEs
  const idx = props.packet.ies.indexOf(ie)
  const defaultExpanded = idx < 3
  ieExpandedMap.set(ie, defaultExpanded)
  return defaultExpanded
}

function toggleIE(ie: IEItem) {
  const current = isIEExpanded(ie)
  ieExpandedMap.set(ie, !current)
}

// Extract header fields from parser metadata
const headerFields = computed<DisplayField[]>(() => {
  const h = props.packet.header
  if (Array.isArray(h._fields)) {
    return h._fields as DisplayField[]
  }
  return []
})

function formatHex(hex: string): string {
  if (!hex) return ''
  const lines: string[] = []
  for (let i = 0; i < hex.length; i += 32) {
    const chunk = hex.slice(i, i + 32)
    const offset = (i / 2).toString(16).padStart(4, '0')
    const bytes = chunk.match(/.{1,2}/g)?.join(' ') || ''
    const ascii = chunk.match(/.{1,2}/g)?.map(b => {
      const c = parseInt(b, 16)
      return c >= 32 && c <= 126 ? String.fromCharCode(c) : '.'
    }).join('') || ''
    lines.push(`${offset}  ${bytes.padEnd(48)}  ${ascii}`)
  }
  return lines.join('\n')
}
</script>

<style scoped>
.packet-detail {
  padding: 4px;
  font-size: 12px;
  color: #bcc8d4;
}

/* Summary bar */
.summary-bar {
  background: rgba(64, 158, 255, 0.06);
  border: 1px solid #1a2a4a;
  border-radius: 4px;
  padding: 6px 10px;
  margin-bottom: 8px;
}

.summary-row {
  display: flex;
  align-items: center;
  gap: 12px;
  line-height: 1.6;
}

.summary-item {
  white-space: nowrap;
  color: #d0dae6;
  display: inline-flex;
  align-items: center;
}

/* Direction tag override */
:deep(.el-tag) {
  background: rgba(64, 158, 255, 0.12) !important;
  border: 1px solid rgba(64, 158, 255, 0.3) !important;
  color: #409eff !important;
  font-size: 11px;
  font-weight: 600;
  padding: 0 8px;
  height: 20px;
  line-height: 20px;
}

:deep(.el-tag--success) {
  background: rgba(103, 194, 58, 0.12) !important;
  border: 1px solid rgba(103, 194, 58, 0.3) !important;
  color: #67c23a !important;
}

.msg-type {
  font-size: 13px;
}

.msg-id {
  color: #6a8aaa;
  font-weight: normal;
}

/* Protocol tree */
.protocol-tree {
  border: 1px solid #1a2a4a;
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.tree-root-header {
  display: flex;
  align-items: baseline;
  padding: 4px 8px;
  cursor: pointer;
  background: #0a1628;
  border-bottom: 1px solid #1a2a4a;
  user-select: none;
  line-height: 1.6;
}

.tree-root-header:hover {
  background: rgba(64, 158, 255, 0.08);
}

.tree-root-body {
  padding: 4px 8px 4px 24px;
  border-bottom: 1px solid #0d1f3c;
}

.expand-icon {
  width: 14px;
  font-size: 9px;
  color: #6a8aaa;
  flex-shrink: 0;
  text-align: center;
}

.protocol-name {
  font-weight: 600;
  color: #d0d8e0;
  font-size: 13px;
}

.ie-title {
  font-weight: 600;
  color: #d0d8e0;
}

.ie-summary {
  color: #69b4ff;
  font-weight: 400;
}

.ie-meta {
  color: #6a8aaa;
  font-size: 11px;
  margin-left: 4px;
}

.field-row {
  display: flex;
  align-items: baseline;
  padding: 1px 0;
  font-size: 12px;
  line-height: 1.7;
}

.field-label {
  color: #8899aa;
  font-weight: 500;
  min-width: 200px;
  flex-shrink: 0;
}

.field-colon {
  margin: 0 6px;
  color: #3a5a7a;
}

.field-value {
  color: #d0dae6;
  word-break: break-all;
}

/* Raw hex section */
.raw-section {
  border: 1px solid #1a2a4a;
  border-radius: 4px;
  overflow: hidden;
}

.hex-dump {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #0a1628;
  color: #a8c088;
  padding: 12px;
  margin: 0;
  overflow-x: auto;
  white-space: pre;
}

/* Shared */
.mono {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

.small {
  font-size: 11px;
}

.text-muted {
  color: #6a8aaa;
}
</style>
