<template>
  <div class="template-manager">
    <div class="tm-toolbar">
      <el-button type="primary" size="small" @click="openCreateDialog">
        <el-icon><Plus /></el-icon> New Template
      </el-button>
      <el-button size="small" @click="loadTemplates">
        <el-icon><Refresh /></el-icon> Refresh
      </el-button>
      <el-tag size="small" type="info">{{ templates.length }} templates</el-tag>
    </div>

    <el-empty v-if="templates.length === 0" description="No templates. Create one from a captured packet or from scratch." :image-size="60" />

    <el-table v-else :data="templates" size="small" stripe @row-click="openEditDialog">
      <el-table-column label="Name" prop="name" min-width="140">
        <template #default="{ row }">
          <span class="tmpl-name">{{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Match Type" width="200">
        <template #default="{ row }">
          <el-tag size="small">{{ row.match_msg_type_name }}</el-tag>
          <span v-if="row.match_seid !== null" class="tmpl-seid">SEID: {{ row.match_seid }}</span>
        </template>
      </el-table-column>
      <el-table-column label="Response" width="80" align="center">
        <template #default="{ row }">
          <span class="tmpl-size">{{ row.response_length }}B</span>
        </template>
      </el-table-column>
      <el-table-column label="Hits" width="60" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.hit_count > 0 ? 'success' : 'info'">{{ row.hit_count }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Status" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            size="small"
            @click.stop
            @change="onToggle(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="Actions" width="100" align="center">
        <template #default="{ row }">
          <el-button type="danger" size="small" text @click.stop="onDelete(row)">
            <el-icon><Delete /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="showDialog" :title="isEditing ? 'Edit Template' : 'New Template'" class="tmpl-fullscreen" fullscreen>
      <div class="tmpl-dialog-body">
        <!-- LEFT: Form -->
        <div class="tmpl-form-pane">
          <el-form :model="form" label-width="140px" size="small">
            <el-form-item label="Name" required>
              <el-input v-model="form.name" placeholder="e.g., Auto Session Deletion Response" />
            </el-form-item>
            <el-form-item label="Match Message Type" required>
              <el-select v-model="form.match_msg_type" filterable placeholder="Select message type" style="width: 100%">
                <el-option
                  v-for="mt in MESSAGE_TYPES"
                  :key="mt.value"
                  :label="`${mt.label} (${mt.value})`"
                  :value="mt.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="Match SEID">
              <el-input v-model="form.match_seid_str" placeholder="Leave empty to match any SEID" />
            </el-form-item>

            <el-divider content-position="left">Response Packet</el-divider>

            <el-form-item label="Auto Seq Number">
              <el-switch v-model="form.auto_seq" />
              <span class="field-hint-inline">Copy from request</span>
            </el-form-item>
            <el-form-item label="Auto SEID">
              <el-switch v-model="form.auto_seid" />
              <span class="field-hint-inline">Copy from request</span>
            </el-form-item>
            <el-form-item label="Response Hex" required>
              <el-input
                v-model="form.response_hex"
                type="textarea"
                :rows="6"
                placeholder="Paste the PFCP response packet as hex..."
                class="hex-input"
              />
              <div class="hex-actions">
                <el-button size="small" type="primary" plain @click="doParseHex" :loading="parsing">
                  <el-icon><View /></el-icon> Parse
                </el-button>
                <span class="field-hint">{{ hexByteCount }} bytes</span>
              </div>
            </el-form-item>

            <el-form-item label="Active">
              <el-switch v-model="form.enabled" />
            </el-form-item>
          </el-form>
        </div>

        <!-- RIGHT: Parsed Editor -->
        <div class="tmpl-parsed-pane">
          <div class="parsed-header">
            <span class="parsed-title">PFCP Packet Editor</span>
            <el-tag v-if="parsedData" size="small" type="success">{{ parsedData.header.message_type_name }}</el-tag>
            <el-tag v-else-if="parseError" size="small" type="danger">{{ parseError }}</el-tag>
            <div style="flex:1" />
            <el-button v-if="parsedData" size="small" type="primary" plain @click="doParseHex" :loading="parsing">Re-parse</el-button>
          </div>

          <div v-if="parsedData" class="parsed-body">
            <!-- ===== Header Section ===== -->
            <div class="section-header" @click="parsedHeaderExpanded = !parsedHeaderExpanded">
              <span class="expand-icon">{{ parsedHeaderExpanded ? '▼' : '▶' }}</span>
              <span class="section-title">Header</span>
              <span class="section-meta">{{ parsedData.header.message_type_name }} (type {{ parsedData.header.message_type }}) — {{ parsedData.header.length }} bytes payload</span>
            </div>
            <div v-if="parsedHeaderExpanded" class="section-body">
              <div class="editable-field">
                <span class="ef-label">Message Type</span>
                <el-select
                  :model-value="headerEditMsgType"
                  @update:model-value="(v: string) => { headerEditMsgType = v }"
                  filterable size="small" class="ef-select"
                  :placeholder="`${parsedData.header.message_type_name} (${parsedData.header.message_type})`"
                >
                  <el-option
                    v-for="mt in MESSAGE_TYPES"
                    :key="mt.value"
                    :label="`${mt.label} (${mt.value})`"
                    :value="String(mt.value)"
                  />
                </el-select>
                <el-tag v-if="headerEditMsgType !== '' && headerEditMsgType !== String(parsedData.header.message_type ?? '')" size="small" type="warning" class="ef-badge">modified</el-tag>
              </div>
              <div class="editable-field">
                <span class="ef-label">Length</span>
                <el-input
                  :model-value="headerEditLength"
                  @input="(v: string) => { headerEditLength = v }"
                  size="small" class="ef-input-sm"
                  :placeholder="`auto (${parsedData.header.length})`"
                />
                <el-tag v-if="headerEditLength !== '' && headerEditLength !== String(parsedData.header.length ?? '')" size="small" type="warning" class="ef-badge">modified</el-tag>
              </div>
              <!-- Flags section -->
              <div class="editable-field flags-row">
                <span class="ef-label">Flags</span>
                <span class="ef-flags">{{ parsedData.header.flags_hex }}</span>
                <el-tag v-if="flagsModified" size="small" type="warning" class="ef-badge">modified</el-tag>
              </div>
              <div class="editable-field flag-editable">
                <span class="ef-label">Version</span>
                <el-input
                  :model-value="headerEditVersion"
                  @input="(v: string) => { headerEditVersion = v }"
                  size="small" class="flag-num"
                  placeholder="0-7"
                />
                <span class="ef-hint">3-bit</span>
              </div>
              <div class="editable-field flag-editable">
                <span class="ef-label">Message Priority</span>
                <el-switch :model-value="headerEditMP" @update:model-value="(v: boolean) => { headerEditMP = v }" size="small" />
                <span class="ef-hint">MP flag</span>
              </div>
              <div class="editable-field flag-editable">
                <span class="ef-label">Follow-On</span>
                <el-switch :model-value="headerEditFO" @update:model-value="(v: boolean) => { headerEditFO = v }" size="small" />
                <span class="ef-hint">FO flag</span>
              </div>
              <div class="editable-field flag-editable">
                <span class="ef-label">SEID Present</span>
                <el-switch :model-value="headerEditS" @update:model-value="(v: boolean) => { headerEditS = v }" size="small" />
                <span class="ef-hint">S flag</span>
              </div>
              <div v-if="parsedData.header.seid !== null && parsedData.header.seid !== undefined" class="editable-field">
                <span class="ef-label">SEID</span>
                <el-input
                  :model-value="headerEditSeid"
                  @input="(v: string) => { headerEditSeid = v }"
                  size="small" class="ef-input"
                >
                  <template #prepend>0x</template>
                </el-input>
                <el-tag v-if="form.auto_seid" size="small" type="info" class="ef-badge">auto</el-tag>
                <el-tag v-if="headerEditSeid !== String(parsedData.header.seid ?? '')" size="small" type="warning" class="ef-badge">modified</el-tag>
              </div>
              <div class="editable-field">
                <span class="ef-label">Sequence Number</span>
                <el-input
                  :model-value="headerEditSeq"
                  @input="(v: string) => { headerEditSeq = v }"
                  size="small" class="ef-input"
                />
                <el-tag v-if="form.auto_seq" size="small" type="info" class="ef-badge">auto</el-tag>
                <el-tag v-if="headerEditSeq !== String(parsedData.header.sequence_number ?? '')" size="small" type="warning" class="ef-badge">modified</el-tag>
              </div>
            </div>

            <!-- ===== IE List ===== -->
            <div class="section-header">
              <span class="section-title">Information Elements</span>
              <span class="section-meta">{{ activeIECount }} IE(s)</span>
            </div>

            <template v-for="(ie, idx) in parsedData.ies" :key="idx">
              <div v-if="!deletedIEs.has(idx)" class="ie-block" :class="{ 'ie-modified': ieHexEdits.has(idx), 'ie-deleted': false }">
                <div class="ie-block-header" @click="toggleParsedIE(ie)">
                  <span class="expand-icon">{{ isParsedIEExpanded(ie) ? '▼' : '▶' }}</span>
                  <span class="ie-title">{{ ie.type_name }}</span>
                  <span class="ie-summary" v-if="ie._summary"> : {{ ie._summary }}</span>
                  <span class="ie-meta">[type={{ ie.type }}, {{ ie.length }}B]</span>
                  <div style="flex:1" />
                  <el-tag v-if="ieHexEdits.has(idx)" size="small" type="warning">modified</el-tag>
                  <el-button
                    size="small" type="danger" text
                    @click.stop="deleteIE(idx)"
                    title="Delete this IE"
                  >
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
                <div v-if="isParsedIEExpanded(ie)" class="ie-block-body">
                  <!-- Inline-editable parsed fields + hex (IEEditor handles everything) -->
                  <IEEditor
                    :ie="ie"
                    :ie-index="idx"
                    :depth="0"
                    :raw-hex="getIEHex(idx)"
                    @update-hex="(hex: string) => setIEHex(idx, hex)"
                  />
                  <div v-if="ieHexEdits.has(idx)" class="ie-hex-changed-info">
                    Changed from {{ ie.length }} bytes
                  </div>
                </div>
              </div>
            </template>

            <!-- ===== Add IE Section ===== -->
            <div class="add-ie-section">
              <div class="section-header" @click="showAddIE = !showAddIE">
                <span class="expand-icon">{{ showAddIE ? '▼' : '▶' }}</span>
                <span class="section-title">+ Add Information Element</span>
                <el-tag v-if="newIEs.length > 0" size="small" type="success">{{ newIEs.length }} pending</el-tag>
              </div>
              <div v-if="showAddIE" class="add-ie-form">
                <div class="add-ie-row">
                  <el-select v-model="addIEType" filterable placeholder="IE Type" size="small" style="width: 220px">
                    <el-option
                      v-for="it in IE_TYPE_OPTIONS"
                      :key="it.value"
                      :label="`${it.label} (${it.value})`"
                      :value="it.value"
                    />
                  </el-select>
                  <el-input
                    v-model="addIEHex"
                    size="small"
                    placeholder="Value hex (e.g., 01 or 0001)"
                    class="add-ie-hex-input"
                  />
                  <el-button size="small" type="primary" @click="addNewIE" :disabled="!addIEType">Add</el-button>
                </div>
                <!-- Pending new IEs -->
                <div v-for="(nie, ni) in newIEs" :key="ni" class="new-ie-item">
                  <el-tag size="small" type="success">NEW</el-tag>
                  <span class="ie-title">{{ getIETypeName(nie.type) }}</span>
                  <span class="ie-meta">[type={{ nie.type }}, {{ Math.floor(nie.hex.replace(/\s/g,'').length / 2) }}B]</span>
                  <span class="ie-hex-preview">{{ nie.hex.replace(/\s/g,'').slice(0, 32) }}{{ nie.hex.replace(/\s/g,'').length > 32 ? '...' : '' }}</span>
                  <el-button size="small" type="danger" text @click="newIEs.splice(ni, 1)"><el-icon><Delete /></el-icon></el-button>
                </div>
              </div>
            </div>

            <!-- Raw hex dump -->
            <div class="raw-toggle" @click="parsedRawExpanded = !parsedRawExpanded">
              <span class="expand-icon">{{ parsedRawExpanded ? '▼' : '▶' }}</span>
              <span>Raw Hex Dump ({{ hexByteCount }} bytes)</span>
            </div>
            <pre v-if="parsedRawExpanded" class="hex-dump">{{ formatHexDump(form.response_hex) }}</pre>
          </div>

          <el-empty v-else-if="!parseError" description="Click 'Parse' to decode the PFCP packet structure. You can then edit fields and IEs directly." :image-size="48" />
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <el-button
            v-if="totalPendingChanges > 0 && parsedData"
            type="warning"
            @click="applyAllChanges"
            :loading="applyingEdits"
          >
            Apply {{ totalPendingChanges }} Change{{ totalPendingChanges !== 1 ? 's' : '' }} to Hex
          </el-button>
          <div v-else-if="parsedData" class="footer-hint">Edit fields above, then apply changes</div>
          <div style="flex: 1" />
          <el-button @click="showDialog = false">Cancel</el-button>
          <el-button type="primary" @click="onSave" :loading="saving">
            {{ isEditing ? 'Update' : 'Create' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Template, TemplateCreate, IEItem, DisplayField } from '../types'
import * as api from '../api'
import FieldRow from './FieldRow.vue'
import IEViewer from './IEViewer.vue'
import IEEditor from './IEEditor.vue'

const templates = ref<Template[]>([])
const showDialog = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)
const parsing = ref(false)
const applyingEdits = ref(false)

// Header editing (direct input values — empty = no change)
const headerEditMsgType = ref('')
const headerEditLength = ref('')
const headerEditSeid = ref('')
const headerEditSeq = ref('')
const headerEditVersion = ref('')
const headerEditMP = ref(false)
const headerEditFO = ref(false)
const headerEditS = ref(false)

// IE hex-level editing
const ieHexEdits = reactive(new Map<number, string>())  // idx → new hex value
const ieRawHexCache = reactive(new Map<number, string>())  // idx → original hex from backend
const deletedIEs = reactive(new Set<number>())           // deleted IE indices

// Add new IE
const newIEs = reactive<{ type: number; hex: string }[]>([])
const addIEType = ref<number | null>(null)
const addIEHex = ref('')
const showAddIE = ref(false)

// Parsed response state
const parsedData = ref<{ header: Record<string, any>; ies: IEItem[] } | null>(null)
const parseError = ref('')
const parsedHeaderExpanded = ref(true)
const parsedRawExpanded = ref(false)
const parsedIEExpandedMap = reactive(new WeakMap<object, boolean>())

const form = reactive({
  name: '',
  match_msg_type: 50,
  match_seid_str: '',
  response_hex: '',
  auto_seq: true,
  auto_seid: false,
  enabled: true,
})

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

const IE_TYPE_OPTIONS = [
  { value: 19, label: 'Cause' },
  { value: 20, label: 'Source Interface' },
  { value: 21, label: 'F-TEID' },
  { value: 22, label: 'Network Instance' },
  { value: 25, label: 'Gate Status' },
  { value: 29, label: 'Precedence' },
  { value: 42, label: 'Destination Interface' },
  { value: 44, label: 'Apply Action' },
  { value: 56, label: 'PDR ID' },
  { value: 57, label: 'F-SEID' },
  { value: 60, label: 'Node ID' },
  { value: 81, label: 'URR ID' },
  { value: 85, label: 'Outer Header Creation' },
  { value: 88, label: 'BAR ID' },
  { value: 93, label: 'UE IP Address' },
  { value: 95, label: 'Outer Header Removal' },
  { value: 108, label: 'FAR ID' },
  { value: 109, label: 'QER ID' },
  { value: 1, label: 'Create PDR (group)' },
  { value: 2, label: 'PDI (group)' },
  { value: 3, label: 'Create FAR (group)' },
  { value: 4, label: 'Forwarding Parameters (group)' },
  { value: 6, label: 'Create URR (group)' },
  { value: 7, label: 'Create QER (group)' },
  { value: 8, label: 'Created PDR (group)' },
]

async function loadTemplates() {
  try {
    templates.value = await api.listTemplates()
  } catch (e: any) {
    ElMessage.error(`Failed to load templates: ${e.message}`)
  }
}

// ---- IE hex editing ----
function getIEHex(idx: number): string {
  if (ieHexEdits.has(idx)) return ieHexEdits.get(idx)!
  if (ieRawHexCache.has(idx)) return ieRawHexCache.get(idx)!
  // Fallback: try to extract from parsed data
  if (!parsedData.value) return ''
  const ie = parsedData.value.ies[idx]
  if (!ie) return ''
  if (ie.value && typeof ie.value === 'object' && 'raw' in ie.value) {
    return (ie.value as any).raw
  }
  return ''
}

function setIEHex(idx: number, hex: string) {
  ieHexEdits.set(idx, hex.replace(/\s/g, ''))
}

function extractIEValueHex(ie: any): string {
  if (ie.value?.raw) return ie.value.raw
  return ''
}

function deleteIE(idx: number) {
  deletedIEs.add(idx)
  ieHexEdits.delete(idx)
}

function addNewIE() {
  if (addIEType.value === null) return
  const hex = addIEHex.value.replace(/\s/g, '')
  // Validate hex
  if (hex && !/^[0-9a-fA-F]*$/.test(hex)) {
    ElMessage.warning('Invalid hex characters')
    return
  }
  if (hex.length % 2 !== 0) {
    ElMessage.warning('Hex must have even number of characters')
    return
  }
  newIEs.push({ type: addIEType.value, hex })
  addIEType.value = null
  addIEHex.value = ''
}

function getIETypeName(typeVal: number): string {
  const opt = IE_TYPE_OPTIONS.find(o => o.value === typeVal)
  if (opt) return opt.label
  const mt = MESSAGE_TYPES.find(m => m.value === typeVal)
  return `IE ${typeVal}`
}

// ---- Computed ----
const hexByteCount = computed(() => {
  const clean = form.response_hex.replace(/\s/g, '')
  return Math.floor(clean.length / 2)
})

const activeIECount = computed(() => {
  if (!parsedData.value) return 0
  return parsedData.value.ies.length - deletedIEs.size + newIEs.length
})

const totalPendingChanges = computed(() => {
  let count = 0
  // Header changes
  if (parsedData.value) {
    const h = parsedData.value.header
    if (headerEditMsgType.value !== '' && headerEditMsgType.value !== String(h.message_type ?? '')) count++
    if (headerEditLength.value !== '' && headerEditLength.value !== String(h.length ?? '')) count++
    if (h.seid !== null && h.seid !== undefined && headerEditSeid.value !== '' && headerEditSeid.value !== String(h.seid)) count++
    if (headerEditSeq.value !== '' && headerEditSeq.value !== String(h.sequence_number ?? '')) count++
    if (flagsModified.value) count++
  }
  count += ieHexEdits.size
  count += deletedIEs.size
  count += newIEs.length
  return count
})

const flagsModified = computed(() => {
  if (!parsedData.value) return false
  const h = parsedData.value.header
  return (
    (headerEditVersion.value !== '' && headerEditVersion.value !== String(h.version ?? '')) ||
    headerEditMP.value !== !!h.mp ||
    headerEditFO.value !== !!h.fo ||
    headerEditS.value !== !!h.seid_flag
  )
})

// ---- Apply all changes ----
async function applyAllChanges() {
  if (!parsedData.value || totalPendingChanges.value === 0) return
  if (!form.response_hex) return

  const ops: api.HexOp[] = []
  const h = parsedData.value.header

  // Header edits
  if (headerEditMsgType.value !== '' && headerEditMsgType.value !== String(h.message_type ?? '')) {
    ops.push({ op: 'edit_header', field: 'message_type', value: headerEditMsgType.value })
  }
  // Flag changes (version, MP, FO, S) — must come before SEID edit since S flag change alters structure
  if (flagsModified.value) {
    if (headerEditVersion.value !== '' && headerEditVersion.value !== String(h.version ?? '')) {
      ops.push({ op: 'edit_header', field: 'version', value: headerEditVersion.value })
    }
    if (headerEditMP.value !== !!h.mp) {
      ops.push({ op: 'edit_header', field: 'mp', value: headerEditMP.value ? 'true' : 'false' })
    }
    if (headerEditFO.value !== !!h.fo) {
      ops.push({ op: 'edit_header', field: 'fo', value: headerEditFO.value ? 'true' : 'false' })
    }
    if (headerEditS.value !== !!h.seid_flag) {
      ops.push({ op: 'edit_header', field: 'seid_flag', value: headerEditS.value ? 'true' : 'false' })
    }
  }
  // SEID edit: only if S flag is still on (or being turned on) and value is non-empty
  const sFlagWillBeOn = flagsModified.value ? headerEditS.value : !!h.seid_flag
  if (sFlagWillBeOn && h.seid !== null && h.seid !== undefined && headerEditSeid.value !== '' && headerEditSeid.value !== String(h.seid)) {
    ops.push({ op: 'edit_header', field: 'seid', value: headerEditSeid.value })
  }
  if (headerEditSeq.value !== '' && headerEditSeq.value !== String(h.sequence_number ?? '')) {
    ops.push({ op: 'edit_header', field: 'sequence_number', value: headerEditSeq.value })
  }
  // Length override (applied last, after all IE changes)
  if (headerEditLength.value !== '' && headerEditLength.value !== String(h.length ?? '')) {
    ops.push({ op: 'edit_header', field: 'length', value: headerEditLength.value })
  }

  // IE deletions (reverse order to keep indices valid)
  const deleteIndices = [...deletedIEs].sort((a, b) => b - a)
  for (const idx of deleteIndices) {
    ops.push({ op: 'delete_ie', index: idx })
  }

  // IE edits
  for (const [idx, hex] of ieHexEdits.entries()) {
    if (!deletedIEs.has(idx)) {
      ops.push({ op: 'edit_ie', index: idx, hex })
    }
  }

  // New IEs
  for (const nie of newIEs) {
    ops.push({ op: 'add_ie', ie_type: nie.type, hex: nie.hex })
  }

  applyingEdits.value = true
  try {
    const result = await api.rebuildHex(form.response_hex.replace(/\s/g, ''), ops)
    form.response_hex = result.hex
    // Clear all edit state
    ieHexEdits.clear()
    deletedIEs.clear()
    newIEs.splice(0, newIEs.length)
    await doParseHex()
    ElMessage.success(`Applied ${result.applied.length} operation(s)`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || e.message)
  }
  applyingEdits.value = false
}

// ---- Parse hex ----

async function doParseHex() {
  const hex = form.response_hex.replace(/\s/g, '')
  if (!hex) {
    parseError.value = 'Empty hex'
    parsedData.value = null
    return
  }
  parsing.value = true
  parseError.value = ''
  // Clear all edit state on re-parse
  ieHexEdits.clear()
  deletedIEs.clear()
  newIEs.splice(0, newIEs.length)
  try {
    parsedData.value = await api.parseHex(hex)
    // Auto-expand first 3 IEs
    parsedData.value.ies.forEach((ie, idx) => {
      parsedIEExpandedMap.set(ie, idx < 3)
    })
    // Fetch raw hex for each IE from backend
    ieRawHexCache.clear()
    const hexClean = form.response_hex.replace(/\s/g, '')
    const fetchPromises = parsedData.value.ies.map(async (ie: any, idx: number) => {
      try {
        const result = await api.extractIE(hexClean, idx)
        ieRawHexCache.set(idx, result.hex)
      } catch {
        // Fallback
        if (ie.value?.raw) ieRawHexCache.set(idx, ie.value.raw)
      }
    })
    await Promise.all(fetchPromises)
    // Cache sub-IE hex for group IEs
    parsedData.value.ies.forEach((ie: any, idx: number) => {
      if (ie.group && ie.ies && ieRawHexCache.has(idx)) {
        const parentHex = ieRawHexCache.get(idx)!
        let offset = 0
        ie.ies.forEach((subIe: any) => {
          const subLen = subIe.length || 0
          // sub-IE: type(2) + length(2) + value(subLen) = 4 + subLen
          const subIeFullHex = parentHex.slice(offset * 2, (offset + 4 + subLen) * 2)
          // sub-IE value hex (skip type+length header = 4 bytes = 8 hex chars)
          subIe._rawHex = subIeFullHex.slice(8) || ''
          offset += 4 + subLen
        })
      }
    })
    // Initialize header edit values
    const h = parsedData.value.header
    headerEditMsgType.value = h.message_type !== null && h.message_type !== undefined ? String(h.message_type) : ''
    headerEditLength.value = h.length !== null && h.length !== undefined ? String(h.length) : ''
    headerEditSeid.value = h.seid !== null && h.seid !== undefined ? String(h.seid) : ''
    headerEditSeq.value = String(h.sequence_number ?? '')
    headerEditVersion.value = h.version !== null && h.version !== undefined ? String(h.version) : ''
    headerEditMP.value = !!h.mp
    headerEditFO.value = !!h.fo
    headerEditS.value = !!h.seid_flag
  } catch (e: any) {
    parseError.value = e.response?.data?.detail || e.message
    parsedData.value = null
  }
  parsing.value = false
}

function isParsedIEExpanded(ie: IEItem): boolean {
  return parsedIEExpandedMap.get(ie) ?? false
}

function toggleParsedIE(ie: IEItem) {
  const cur = isParsedIEExpanded(ie)
  parsedIEExpandedMap.set(ie, !cur)
}

function formatHexDump(hex: string): string {
  const clean = hex.replace(/\s/g, '')
  if (!clean) return ''
  const lines: string[] = []
  for (let i = 0; i < clean.length; i += 32) {
    const chunk = clean.slice(i, i + 32)
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

function resetForm() {
  form.name = ''
  form.match_msg_type = 50
  form.match_seid_str = ''
  form.response_hex = ''
  form.auto_seq = true
  form.auto_seid = false
  form.enabled = true
  editingId.value = null
  isEditing.value = false
  ieHexEdits.clear()
  deletedIEs.clear()
  newIEs.splice(0, newIEs.length)
  headerEditMsgType.value = ''
  headerEditLength.value = ''
  headerEditSeid.value = ''
  headerEditSeq.value = ''
  headerEditVersion.value = ''
  headerEditMP.value = false
  headerEditFO.value = false
  headerEditS.value = false
  showAddIE.value = false
}

function openCreateDialog() {
  resetForm()
  parsedData.value = null
  parseError.value = ''
  showDialog.value = true
}

function openEditDialog(row: Template) {
  isEditing.value = true
  editingId.value = row.id
  form.name = row.name
  form.match_msg_type = row.match_msg_type
  form.match_seid_str = row.match_seid !== null ? String(row.match_seid) : ''
  form.response_hex = row.response_hex
  form.auto_seq = row.auto_seq
  form.auto_seid = row.auto_seid
  form.enabled = row.enabled
  parsedData.value = null
  parseError.value = ''
  ieHexEdits.clear()
  deletedIEs.clear()
  newIEs.splice(0, newIEs.length)
  showDialog.value = true
  // Auto-parse on edit
  if (form.response_hex) {
    doParseHex()
  }
}

async function onSave() {
  if (!form.name.trim()) {
    ElMessage.warning('Name is required')
    return
  }
  if (!form.response_hex.trim()) {
    ElMessage.warning('Response hex is required')
    return
  }

  // Auto-apply any pending IE edits before saving
  if (parsedData.value && totalPendingChanges.value > 0) {
    try {
      const ops: api.HexOp[] = []
      const h = parsedData.value.header

      // Header edits
      if (h.seid !== null && h.seid !== undefined && headerEditSeid.value !== String(h.seid)) {
        ops.push({ op: 'edit_header', field: 'seid', value: headerEditSeid.value })
      }
      if (headerEditSeq.value !== String(h.sequence_number ?? '')) {
        ops.push({ op: 'edit_header', field: 'sequence_number', value: headerEditSeq.value })
      }

      // IE deletions (reverse order)
      const deleteIndices = [...deletedIEs].sort((a, b) => b - a)
      for (const idx of deleteIndices) {
        ops.push({ op: 'delete_ie', index: idx })
      }

      // IE edits
      for (const [idx, hex] of ieHexEdits.entries()) {
        if (!deletedIEs.has(idx)) {
          ops.push({ op: 'edit_ie', index: idx, hex })
        }
      }

      // New IEs
      for (const nie of newIEs) {
        ops.push({ op: 'add_ie', ie_type: nie.type, hex: nie.hex })
      }

      if (ops.length > 0) {
        const result = await api.rebuildHex(form.response_hex.replace(/\s/g, ''), ops)
        form.response_hex = result.hex
        // Clear edit state
        ieHexEdits.clear()
        deletedIEs.clear()
        newIEs.splice(0, newIEs.length)
      }
    } catch (e: any) {
      ElMessage.error(`Failed to apply edits before save: ${e.response?.data?.detail || e.message}`)
      saving.value = false
      return
    }
  }

  saving.value = true
  try {
    const payload: TemplateCreate = {
      name: form.name.trim(),
      match_msg_type: form.match_msg_type,
      match_seid: form.match_seid_str.trim() ? Number(form.match_seid_str) : null,
      response_hex: form.response_hex.replace(/\s/g, ''),
      auto_seq: form.auto_seq,
      auto_seid: form.auto_seid,
      enabled: form.enabled,
    }

    if (isEditing.value && editingId.value) {
      await api.updateTemplate(editingId.value, payload)
      ElMessage.success('Template updated')
    } else {
      await api.createTemplate(payload)
      ElMessage.success('Template created')
    }
    showDialog.value = false
    await loadTemplates()
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
  saving.value = false
}

async function onToggle(row: Template) {
  try {
    await api.toggleTemplate(row.id)
  } catch (e: any) {
    row.enabled = !row.enabled
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onDelete(row: Template) {
  try {
    await ElMessageBox.confirm(`Delete template "${row.name}"?`, 'Confirm', {
      type: 'warning',
    })
    await api.deleteTemplate(row.id)
    ElMessage.success('Template deleted')
    await loadTemplates()
  } catch {
    // cancelled
  }
}

/** Create a template from a captured packet */
async function createFromPacket(packet: { message_type_id: number; raw_hex: string; seid: number | null }) {
  resetForm()
  form.match_msg_type = packet.message_type_id
  form.response_hex = packet.raw_hex
  if (packet.seid !== null) {
    form.match_seid_str = ''
  }
  // Guess a name from message type
  const mt = MESSAGE_TYPES.find(m => m.value === packet.message_type_id)
  form.name = mt ? `Auto ${mt.label} Response` : `Auto Response (type ${packet.message_type_id})`
  parsedData.value = null
  parseError.value = ''
  showDialog.value = true
  // Auto-parse the captured packet
  if (form.response_hex) {
    doParseHex()
  }
}

onMounted(loadTemplates)

defineExpose({ createFromPacket, loadTemplates })
</script>

<style scoped>
.template-manager {
  padding: 4px;
}

.tm-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.tm-toolbar .el-tag {
  margin-left: auto;
}

.tmpl-name {
  font-weight: 600;
  font-size: 13px;
}

.tmpl-seid {
  font-size: 11px;
  color: #909399;
  margin-left: 4px;
}

.tmpl-size {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
}

.field-hint {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.field-hint-inline {
  font-size: 11px;
  color: #909399;
  margin-left: 8px;
}

.hex-input :deep(textarea) {
  font-family: monospace;
  font-size: 12px;
}

/* Dialog layout: form left, editor right */
.tmpl-fullscreen :deep(.el-dialog__body) {
  padding: 0 16px;
  height: calc(100vh - 120px);
  overflow: hidden;
}

.tmpl-dialog-body {
  display: flex;
  gap: 16px;
  height: 100%;
}

.tmpl-form-pane {
  width: 340px;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 8px 0;
}

.tmpl-parsed-pane {
  flex: 1;
  min-width: 0;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.parsed-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.parsed-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}

.parsed-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
  font-size: 12px;
}

/* Section headers */
.section-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  background: #f0f2f5;
  border-bottom: 1px solid #e4e7ed;
  user-select: none;
}

.section-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
}

.section-meta {
  font-size: 11px;
  color: #909399;
}

.section-body {
  padding: 8px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #fafafa;
}

/* IE blocks */
.ie-block {
  border-bottom: 1px solid #ebeef5;
}

.ie-block-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  cursor: pointer;
  background: #f5f7fa;
  user-select: none;
  line-height: 1.6;
}

.ie-block-header:hover {
  background: #ecf5ff;
}

.ie-block.ie-modified .ie-block-header {
  background: #fdf6ec;
  border-left: 3px solid #E6A23C;
}

.ie-block-body {
  padding: 8px 12px 8px 28px;
  border-top: 1px solid #ebeef5;
  background: #fff;
}

/* IE hex editor */
.ie-hex-editor {
  margin-bottom: 8px;
}

.ie-hex-label {
  font-size: 11px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 4px;
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

.ie-hex-changed {
  color: #E6A23C;
  font-weight: 600;
}

.ie-hex-changed-info {
  font-size: 11px;
  color: #E6A23C;
  padding: 2px 0;
}

/* Add IE section */
.add-ie-section {
  border-top: 2px solid #e4e7ed;
}

.add-ie-form {
  padding: 8px 12px;
}

.add-ie-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.add-ie-hex-input {
  flex: 1;
}

.add-ie-hex-input :deep(.el-input__inner) {
  font-family: monospace;
  font-size: 12px;
}

.new-ie-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  border-top: 1px dashed #e4e7ed;
  margin-top: 4px;
}

.ie-hex-preview {
  font-family: monospace;
  font-size: 11px;
  color: #909399;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Expand icon & IE title styles */
.expand-icon {
  width: 14px;
  font-size: 9px;
  color: #909399;
  flex-shrink: 0;
  text-align: center;
}

.ie-title {
  font-weight: 600;
  color: #303133;
}

.ie-summary {
  color: #409EFF;
  font-weight: 400;
}

.ie-meta {
  color: #909399;
  font-size: 11px;
  margin-left: 2px;
}

/* Editable fields */
.editable-field {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.ef-label {
  font-size: 12px;
  color: #606266;
  min-width: 120px;
  flex-shrink: 0;
}

.ef-input {
  flex: 1;
  max-width: 240px;
}

.ef-input :deep(.el-input__inner) {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

.ef-badge {
  font-size: 10px;
  color: #E6A23C;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  padding: 0 4px;
  border-radius: 2px;
  line-height: 18px;
}

.ef-readonly {
  font-family: monospace;
  font-size: 13px;
  color: #303133;
}

.ef-select {
  width: 200px;
}

.ef-input-sm {
  width: 90px;
}

.ef-input-sm :deep(.el-input__inner) {
  font-family: monospace;
  font-size: 12px;
}

.ef-hint {
  font-size: 11px;
  color: #909399;
}

.ef-flags {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: #409EFF;
  font-weight: 600;
}

/* Flag controls */
.flag-editable {
  background: #f0f9eb;
  border-radius: 3px;
  padding: 4px 8px !important;
  margin: 2px 0;
}

.flag-num {
  width: 70px;
}

.flag-num :deep(.el-input__inner) {
  font-family: 'Cascadia Code', 'Fira Code', monospace;
  font-size: 12px;
  text-align: center;
}

/* Hex actions */
.hex-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

/* Raw hex dump */
.raw-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  cursor: pointer;
  background: #f5f7fa;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  user-select: none;
}

.raw-toggle:hover {
  background: #ecf5ff;
}

.hex-dump {
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  background: #1d1e1f;
  color: #a8c088;
  padding: 8px 10px;
  margin: 0;
  overflow-x: auto;
  white-space: pre;
  max-height: 200px;
}

/* Dialog footer */
.dialog-footer {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 8px;
}

.footer-hint {
  font-size: 12px;
  color: #909399;
}
</style>
