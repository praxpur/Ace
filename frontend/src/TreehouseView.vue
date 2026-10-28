<template>
  <div class="treehouse-view">
    <div class="page-heading">
      <div><h2>智慧树</h2><p>连接账号、扫描课程，再选择要播放的视频</p></div>
      <el-tag :type="running ? 'success' : 'info'">{{ running ? '任务进行中' : '等待开始' }}</el-tag>
    </div>
    <el-tabs v-model="tab">
      <el-tab-pane label="连接与设置" name="settings">
        <el-card shadow="never">
          <el-form label-width="130px" class="settings-form">
            <el-form-item label="课程入口"><el-input v-model="options.url" /></el-form-item>
            <el-form-item label="登录态文件"><el-input v-model="options.state_path" placeholder="首次登录会保存到此处" /></el-form-item>
            <el-form-item label="记住登录"><el-switch v-model="options.remember" /></el-form-item>
            <el-form-item label="无头运行"><el-switch v-model="options.headless" /><span class="hint">首次登录请关闭</span></el-form-item>
            <el-form-item label="连接方式"><el-radio-group v-model="options.connection_mode"><el-radio value="system">跟随系统</el-radio><el-radio value="direct">直接连接</el-radio></el-radio-group></el-form-item>
            <el-form-item label="播放速度"><el-select v-model="options.speed" style="width: 160px"><el-option v-for="rate in rates" :key="rate" :label="`${rate}×`" :value="rate" /></el-select></el-form-item>
            <el-form-item><el-button type="primary" :loading="starting" :disabled="running" @click="start">连接并选择课程</el-button></el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="课程与视频" name="catalog">
        <el-alert v-if="request" :title="request.title === '课程' ? '请选择课程，确认后会扫描全部所选课程' : '扫描完成，请手动勾选要播放的视频'" type="info" :closable="false" class="notice" />
        <el-card shadow="never" v-if="request?.title === '课程'">
          <template #header>课程列表 · 已选 {{ selected.length }} 门</template>
          <el-input v-model="query" placeholder="搜索课程" clearable class="search" />
          <el-checkbox-group v-model="selected" class="choice-list">
            <el-checkbox v-for="item in visibleChoices" :key="item.key" :value="item.key" class="choice-row">
              <span>{{ item.label }}</span><small v-if="item.detail">{{ item.detail }}</small>
            </el-checkbox>
          </el-checkbox-group>
        </el-card>
        <el-card shadow="never" v-else-if="request?.title === '视频'">
          <template #header>播放清单 · 已选 {{ selected.length }} 个视频</template>
          <el-select v-model="activeCourse" placeholder="选择课程" class="course-picker">
            <el-option v-for="group in groups" :key="group.key" :label="`${group.course.label} (${group.videos.length})`" :value="group.key" />
          </el-select>
          <el-input v-model="query" placeholder="搜索视频" clearable class="search" />
          <el-checkbox-group v-model="selected" class="choice-list">
            <el-checkbox v-for="item in visibleChoices" :key="item.key" :value="item.key" class="choice-row">
              <span>{{ item.label }}</span><small v-if="item.detail">{{ item.detail }}</small>
            </el-checkbox>
          </el-checkbox-group>
        </el-card>
        <el-empty v-else description="连接后，课程和视频选择会显示在这里" />
        <div v-if="request" class="actions"><el-button type="primary" :disabled="selected.length === 0" @click="confirmSelection">{{ request.title === '课程' ? '扫描所选课程' : '开始播放所选视频' }}</el-button></div>
      </el-tab-pane>
      <el-tab-pane label="运行监控" name="monitor">
        <el-card shadow="never" class="monitor-card">
          <div class="monitor-top"><strong>{{ phase }}</strong><el-button :disabled="!running" @click="stop">停止任务</el-button></div>
          <p>{{ message }}</p>
          <el-progress :percentage="progress" :status="progress === 100 ? 'success' : undefined" />
          <p v-if="queueTotal">队列 {{ queueCompleted }} / {{ queueTotal }}</p>
        </el-card>
        <el-card shadow="never" class="log-card"><template #header>运行日志</template><div class="logs"><div v-for="(line, index) in logs" :key="index">{{ line }}</div></div></el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

type Choice = {key: string, label: string, detail?: string}
type Request = {request_id: string, title: string, choices: Choice[]}
type Group = {key: string, course: Choice, videos: Choice[]}
const api = async (method: string, ...args: unknown[]) => {
  const bridge = (window as any).pywebview?.api
  if (!bridge) throw new Error('桌面服务尚未就绪')
  return bridge[method](...args)
}
const options = ref({url: '', state_path: '', remember: true, headless: false, connection_mode: 'system', speed: 1})
const rates = [1, 1.25, 1.5, 1.75, 2, 3, 4]
const tab = ref('settings')
const running = ref(false)
const starting = ref(false)
const request = ref<Request | null>(null)
const groups = ref<Group[]>([])
const activeCourse = ref('')
const selected = ref<string[]>([])
const query = ref('')
const phase = ref('尚未开始')
const message = ref('连接账号后，按步骤选择课程与视频。')
const progress = ref(0)
const queueCompleted = ref(0)
const queueTotal = ref(0)
const logs = ref<string[]>([])
const visibleChoices = computed(() => {
  let items = request.value?.choices || []
  if (request.value?.title === '视频' && activeCourse.value) {
    const keys = new Set(groups.value.find(group => group.key === activeCourse.value)?.videos.map(video => video.key) || [])
    items = items.filter(item => keys.has(item.key))
  }
  const filter = query.value.trim().toLowerCase()
  return filter ? items.filter(item => `${item.label} ${item.detail || ''}`.toLowerCase().includes(filter)) : items
})
const initialize = async () => {
  try { const result = await api('treehouse_defaults'); if (result.success) Object.assign(options.value, result.data) } catch { /* wait for pywebviewready */ }
}
const start = async () => {
  starting.value = true
  try {
    const result = await api('treehouse_start', options.value)
    if (!result.success) throw new Error(result.msg)
    running.value = true; request.value = null; groups.value = []; selected.value = []; logs.value = []
    phase.value = '正在连接'; message.value = '浏览器启动后，请在浏览器中完成登录。'; progress.value = 0
    tab.value = 'monitor'
  } catch (error) { ElMessage.error(String(error)) } finally { starting.value = false }
}
const confirmSelection = async () => {
  if (!request.value || !selected.value.length) return
  try {
    const result = await api('treehouse_select', request.value.request_id, selected.value)
    if (!result.success) throw new Error(result.msg)
    request.value = null; selected.value = []; query.value = ''; tab.value = 'monitor'
  } catch (error) { ElMessage.error(String(error)) }
}
const stop = async () => { await api('treehouse_stop'); message.value = '正在停止任务…' }
const poll = async () => {
  try {
    const result = await api('treehouse_updates')
    running.value = result.running
    for (const event of result.events || []) {
      const data = event.data || {}
      if (event.kind === 'phase') { phase.value = data.phase; message.value = data.message }
      if (event.kind === 'log') { logs.value.push(data.message); if (logs.value.length > 500) logs.value.shift() }
      if (event.kind === 'selection_request') {
        request.value = data; selected.value = []; query.value = ''; tab.value = 'catalog'
        if (data.title === '视频') activeCourse.value = groups.value[0]?.key || ''
      }
      if (event.kind === 'catalog_ready') { groups.value = data.groups || []; activeCourse.value = groups.value[0]?.key || '' }
      if (event.kind === 'progress') progress.value = Math.max(0, Math.min(100, Number(data.percent) || 0))
      if (event.kind === 'queue') { queueCompleted.value = data.completed; queueTotal.value = data.total }
      if (event.kind === 'finished') { running.value = false; phase.value = data.status; message.value = data.message; tab.value = 'monitor' }
    }
  } catch { /* desktop bridge may still be initializing */ }
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => { window.addEventListener('pywebviewready', initialize); initialize(); timer = setInterval(poll, 500) })
onUnmounted(() => { window.removeEventListener('pywebviewready', initialize); if (timer) clearInterval(timer) })
</script>

<style scoped>
.treehouse-view { max-width: 980px; margin: auto; }
.page-heading,.monitor-top { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.page-heading { margin-bottom: 16px; }
.page-heading h2 { margin:0 0 4px; font-size:24px; }
.page-heading p,.hint { color:var(--el-text-color-secondary); font-size:13px; }
.hint { margin-left:12px; }
.settings-form { max-width:720px; }
.notice,.search,.course-picker { margin-bottom:14px; }
.course-picker { width:100%; }
.choice-list { display:flex; flex-direction:column; max-height:420px; overflow:auto; }
.choice-row { width:100%; min-height:46px; margin:0; border-bottom:1px solid var(--el-border-color-lighter); }
.choice-row :deep(.el-checkbox__label) { display:flex; flex-direction:column; white-space:normal; padding:10px 0; }
.choice-row small { color:var(--el-text-color-secondary); font-size:12px; }
.actions { display:flex; justify-content:flex-end; margin-top:16px; }
.monitor-card { margin-bottom:16px; }
.logs { height:260px; overflow:auto; font:12px/1.6 Consolas,monospace; white-space:pre-wrap; }
</style>
