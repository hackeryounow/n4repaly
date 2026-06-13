<template>
  <div class="field-editor" v-if="detail">
    <div class="editor-summary">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Intercept ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="Message Type">{{ detail.message_type }}</el-descriptions-item>
        <el-descriptions-item label="Direction">{{ detail.direction }}</el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="detail.status === 'held' ? 'warning' : 'info'" size="small">
            {{ detail.status }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <el-divider content-position="left">Header Fields</el-divider>
    <el-form label-width="160px" size="small" class="edit-form">
      <el-form-item label="SEID" v-if="detail.header.seid !== undefined && detail.header.seid !== null">
        <el-input v-model="headerEdits.seid" placeholder="SEID (integer)" />
        <div class="field-hint">64-bit Session Endpoint Identifier</div>
      </el-form-item>
      <el-form-item label="Sequence Number">
        <el-input-number v-model="headerEdits.sequence_number" :min="0" :max="16777215" />
        <div class="field-hint">24-bit sequence number</div>
      </el-form-item>
    </el-form>

    <el-divider content-position="left">IE Fields</el-divider>

    <div v-for="(ie, ieIdx) in detail.ies" :key="ieIdx" class="ie-edit-section">
      <template v-if="ie.group && ie.ies">
        <!-- Group IE - show sub-IEs recursively -->
        <el-collapse>
          <el-collapse-item :title="`${ie.type_name}${ie._summary ? ' : ' + ie._summary : ''}`" :name="String(ieIdx)">
            <template v-for="(subIe, subIdx) in ie.ies" :key="subIdx">
              <div v-if="subIe.group && subIe.ies" class="sub-ie-edit">
                <div class="sub-ie-label">{{ subIe.type_name }}{{ subIe._summary ? ' : ' + subIe._summary : '' }} [{{ subIe.length }}B]</div>
                <!-- Recursively render nested group IEs -->
                <div v-for="(deepIe, deepIdx) in subIe.ies" :key="deepIdx" class="deep-ie-edit">
                  <div v-if="deepIe.group && deepIe.ies" class="sub-ie-edit">
                    <div class="sub-ie-label">{{ deepIe.type_name }}{{ deepIe._summary ? ' : ' + deepIe._summary : '' }} [{{ deepIe.length }}B]</div>
                    <IEEditor
                      v-for="(leafIe, leafIdx) in deepIe.ies"
                      :key="leafIdx"
                      :ie="leafIe"
                      :ie-index="leafIdx"
                      :depth="3"
                      @update-hex="(hex: string) => onSubIEHexUpdate(`ies.${ieIdx}.ies.${subIdx}.ies.${deepIdx}.ies.${leafIdx}`, hex)"
                    />
                  </div>
                  <IEEditor
                    v-else
                    :ie="deepIe"
                    :ie-index="deepIdx"
                    :depth="2"
                    @update-hex="(hex: string) => onSubIEHexUpdate(`ies.${ieIdx}.ies.${subIdx}.ies.${deepIdx}`, hex)"
                  />
                </div>
              </div>
              <IEEditor
                v-else
                :ie="subIe"
                :ie-index="subIdx"
                :depth="1"
                @update-hex="(hex: string) => onSubIEHexUpdate(`ies.${ieIdx}.ies.${subIdx}`, hex)"
              />
            </template>
          </el-collapse-item>
        </el-collapse>
      </template>
      <template v-else>
        <IEEditor
          :ie="ie"
          :ie-index="ieIdx"
          :depth="0"
          @update-hex="(hex: string) => onSubIEHexUpdate(`ies.${ieIdx}`, hex)"
        />
      </template>
    </div>

    <div class="editor-actions">
      <el-button @click="$emit('cancel')">Cancel</el-button>
      <el-button type="primary" @click="onSave" :disabled="!hasChanges">
        <el-icon><Check /></el-icon> Save Modifications
      </el-button>
      <el-tag v-if="modificationCount > 0" type="warning" size="small">
        {{ modificationCount }} field(s) modified
      </el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from 'vue'
import type { InterceptedPacketDetail } from '../types'
import IEEditor from './IEEditor.vue'

const props = defineProps<{
  detail: InterceptedPacketDetail
}>()

const emit = defineEmits<{
  (e: 'save', id: string, modifications: Record<string, any>): void
  (e: 'cancel'): void
}>()

// Header edits (reactive so v-model works)
const headerEdits = reactive({
  seid: props.detail.header.seid !== undefined && props.detail.header.seid !== null
    ? String(props.detail.header.seid)
    : '',
  sequence_number: props.detail.header.sequence_number,
})

// Store for IE field modifications (reactive for Vue 3 tracking)
const modifications = reactive<Record<string, any>>({})

function onFieldUpdate(path: string, value: any) {
  modifications[path] = value
}

function onSubIEHexUpdate(path: string, hex: string) {
  modifications[path] = { hex }
}

// Computed: how many IE fields have been modified
const modificationCount = computed(() => Object.keys(modifications).length)

// Computed: true if any header or IE field has changed
const hasChanges = computed(() => {
  // Check header changes
  const origSeid = props.detail.header.seid !== undefined && props.detail.header.seid !== null
    ? String(props.detail.header.seid) : ''
  if (headerEdits.seid !== origSeid) return true
  if (headerEdits.sequence_number !== props.detail.header.sequence_number) return true
  // Check IE modifications
  return modificationCount.value > 0
})

function onSave() {
  const mods: Record<string, any> = {}

  // Add header modifications
  const origSeid = props.detail.header.seid !== undefined && props.detail.header.seid !== null
    ? String(props.detail.header.seid) : ''
  if (headerEdits.seid !== origSeid) {
    mods['header'] = mods['header'] || {}
    mods['header']['seid'] = Number(headerEdits.seid)
  }
  if (headerEdits.sequence_number !== props.detail.header.sequence_number) {
    mods['header'] = mods['header'] || {}
    mods['header']['sequence_number'] = headerEdits.sequence_number
  }

  // Add IE modifications - convert dot-path to nested object
  for (const [path, value] of Object.entries(modifications)) {
    const parts = path.split('.')
    let current = mods
    for (let i = 0; i < parts.length - 1; i++) {
      current[parts[i]] = current[parts[i]] || {}
      current = current[parts[i]]
    }
    current[parts[parts.length - 1]] = value
  }

  emit('save', props.detail.id, mods)
}
</script>

<style scoped>
.field-editor {
  max-height: 70vh;
  overflow-y: auto;
}

.editor-summary {
  margin-bottom: 12px;
}

.edit-form {
  padding: 0 8px;
}

.field-hint {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.ie-edit-section {
  margin-bottom: 8px;
}

.sub-ie-edit {
  padding: 8px;
  margin: 4px 0;
  border-left: 2px solid #409EFF;
  background: #f8f9fa;
}

.deep-ie-edit {
  margin: 2px 0;
}

.deep-ie-edit .sub-ie-edit {
  border-left-color: #67C23A;
}

.sub-ie-label {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 4px;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
  margin-top: 16px;
}
</style>
