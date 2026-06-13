<template>
  <div class="ie-viewer">
    <template v-if="ie.group && ie.ies">
      <!-- Group IE: render sub-IEs as expandable tree nodes -->
      <div v-for="(subIe, idx) in ie.ies" :key="idx" class="tree-node">
        <div class="tree-node-header" @click="toggleExpand(subIe)">
          <span class="expand-icon" v-if="hasChildren(subIe) || hasFields(subIe)">
            {{ getNodeExpanded(subIe) ? '▼' : '▶' }}
          </span>
          <span class="expand-icon" v-else>  </span>
          <span class="ie-title">{{ subIe.type_name }}</span>
          <span class="ie-summary" v-if="subIe._summary"> : {{ subIe._summary }}</span>
          <span class="ie-meta"> [{{ subIe.length }} bytes]</span>
        </div>
        <!-- Expanded content -->
        <div v-if="getNodeExpanded(subIe)" class="tree-node-body">
          <!-- IE Type and Length -->
          <FieldRow label="IE Type" :value="`${subIe.type_name} (${subIe.type})`" :depth="depth + 1" />
          <FieldRow label="IE Length" :value="subIe.length" :depth="depth + 1" />
          <!-- Sub-IEs (if group) -->
          <template v-if="subIe.group && subIe.ies">
            <IEViewer :ie="subIe" :depth="depth + 1" />
          </template>
          <!-- Value fields (if leaf) -->
          <template v-else-if="subIe.value">
            <template v-for="(field, fIdx) in getFields(subIe.value)" :key="fIdx">
              <FieldRow
                :label="field.label"
                :value="field.value"
                :depth="depth + 1"
                :bits="field.bits"
                :isBits="field.type === 'bits'"
              />
            </template>
          </template>
        </div>
      </div>
    </template>

    <!-- Leaf IE: render value fields -->
    <template v-else-if="ie.value">
      <template v-for="(field, idx) in getFields(ie.value)" :key="idx">
        <FieldRow
          :label="field.label"
          :value="field.value"
          :depth="depth"
          :bits="field.bits"
          :isBits="field.type === 'bits'"
        />
      </template>
    </template>

    <!-- Fallback -->
    <div v-else class="no-value" :style="{ paddingLeft: depth * 16 + 'px' }">
      (no parsed data)
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { IEItem, DisplayField } from '../types'
import FieldRow from './FieldRow.vue'

const props = defineProps<{
  ie: IEItem
  depth: number
}>()

// Track expanded state per IE node
const expandedMap = reactive(new WeakMap<object, boolean>())

function getNodeExpanded(ie: IEItem): boolean {
  if (expandedMap.has(ie)) return expandedMap.get(ie)!
  // Default: expand first level
  const defaultExpanded = props.depth < 1
  expandedMap.set(ie, defaultExpanded)
  return defaultExpanded
}

function toggleExpand(ie: IEItem) {
  const current = getNodeExpanded(ie)
  expandedMap.set(ie, !current)
}

function hasChildren(ie: IEItem): boolean {
  return !!(ie.group && ie.ies && ie.ies.length > 0)
}

function hasFields(ie: IEItem): boolean {
  if (!ie.value) return false
  const fields = getFields(ie.value)
  return fields.length > 0
}

function getFields(value: Record<string, any>): DisplayField[] {
  if (!value) return []
  if (Array.isArray(value._fields)) {
    return value._fields as DisplayField[]
  }
  // Fallback: render all non-internal keys
  const fields: DisplayField[] = []
  for (const [key, val] of Object.entries(value)) {
    if (key.startsWith('_')) continue
    fields.push({ type: 'field', label: formatKey(key), value: val })
  }
  return fields
}

function formatKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

<style scoped>
.ie-viewer {
  font-size: 12px;
}

.tree-node {
  margin: 1px 0;
}

.tree-node-header {
  display: flex;
  align-items: baseline;
  padding: 2px 4px;
  cursor: pointer;
  border-radius: 2px;
  user-select: none;
  line-height: 1.6;
}

.tree-node-header:hover {
  background: rgba(64, 158, 255, 0.08);
}

.expand-icon {
  width: 14px;
  font-size: 9px;
  color: #5a7a9a;
  flex-shrink: 0;
  text-align: center;
}

.ie-title {
  font-weight: 600;
  color: #d0dae6;
}

.ie-summary {
  color: #69b4ff;
  font-weight: 400;
}

.ie-meta {
  color: #5a7a9a;
  font-size: 11px;
  margin-left: 4px;
}

.tree-node-body {
  padding-left: 14px;
  border-left: 1px solid #0d1f3c;
  margin-left: 6px;
}

.no-value {
  color: #3a5a7a;
  font-style: italic;
}
</style>
