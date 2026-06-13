<template>
  <div class="field-row" :class="{ 'bit-row': isBits }" :style="{ paddingLeft: (depth ?? 0) * 16 + 'px' }">
    <span v-if="isBits" class="bit-pattern mono">{{ bits }}</span>
    <span class="field-label">{{ label }}</span>
    <span class="field-colon">:</span>
    <span class="field-value">{{ displayValue }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: any
  depth?: number
  bits?: string
  isBits?: boolean
}>()

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined) return 'N/A'
  if (typeof props.value === 'boolean') return props.value ? 'True' : 'False'
  if (typeof props.value === 'object') return JSON.stringify(props.value)
  return String(props.value)
})
</script>

<style scoped>
.field-row {
  display: flex;
  align-items: baseline;
  padding: 1px 0;
  font-size: 12px;
  line-height: 1.7;
  border-bottom: 1px solid #0d1f3c;
}

.field-row:last-child {
  border-bottom: none;
}

.bit-row {
  background: rgba(64, 158, 255, 0.04);
}

.bit-pattern {
  color: #409EFF;
  font-size: 11px;
  min-width: 100px;
  flex-shrink: 0;
  letter-spacing: 0.5px;
  text-align: right;
  padding-right: 8px;
  user-select: text;
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
  flex-shrink: 0;
}

.field-value {
  color: #d0dae6;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  word-break: break-all;
}
</style>
