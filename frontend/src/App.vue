<template>
  <el-container class="app-container">
    <!-- Header -->
    <el-header class="app-header">
      <div class="header-left">
        <el-icon size="28" color="#409EFF"><Connection /></el-icon>
        <h1 class="app-title">N4Relay</h1>
        <el-tag :type="status.running ? 'success' : 'danger'" size="large" effect="dark">
          {{ status.running ? 'RUNNING' : 'STOPPED' }}
        </el-tag>
      </div>
      <div class="header-center">
        <el-space :size="16">
          <el-button
            :type="status.running ? 'danger' : 'success'"
            @click="toggleRelay"
            :loading="loading.relay"
          >
            <el-icon><VideoPlay v-if="!status.running" /><VideoPause v-else /></el-icon>
            {{ status.running ? 'Stop Relay' : 'Start Relay' }}
          </el-button>
          <el-divider direction="vertical" />
          <el-tag type="info">
            Target: {{ status.target_addr }}:{{ status.target_port }}
          </el-tag>
          <el-button size="small" @click="showTargetDialog = true">
            <el-icon><Setting /></el-icon>
          </el-button>
        </el-space>
      </div>
      <div class="header-right">
        <el-space :size="12">
          <span class="intercept-label">Intercept:</span>
          <el-switch
            v-model="status.intercept_enabled"
            @change="toggleIntercept"
            active-color="#E6A23C"
            :loading="loading.intercept"
          />
          <el-divider direction="vertical" />
          <el-tag>Packets: {{ status.packets_captured }}</el-tag>
          <el-tag type="warning" v-if="status.packets_intercepted > 0">
            Intercepted: {{ status.packets_intercepted }}
          </el-tag>
          <el-tag type="info" v-if="status.queue_depth > 0">
            Queue: {{ status.queue_depth }}/{{ status.queue_max_size }}
          </el-tag>
          <el-tag type="danger" v-if="status.queue_overflow_dropped > 0">
            Dropped: {{ status.queue_overflow_dropped }}
          </el-tag>
          <el-tag v-if="status.uptime_seconds" type="info">
            Uptime: {{ formatUptime(status.uptime_seconds) }}
          </el-tag>
        </el-space>
      </div>
    </el-header>

    <!-- Main Content -->
    <el-container class="main-content">
      <!-- Left: Packet List -->
      <div class="packet-main" :style="{ width: leftWidth + 'px' }">
        <PacketList
          :packets="packets"
          :total="totalPackets"
          :currentPage="currentPage"
          :pageSize="pageSize"
          @select="onPacketSelect"
          @clear="onClearPackets"
          @refresh="(msgType: string, dir: string, excludeHb: boolean) => { currentPage = 1; loadPackets(msgType, dir, excludeHb) }"
          @page-change="(page: number, size: number) => onPageChange(page, size)"
        />
      </div>

      <!-- Resize Handle -->
      <div
        class="resize-handle"
        @mousedown="onResizeStart"
        :class="{ active: isResizing }"
      >
        <div class="resize-grip"></div>
      </div>

      <!-- Right: Packet Detail + Intercept Panel -->
      <div class="detail-panel" :style="{ width: rightWidth + 'px' }">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="Packet Detail" name="detail">
            <div v-if="selectedPacket" class="detail-actions">
              <el-button size="small" type="warning" @click="onSaveAsTemplate">
                <el-icon><DocumentCopy /></el-icon> Save as Template
              </el-button>
            </div>
            <PacketDetail v-if="selectedPacket" :packet="selectedPacket" />
            <el-empty v-else description="Select a packet to view details" />
          </el-tab-pane>
          <el-tab-pane name="intercept">
            <template #label>
              Intercept Panel
              <el-badge :value="intercepted.length" :hidden="intercepted.length === 0" class="badge" />
            </template>
            <InterceptPanel
              :intercepted="intercepted"
              @release="onRelease"
              @drop="onDrop"
              @release-all="onReleaseAll"
              @drop-all="onDropAll"
              @select="onInterceptSelect"
              @refresh="loadIntercepted"
            />
          </el-tab-pane>
          <el-tab-pane label="Templates" name="templates">
            <TemplateManager ref="templateManagerRef" />
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-container>

    <!-- Target Config Dialog -->
    <el-dialog v-model="showTargetDialog" title="Target Configuration" width="400px">
      <el-form label-width="100px">
        <el-form-item label="Target Addr">
          <el-input v-model="targetForm.addr" placeholder="UPF hostname or IP" />
        </el-form-item>
        <el-form-item label="Target Port">
          <el-input-number v-model="targetForm.port" :min="1" :max="65535" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showTargetDialog = false">Cancel</el-button>
        <el-button type="primary" @click="updateTarget" :loading="loading.target">Update</el-button>
      </template>
    </el-dialog>

    <!-- Intercept Edit Dialog -->
    <el-dialog v-model="showEditDialog" title="Edit Intercepted Packet" width="700px" top="5vh">
      <FieldEditor
        v-if="editingIntercept"
        :key="editingIntercept.id"
        :detail="editingIntercept"
        @save="onSaveEdit"
        @cancel="showEditDialog = false"
      />
    </el-dialog>
  </el-container>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { StatusResponse, PacketSummary, PacketDetail, InterceptedPacket, InterceptedPacketDetail } from './types'
import * as api from './api'
import { packetWS, interceptWS } from './api/websocket'
import PacketList from './components/PacketList.vue'
import PacketDetailComp from './components/PacketDetail.vue'
import InterceptPanel from './components/InterceptPanel.vue'
import FieldEditor from './components/FieldEditor.vue'
import TemplateManager from './components/TemplateManager.vue'

// Rename the component to avoid collision with the type
const PacketDetail = PacketDetailComp

const status = reactive<StatusResponse>({
  running: false,
  intercept_enabled: false,
  target_addr: '',
  target_port: 8805,
  listen_addr: '',
  listen_port: 8805,
  packets_captured: 0,
  packets_intercepted: 0,
  uptime_seconds: null,
  queue_depth: 0,
  queue_max_size: 0,
  queue_overflow_dropped: 0,
  queue_processed_total: 0,
  worker_count: 0,
})

const packets = ref<PacketSummary[]>([])
const totalPackets = ref(0)
const intercepted = ref<InterceptedPacket[]>([])
const selectedPacket = ref<PacketDetail | null>(null)
const activeTab = ref('detail')
const packetFilterMsgType = ref('')
const packetFilterDirection = ref('')
const packetFilterHeartbeat = ref(true)
const currentPage = ref(1)
const pageSize = ref(50)
const showTargetDialog = ref(false)
const showEditDialog = ref(false)
const editingIntercept = ref<InterceptedPacketDetail | null>(null)
const templateManagerRef = ref<InstanceType<typeof TemplateManager> | null>(null)

const targetForm = reactive({ addr: '', port: 8805 })
const loading = reactive({ relay: false, intercept: false, target: false })

// Resizable panel state
const HANDLE_WIDTH = 6
const MIN_LEFT = 300
const MIN_RIGHT = 420
const rightWidth = ref(580)
const leftWidth = ref(0)
const isResizing = ref(false)
let startX = 0
let startRightWidth = 0

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  isResizing.value = true
  startX = e.clientX
  startRightWidth = rightWidth.value

  const onMouseMove = (ev: MouseEvent) => {
    const delta = startX - ev.clientX
    const containerWidth = window.innerWidth
    const newRight = Math.max(MIN_RIGHT, Math.min(startRightWidth + delta, containerWidth - MIN_LEFT - HANDLE_WIDTH))
    rightWidth.value = newRight
    leftWidth.value = containerWidth - newRight - HANDLE_WIDTH
  }
  const onMouseUp = () => {
    isResizing.value = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

let statusTimer: ReturnType<typeof setInterval> | null = null

function formatUptime(seconds: number | null): string {
  if (!seconds) return '0s'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

async function loadStatus() {
  try {
    const s = await api.getStatus()
    Object.assign(status, s)
  } catch (e) {
    console.error('Failed to load status', e)
  }
}

async function loadPackets(msgType?: string, direction?: string, excludeHeartbeat?: boolean) {
  // Store filter state
  if (msgType !== undefined) packetFilterMsgType.value = msgType
  if (direction !== undefined) packetFilterDirection.value = direction
  if (excludeHeartbeat !== undefined) packetFilterHeartbeat.value = excludeHeartbeat
  try {
    const offset = (currentPage.value - 1) * pageSize.value
    const res = await api.listPackets(offset, pageSize.value, packetFilterMsgType.value || undefined, packetFilterDirection.value || undefined, packetFilterHeartbeat.value)
    packets.value = res.packets
    totalPackets.value = res.total
  } catch (e) {
    console.error('Failed to load packets', e)
  }
}

function onPageChange(page: number, size: number) {
  currentPage.value = page
  if (size !== pageSize.value) {
    pageSize.value = size
    currentPage.value = 1
  }
  loadPackets()
}

async function loadIntercepted() {
  try {
    intercepted.value = await api.listIntercepted()
  } catch (e) {
    console.error('Failed to load intercepted', e)
  }
}

async function toggleRelay() {
  loading.relay = true
  try {
    const s = await api.updateStatus({ running: !status.running })
    Object.assign(status, s)
    ElMessage.success(`Relay ${status.running ? 'started' : 'stopped'}`)
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
  loading.relay = false
}

async function toggleIntercept(val: boolean | string | number) {
  loading.intercept = true
  try {
    const s = await api.updateStatus({ intercept_enabled: !!val })
    Object.assign(status, s)
    ElMessage.success(`Intercept ${status.intercept_enabled ? 'enabled' : 'disabled'}`)
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
  loading.intercept = false
}

async function updateTarget() {
  loading.target = true
  try {
    const s = await api.updateStatus({ target_addr: targetForm.addr, target_port: targetForm.port })
    Object.assign(status, s)
    showTargetDialog.value = false
    ElMessage.success('Target updated')
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
  loading.target = false
}

async function onPacketSelect(pkt: PacketSummary) {
  try {
    selectedPacket.value = await api.getPacket(pkt.id)
    activeTab.value = 'detail'
  } catch (e: any) {
    ElMessage.error(`Failed to load packet: ${e.message}`)
  }
}

async function onClearPackets() {
  try {
    await api.clearPackets()
    packets.value = []
    totalPackets.value = 0
    selectedPacket.value = null
    ElMessage.success('Packets cleared')
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onRelease(id: string) {
  try {
    await api.releaseIntercepted(id)
    ElMessage.success('Packet released')
    await loadIntercepted()
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onDrop(id: string) {
  try {
    await api.dropIntercepted(id)
    ElMessage.success('Packet dropped')
    await loadIntercepted()
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onReleaseAll() {
  try {
    const res = await api.releaseAllIntercepted()
    ElMessage.success(res.message)
    await loadIntercepted()
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onDropAll() {
  try {
    const res = await api.dropAllIntercepted()
    ElMessage.success(res.message)
    await loadIntercepted()
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

async function onInterceptSelect(id: string) {
  try {
    editingIntercept.value = await api.getIntercepted(id)
    showEditDialog.value = true
  } catch (e: any) {
    ElMessage.error(`Failed to load intercept detail: ${e.message}`)
  }
}

async function onSaveEdit(id: string, modifications: Record<string, any>) {
  try {
    await api.modifyIntercepted(id, { modifications })
    ElMessage.success('Modifications saved. They will apply on release.')
    showEditDialog.value = false
  } catch (e: any) {
    ElMessage.error(`Failed: ${e.message}`)
  }
}

function onSaveAsTemplate() {
  if (!selectedPacket.value || !templateManagerRef.value) return
  templateManagerRef.value.createFromPacket({
    message_type_id: selectedPacket.value.message_type_id,
    raw_hex: selectedPacket.value.raw_hex,
    seid: selectedPacket.value.seid,
  })
  activeTab.value = 'templates'
}

// WebSocket handlers
function onPacketWS(msg: any) {
  if (msg.type === 'new_packet') {
    const pkt = msg.data
    // Apply heartbeat filter client-side
    if (packetFilterHeartbeat.value && (pkt.message_type_id === 1 || pkt.message_type_id === 2)) {
      totalPackets.value++ // still count it, but don't display
      return
    }
    // Apply message type filter client-side
    if (packetFilterMsgType.value) {
      const filterId = Number(packetFilterMsgType.value)
      if (!isNaN(filterId) && pkt.message_type_id !== filterId) return
    }
    // Apply direction filter client-side
    if (packetFilterDirection.value && !(pkt.direction || '').toLowerCase().includes(packetFilterDirection.value.toLowerCase())) {
      return
    }
    // Prepend new packet
    packets.value.unshift(pkt)
    totalPackets.value++
    // Trim to 200
    if (packets.value.length > 200) {
      packets.value = packets.value.slice(0, 200)
    }
  }
}

function onInterceptWS(msg: any) {
  if (msg.type === 'new_intercept') {
    loadIntercepted()
  }
}

onMounted(async () => {
  await loadStatus()
  await loadPackets()
  await loadIntercepted()

  targetForm.addr = status.target_addr
  targetForm.port = status.target_port

  // Calculate initial panel widths
  const containerWidth = window.innerWidth
  leftWidth.value = containerWidth - rightWidth.value - HANDLE_WIDTH

  // Start WebSocket connections
  packetWS.onMessage(onPacketWS)
  interceptWS.onMessage(onInterceptWS)
  packetWS.connect()
  interceptWS.connect()

  // Poll status every 5s
  statusTimer = setInterval(loadStatus, 5000)

  // Handle window resize
  window.addEventListener('resize', onWindowResize)
})

function onWindowResize() {
  const containerWidth = window.innerWidth
  if (rightWidth.value > containerWidth - MIN_LEFT - HANDLE_WIDTH) {
    rightWidth.value = containerWidth - MIN_LEFT - HANDLE_WIDTH
  }
  leftWidth.value = containerWidth - rightWidth.value - HANDLE_WIDTH
}

onUnmounted(() => {
  packetWS.removeHandler(onPacketWS)
  interceptWS.removeHandler(onInterceptWS)
  packetWS.disconnect()
  interceptWS.disconnect()
  if (statusTimer) clearInterval(statusTimer)
  window.removeEventListener('resize', onWindowResize)
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', Arial, sans-serif;
}

.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1d1e1f;
  color: #fff;
  padding: 0 20px;
  height: 60px !important;
  border-bottom: 2px solid #409EFF;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  color: #409EFF;
}

.header-center {
  display: flex;
  align-items: center;
}

.intercept-label {
  font-size: 14px;
  color: #ccc;
}

.header-right {
  display: flex;
  align-items: center;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: row;
  background: #060e1a;
}

.packet-main {
  padding: 12px;
  overflow: auto;
  flex-shrink: 0;
  background: #060e1a;
}

.resize-handle {
  width: 6px;
  cursor: col-resize;
  background: #0d1f3c;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  position: relative;
  z-index: 10;
}

.resize-handle:hover,
.resize-handle.active {
  background: #409EFF;
}

.resize-grip {
  width: 2px;
  height: 40px;
  background: #2a4a6a;
  border-radius: 1px;
}

.resize-handle:hover .resize-grip,
.resize-handle.active .resize-grip {
  background: #fff;
}

.detail-panel {
  border-left: 1px solid #1a2a4a;
  background: #060e1a;
  overflow: auto;
  flex-shrink: 0;
}

.detail-panel .el-tabs {
  height: 100%;
}

.detail-panel .el-tabs__header {
  background: #0a1628;
  border-bottom: 1px solid #1a2a4a;
  margin-bottom: 0;
}

.detail-panel .el-tabs__item {
  color: #6a8aaa;
}

.detail-panel .el-tabs__item.is-active {
  color: #409eff;
}

.detail-panel .el-tabs__active-bar {
  background-color: #409eff;
}

.detail-panel .el-tabs__content {
  padding: 12px;
  overflow: auto;
  height: calc(100% - 40px);
  color: #bcc8d4;
}

.badge {
  margin-left: 6px;
}

.detail-actions {
  margin-bottom: 8px;
}

/* ── Global Element Plus Dark Overrides (teleported poppers) ── */
.el-select__wrapper {
  background-color: #0d1f3c !important;
  box-shadow: 0 0 0 1px #1a3050 inset !important;
}

.el-select__wrapper.is-hovering:not(.is-focused) {
  box-shadow: 0 0 0 1px #2a4a6a inset !important;
}

.el-select__wrapper.is-focused {
  box-shadow: 0 0 0 1px #409eff inset !important;
}

.el-select__placeholder {
  color: #bcc8d4 !important;
}

.el-select__placeholder.is-transparent {
  color: #5a7a9a !important;
}

.el-popper.is-light {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
}

.el-select-dropdown {
  background: #0d1f3c !important;
  border: 1px solid #1a3050 !important;
}

.el-select-dropdown__item {
  color: #bcc8d4 !important;
}

.el-select-dropdown__item.hover,
.el-select-dropdown__item:hover {
  background: rgba(64, 158, 255, 0.1) !important;
}

.el-select-dropdown__item.selected {
  color: #409eff !important;
  font-weight: 600;
}

.el-popper.is-light .el-popper__arrow::before {
  background: #0d1f3c !important;
  border-color: #1a3050 !important;
}

/* scrollbar in dropdowns */
.el-select-dropdown .el-scrollbar__bar.is-vertical {
  width: 5px;
}
.el-select-dropdown .el-scrollbar__thumb {
  background: #1a3050 !important;
}
</style>
