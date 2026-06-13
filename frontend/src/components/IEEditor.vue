<template>
  <div class="ie-editor">
    <!-- ===== Group IE: render sub-IEs ===== -->
    <template v-if="ie.group && ie.ies">
      <div v-for="(subIe, idx) in ie.ies" :key="idx" class="sub-ie-node" :class="{ 'sub-ie-deleted': deletedSubIEs.has(idx) }">
        <div v-if="!deletedSubIEs.has(idx)" class="sub-ie-header" @click="toggleSubIE(subIe)">
          <span class="expand-icon">{{ isSubIEExpanded(subIe) ? '▼' : '▶' }}</span>
          <span class="ie-title">{{ subIe.type_name }}</span>
          <span class="ie-summary" v-if="subIe._summary"> : {{ subIe._summary }}</span>
          <span class="ie-meta">[type={{ subIe.type }}, {{ subIe.length }}B]</span>
          <div style="flex:1" />
          <el-tag v-if="subIEHexEdits.has(idx)" size="small" type="warning">modified</el-tag>
          <el-button
            size="small" type="danger" text
            @click.stop="deleteSubIE(idx)"
            title="Delete this sub-IE"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
        <div v-if="!deletedSubIEs.has(idx) && isSubIEExpanded(subIe)" class="sub-ie-body">
          <IEEditor
            :ie="subIe"
            :ie-index="idx"
            :depth="depth + 1"
            :raw-hex="getSubIERawHex(idx)"
            @update-hex="(hex: string) => onSubIEHexChange(idx, hex)"
          />
          <!-- Sub-IE hex editor -->
          <div class="ie-hex-editor compact">
            <div class="ie-hex-label">Value (hex)</div>
            <el-input
              :model-value="getSubIERawHex(idx)"
              @input="(v: string) => onSubIEHexChange(idx, v.replace(/\s/g, ''))"
              type="textarea"
              :rows="1"
              class="ie-hex-input"
              placeholder="sub-IE hex..."
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ===== Leaf IE: inline-editable parsed fields + hex ===== -->
    <template v-else>
      <!-- Inline-editable parsed fields -->
      <div v-if="ie.value && ie.value._fields" class="parsed-fields-editable">
        <div v-for="(field, fIdx) in ie.value._fields" :key="fIdx" class="pf-row" :class="{ 'pf-editable': !!field.edit_key }">
          <span class="pf-label">{{ field.label }}</span>
          <!-- Bit pattern (read-only) -->
          <span v-if="field.type === 'bits'" class="pf-bits">{{ field.bits }}</span>
          <!-- Editable field -->
          <template v-if="field.edit_key">
            <el-input
              v-if="field.edit_type === 'text'"
              v-model="inlineValues[field.edit_key]"
              @change="() => onInlineFieldChange(field.edit_key!)"
              size="small"
              class="pf-input"
            />
            <el-input
              v-else-if="field.edit_type === 'number'"
              v-model="inlineValues[field.edit_key]"
              @change="() => onInlineFieldChange(field.edit_key!)"
              size="small"
              class="pf-input pf-input-num"
            />
          </template>
          <!-- Read-only value -->
          <span v-else class="pf-value">{{ field.value }}</span>
        </div>
      </div>

      <!-- Flag-based editing (Apply Action etc.) -->
      <div v-if="ie._edit_mode === 'flags' && ie._flag_items" class="flag-editor">
        <span class="flag-label">Actions</span>
        <div class="flag-checks">
          <el-checkbox
            v-for="item in flagStates"
            :key="item.name"
            v-model="item.checked"
            @change="() => onFlagChange()"
            :label="item.name"
          />
        </div>
      </div>

      <!-- Serialize status -->
      <div v-if="serializing" class="serialize-status">
        <el-icon class="is-loading"><Loading /></el-icon> Serializing...
      </div>
      <div v-else-if="serializeError" class="serialize-status serialize-error">
        {{ serializeError }}
      </div>

      <!-- Hex textarea (always visible) -->
      <div class="ie-hex-editor">
        <div class="ie-hex-label">Value (hex)</div>
        <el-input
          v-model="localHex"
          @change="onHexInputChange"
          type="textarea"
          :rows="Math.max(1, Math.ceil((localHex.replace(/\s/g,'').length) / 32))"
          class="ie-hex-input"
          placeholder="IE value hex bytes..."
        />
        <div class="ie-hex-info">
          <span>{{ Math.floor(localHex.replace(/\s/g,'').length / 2) }} bytes</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { Delete } from '@element-plus/icons-vue'
import type { IEItem } from '../types'
import * as api from '../api'

const props = defineProps<{
  ie: IEItem
  ieIndex: number
  depth: number
  rawHex?: string
}>()

const emit = defineEmits<{
  (e: 'update-hex', hex: string): void
}>()

// ---- Current hex (from rawHex prop or empty) ----
const currentHex = computed(() => props.rawHex || '')
const localHex = ref('')

// Sync localHex with rawHex prop changes
watch(currentHex, (val) => {
  localHex.value = val
}, { immediate: true })

function onHexInputChange() {
  // Strip whitespace and emit to parent
  const clean = localHex.value.replace(/\s/g, '')
  localHex.value = clean
  _internalUpdate = true
  emit('update-hex', clean)
  nextTick(() => { _internalUpdate = false })
}

// ---- Sub-IE expansion state ----
const subIEExpandedMap = reactive(new WeakMap<object, boolean>())
const subIEHexEdits = reactive(new Map<number, string>())
const deletedSubIEs = reactive(new Set<number>())

function isSubIEExpanded(ie: IEItem): boolean {
  if (subIEExpandedMap.has(ie)) return subIEExpandedMap.get(ie)!
  const def = props.depth < 2
  subIEExpandedMap.set(ie, def)
  return def
}
function toggleSubIE(ie: IEItem) {
  subIEExpandedMap.set(ie, !isSubIEExpanded(ie))
}
function getSubIERawHex(idx: number): string {
  // Check local edits first, then fall back to cached raw hex
  if (subIEHexEdits.has(idx)) return subIEHexEdits.get(idx)!
  const subIe = props.ie.ies?.[idx]
  return (subIe as any)?._rawHex || ''
}
function onSubIEHexChange(idx: number, hex: string) {
  subIEHexEdits.set(idx, hex)
  rebuildGroupHex()
}
function deleteSubIE(idx: number) {
  deletedSubIEs.add(idx)
  subIEHexEdits.delete(idx)
  rebuildGroupHex()
}
function rebuildGroupHex() {
  if (!props.ie.group || !props.ie.ies) return
  let combined = ''
  props.ie.ies.forEach((subIe, idx) => {
    // Skip deleted sub-IEs
    if (deletedSubIEs.has(idx)) return
    // Use edited hex if available, otherwise use cached raw hex
    const valueHex = subIEHexEdits.has(idx)
      ? subIEHexEdits.get(idx)!
      : ((subIe as any)?._rawHex || '')
    const typeHex = subIe.type.toString(16).padStart(4, '0')
    const lenHex = (valueHex.length / 2).toString(16).padStart(4, '0')
    combined += typeHex + lenHex + valueHex
  })
  _internalUpdate = true
  emit('update-hex', combined)
  nextTick(() => { _internalUpdate = false })
}

// ---- Inline field editing ----
const inlineValues = reactive<Record<string, any>>({})
const flagStates = reactive<{ name: string; bit: number; checked: boolean }[]>([])
const serializing = ref(false)
const serializeError = ref('')

function initInlineValues() {
  for (const k of Object.keys(inlineValues)) delete inlineValues[k]
  flagStates.splice(0, flagStates.length)

  const val = props.ie.value
  if (!val || typeof val !== 'object') return
  const fields = val._fields
  if (!fields) return

  for (const f of fields) {
    if (f.edit_key) {
      inlineValues[f.edit_key] = f.edit_value ?? ''
    }
  }

  // Flag-based IEs
  if (props.ie._edit_mode === 'flags' && props.ie._flag_items) {
    for (const item of props.ie._flag_items as any[]) {
      flagStates.push({ name: item.name, bit: item.bit, checked: !!item.checked })
    }
  }
}

onMounted(initInlineValues)
watch(() => props.ie, initInlineValues, { deep: true })

// Track if we're in the middle of our own serialization (to avoid feedback loop)
let _internalUpdate = false

// Re-init inline values when rawHex changes externally (e.g., after Apply/Re-parse)
watch(() => props.rawHex, (newHex) => {
  if (_internalUpdate) return
  // rawHex changed from outside → re-parse inline values from the IE data
  initInlineValues()
})

let debounceTimer: ReturnType<typeof setTimeout> | null = null

function onInlineFieldChange(key: string) {
  // v-model already updated inlineValues[key]
  // Always serialize — empty fields become 0 in the output
  serializeError.value = ''
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => doSerialize(), 300)
}

function onFlagChange() {
  // v-model already updated flagStates, compute combined flag value
  let flagValue = 0
  for (const fs of flagStates) {
    if (fs.checked) flagValue |= fs.bit
  }
  // For F-TEID (21) / F-SEID (57): include all inline values + flag bits
  // For Apply Action (44): just send action
  if (props.ie.type === 21 || props.ie.type === 57) {
    const allFields: Record<string, any> = { ...inlineValues, flags: flagValue }
    // Parse numeric fields
    const val = props.ie.value as any
    if (val && val._fields) {
      for (const f of val._fields) {
        if (f.edit_key && f.edit_type === 'number') {
          const raw = allFields[f.edit_key]
          allFields[f.edit_key] = (raw === '' || raw === null || raw === undefined) ? 0 : (Number(raw) || 0)
        }
      }
    }
    // Handle TEID/SEID hex strings
    if (props.ie.type === 21 && typeof allFields.teid === 'string') {
      allFields.teid = allFields.teid !== '' ? (parseInt(allFields.teid.replace(/^0x/i, ''), 16) || 0) : 0
    }
    if (props.ie.type === 57 && typeof allFields.seid === 'string') {
      allFields.seid = allFields.seid !== '' ? (parseInt(allFields.seid.replace(/^0x/i, ''), 16) || 0) : 0
    }
    serializeFromFields(allFields)
  } else {
    serializeFromFields({ action: flagValue })
  }
}

async function doSerialize() {
  // Collect all current inline values as the fields dict
  const fields: Record<string, any> = { ...inlineValues }

  // For numeric types, parse as number — empty fields become 0
  const val = props.ie.value as any
  if (val && val._fields) {
    for (const f of val._fields) {
      if (f.edit_key && f.edit_type === 'number') {
        const raw = fields[f.edit_key]
        if (raw === '' || raw === null || raw === undefined) {
          fields[f.edit_key] = 0
        } else {
          fields[f.edit_key] = Number(raw) || 0
        }
      }
    }
  }

  // Special handling: SEID and TEID may be hex strings — empty becomes 0
  if (props.ie.type === 57 && typeof fields.seid === 'string') {
    fields.seid = fields.seid !== '' ? (parseInt(fields.seid.replace(/^0x/i, ''), 16) || 0) : 0
  }
  if (props.ie.type === 21 && typeof fields.teid === 'string') {
    // TEID might be hex like "00000001"
    if (fields.teid !== '') {
      const teidStr = fields.teid.replace(/^0x/i, '')
      fields.teid = parseInt(teidStr, 16) || 0
    } else {
      fields.teid = 0
    }
  }

  // For F-SEID/F-TEID: compute flags from flag editor if present, else from address fields
  if (props.ie.type === 57 || props.ie.type === 21) {
    let flags = 0
    // If flag editor is active, use its state
    if (props.ie._edit_mode === 'flags' && flagStates.length > 0) {
      for (const fs of flagStates) {
        if (fs.checked) flags |= fs.bit
      }
    } else {
      // Compute from available address fields
      if (fields.ipv4_address) flags |= 0x01
      if (fields.ipv6_address) flags |= 0x02
    }
    fields.flags = flags
  }

  // For Node ID: set node_id_type_value and keep address fields
  if (props.ie.type === 60) {
    const nodeType = Number(fields.node_id_type_value) || 0
    fields.node_id_type_value = nodeType
    // Clear irrelevant address fields
    if (nodeType !== 0) delete fields.ipv4_address
    if (nodeType !== 1) delete fields.ipv6_address
    if (nodeType !== 2) delete fields.fqdn
  }

  // For UE IP Address: compute flags from available addresses
  if (props.ie.type === 93) {
    let flags = (props.ie.value as any)?.flags || 0
    flags = flags & 0xFC  // Clear v4/v6 bits
    if (fields.ipv4) flags |= 0x02
    if (fields.ipv6) flags |= 0x01
    fields.flags = flags
  }

  await serializeFromFields(fields)
}

async function serializeFromFields(fields: Record<string, any>) {
  serializing.value = true
  serializeError.value = ''
  try {
    const result = await api.serializeIE(props.ie.type, fields)
    _internalUpdate = true
    emit('update-hex', result.hex)
    await nextTick()
    _internalUpdate = false
  } catch (e: any) {
    serializeError.value = e.response?.data?.detail || e.message
  }
  serializing.value = false
}
</script>

<style scoped>
.ie-editor {
  font-size: 12px;
}

/* Sub-IE tree */
.sub-ie-node {
  border-bottom: 1px solid #ebeef5;
}
.sub-ie-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  user-select: none;
  background: #f9f9fb;
  line-height: 1.6;
}
.sub-ie-header:hover { background: #ecf5ff; }
.sub-ie-deleted {
  opacity: 0.4;
}
.sub-ie-body {
  padding: 4px 0 4px 8px;
  border-left: 2px solid #e4e7ed;
  margin-left: 6px;
  background: #fafbfc;
}

.expand-icon {
  width: 14px;
  font-size: 9px;
  color: #909399;
  flex-shrink: 0;
  text-align: center;
}
.ie-title { font-weight: 600; color: #303133; }
.ie-summary { color: #409EFF; }
.ie-meta { color: #909399; font-size: 11px; }

/* Parsed fields - inline editable */
.parsed-fields-editable {
  padding: 2px 0;
}

.pf-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
  line-height: 1.5;
}

.pf-row.pf-editable {
  background: #f0f9eb;
  border-radius: 3px;
  padding: 2px 6px;
  margin: 1px -6px;
}

.pf-label {
  min-width: 110px;
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
}

.pf-editable .pf-label {
  color: #67C23A;
  font-weight: 600;
}

.pf-bits {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 11px;
  color: #b37feb;
  background: #f9f0ff;
  padding: 0 4px;
  border-radius: 2px;
}

.pf-value {
  font-size: 12px;
  color: #303133;
}

.pf-input {
  width: 200px;
}

.pf-input-num {
  width: 120px;
}

.pf-input :deep(.el-input__inner) {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

/* Flag editor */
.flag-editor {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.flag-label {
  min-width: 110px;
  font-size: 11px;
  color: #67C23A;
  font-weight: 600;
  flex-shrink: 0;
}

.flag-checks {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* Status */
.serialize-status {
  font-size: 11px;
  color: #909399;
  padding: 2px 0;
  display: flex;
  align-items: center;
  gap: 4px;
}
.serialize-error {
  color: #F56C6C;
}

/* Hex editor */
.ie-hex-editor {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #e4e7ed;
}
.ie-hex-editor.compact {
  margin-top: 4px;
  padding-top: 4px;
}
.ie-hex-label {
  font-size: 11px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 3px;
}
.ie-hex-input :deep(textarea) {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}
.ie-hex-info {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
</style>
