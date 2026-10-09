<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import type { FloorPlan } from '@roomcraft/shared-schema'
import PrototypeCanvas from '@/components/PrototypeCanvas.vue'
import PlanIllustration from '@/components/PlanIllustration.vue'
import { loadDemoPlan, validatePlan } from '@/scene/planLoader'
import { useAppStore } from '@/store/app'

type Page = 'home' | 'upload' | 'preview'
const initialPage = (): Page => location.hash === '#upload' ? 'upload' : location.hash === '#preview' || location.search.includes('view=walk') ? 'preview' : 'home'
const page = ref<Page>(initialPage())
const canvasRef = ref<InstanceType<typeof PrototypeCanvas>>()
const fileInput = ref<HTMLInputElement>()
const store = useAppStore()
const plan = ref<FloorPlan>(loadDemoPlan())
const file = ref<File | null>(null)
const imageUrl = ref('')
const loading = ref(false)
const dragOver = ref(false)
const error = ref('')
const isExample = ref(true)
const simulated = ref(false)
let controller: AbortController | null = null
const openings = computed(() => plan.value.walls.reduce((sum, wall) => sum + wall.openings.length, 0))
const roomArea = (room: FloorPlan['rooms'][number]): string => {
  const points = room.polygon ?? []
  if (points.length < 3) return '—'
  const sum = points.reduce((s, p, i) => { const q = points[(i + 1) % points.length]; return s + p.x * q.y - q.x * p.y }, 0)
  return (Math.abs(sum) / 2).toFixed(1)
}
function navigate(next: Page): void {
  if (loading.value) { controller?.abort(); controller = null; loading.value = false }
  page.value = next
  location.hash = next === 'home' ? '' : next
  void nextTick(() => window.scrollTo(0, 0))
}
function onHashChange(): void {
  const next = initialPage()
  if (next !== page.value && loading.value) { controller?.abort(); controller = null; loading.value = false }
  page.value = next
  void nextTick(() => window.scrollTo(0, 0))
}
window.addEventListener('hashchange', onHashChange)
function example(): void {
  plan.value = loadDemoPlan()
  isExample.value = true
  simulated.value = false
  navigate('preview')
}
function choose(selected?: File): void {
  if (!selected || loading.value) return
  error.value = ''
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) { error.value = '请选择 JPG、PNG 或 WebP 图片。'; return }
  if (selected.size > 10 * 1024 * 1024) { error.value = '图片不能超过 10 MB，请压缩后重试。'; return }
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  file.value = selected
  imageUrl.value = URL.createObjectURL(selected)
}
function drop(event: DragEvent): void { dragOver.value = false; choose(event.dataTransfer?.files[0]) }
async function recognize(): Promise<void> {
  if (!file.value || loading.value) return
  loading.value = true
  error.value = ''
  const requestController = new AbortController()
  controller = requestController
  const timeout = window.setTimeout(() => requestController.abort(), 320_000)
  try {
    const response = await fetch('/api/plans/recognize', { method: 'POST', headers: { 'Content-Type': file.value.type }, body: file.value, signal: requestController.signal })
    const result = await response.json().catch(() => null)
    if (!response.ok) throw new Error(typeof result?.detail === 'string' ? result.detail : '识别服务未连接，请确认后端已启动后重试。')
    if (requestController.signal.aborted) return
    plan.value = validatePlan(result.plan)
    simulated.value = result.simulated === true
    isExample.value = false
    loading.value = false
    navigate('preview')
  } catch (cause) {
    if (controller === requestController && page.value === 'upload') error.value = cause instanceof Error && cause.name === 'AbortError' ? '识别等待超时，请稍后重试。' : cause instanceof Error ? cause.message : '识别失败，请重试。'
  } finally {
    window.clearTimeout(timeout)
    if (controller === requestController) { loading.value = false; controller = null }
  }
}
async function view(mode: 'top' | 'walk'): Promise<void> {
  if (store.viewMode === 'transition') return
  if (mode !== store.viewMode) await canvasRef.value?.toggleWalk()
}
function download(): void {
  const url = canvasRef.value?.snapshot()
  if (!url) return
  const a = document.createElement('a'); a.href = url; a.download = 'roomcraft-preview.png'; a.click()
}
onBeforeUnmount(() => {
  controller?.abort()
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  window.removeEventListener('hashchange', onHashChange)
})
</script>

<template>
  <div class="site" :class="{ 'workspace-site': page === 'preview' }">
    <header class="site-header">
      <button class="wordmark" aria-label="RoomCraft 首页" @click="navigate('home')"><span class="brand-symbol">R<span>↗</span></span>RoomCraft<span class="brand-period">.</span></button>
      <nav v-if="page !== 'preview'" aria-label="主导航">
        <button class="nav-link" :class="{ active: page === 'home' }" @click="navigate('home')">产品介绍</button>
        <button class="nav-link" @click="example">体验示例 <span>↗</span></button>
        <button class="button dark compact" @click="navigate('upload')">开始我的设计 <span>→</span></button>
      </nav>
      <div v-else class="workspace-header-actions"><span class="status-dot"></span><span class="status-label">{{ simulated ? '模拟预览' : isExample ? '示例体验' : '户型预览' }}</span><button class="button outline compact" @click="navigate('upload')">上传新户型 <span>＋</span></button></div>
    </header>

    <main v-if="page === 'home'" class="home page-enter">
      <section class="hero">
        <div class="hero-copy">
          <div class="eyebrow"><span class="tiny-line"></span> YOUR SPACE, REIMAGINED</div>
          <h1>一张户型图，<br>看见家的<span class="serif">可能。</span></h1>
          <p class="hero-description">把平面的想象，变成立体的空间。<br>上传户型图，让 AI 帮你读懂布局，走进未来的家。</p>
          <div class="hero-actions"><button class="button dark" @click="navigate('upload')">上传我的户型 <span>↗</span></button><button class="text-button" @click="example">先看看示例 <span>→</span></button></div>
          <div class="hero-note"><span class="status-dot"></span>无需注册即可开始 · 支持 JPG / PNG / WebP</div>
        </div>
        <button class="hero-art" aria-label="打开示例户型预览" @click="example">
          <div class="art-caption"><span>SPACE STUDY / 001</span><span>↗</span></div>
          <div class="art-halo"></div><div class="art-plan"><PlanIllustration /></div>
          <div class="art-bottom"><div><span class="art-kicker">从一张图，到一个家</span><strong>两室两厅 · 空间预览</strong></div><span class="round-arrow">↗</span></div>
          <span class="art-watermark">ROOM<br>CRAFT</span>
        </button>
      </section>
      <section class="process" aria-label="使用流程">
        <div class="process-intro"><span class="eyebrow">LESS EFFORT. MORE SPACE.</span><h2>三步，走进你的家。</h2></div>
        <div class="process-grid">
          <article><span class="step-number">01 /</span><h3>上传户型图</h3><p>一张带尺寸标注的清晰图片，<br>就是探索空间的起点。</p></article>
          <article><span class="step-number">02 /</span><h3>看清空间布局</h3><p>从俯视理解房间关系，<br>再切换行走视角感受空间。</p></article>
          <article><span class="step-number">03 /</span><h3>留住设计灵感</h3><p>对照原图检查识别结果，<br>导出预览，继续构想理想的家。</p></article>
        </div>
      </section>
      <footer class="home-footer"><span>RoomCraft · 让空间想象，触手可及。</span><span>DESIGNED AROUND YOU.</span></footer>
    </main>

    <main v-else-if="page === 'upload'" class="upload-page page-enter">
      <button class="back-link" @click="navigate('home')">← 返回首页</button>
      <div class="upload-heading"><div class="eyebrow">START WITH YOUR FLOOR PLAN</div><h1>家的新可能，<br>从这张图开始。</h1><p>上传清晰的户型图片，我们为你构建空间预览。</p></div>
      <div class="upload-layout">
        <section class="upload-card" :aria-busy="loading">
          <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" class="file-input" aria-label="选择户型图片" :disabled="loading" @change="choose(($event.target as HTMLInputElement).files?.[0])">
          <button class="drop-zone" :class="{ dragging: dragOver, selected: file }" :disabled="loading" @click="fileInput?.click()" @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="drop">
            <img v-if="imageUrl" :src="imageUrl" alt="待识别的户型原图">
            <template v-else><span class="upload-symbol">↑</span><strong>拖拽户型图到这里</strong><span>或点击选择图片</span><small>JPG / PNG / WebP · 最大 10 MB</small></template>
          </button>
          <div v-if="file" class="file-meta"><div><strong>{{ file.name }}</strong><span>{{ (file.size / 1024 / 1024).toFixed(2) }} MB · 点击图片可重新选择</span></div><span>✓</span></div>
          <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
          <div v-if="loading" class="recognition-progress" role="status"><span class="spinner"></span><div><strong>正在读懂你的空间…</strong><span>识别墙体、门窗与房间，可能需要几分钟。请保持页面打开。</span></div></div>
          <button class="button dark full" :disabled="!file || loading" @click="recognize">{{ loading ? '正在构建空间' : '生成户型预览' }}<span v-if="!loading">→</span></button>
          <p class="upload-privacy">点击生成后，图片将发送至识别服务，用于解析你的户型。</p>
        </section>
        <aside class="upload-guide"><span class="eyebrow">A BETTER START</span><h2>好图片，<br>让空间更准确。</h2><div class="guide-item"><span>01</span><div><h3>保留尺寸标注</h3><p>完整的长度标注帮助确定真实比例。暂无尺寸的图片暂不支持。</p></div></div><div class="guide-item"><span>02</span><div><h3>保持清晰、完整</h3><p>电子户型图识别更稳定；翻拍时尽量正对图纸，避免反光和裁切。</p></div></div><div class="guide-item"><span>03</span><div><h3>预览后对照检查</h3><p>AI 识别可能存在偏差，请对照原图确认墙体、房间与门窗。</p></div></div><div class="guide-example"><span>还没有准备好图片？</span><button class="text-button" @click="example">体验示例户型 →</button></div></aside>
      </div>
    </main>

    <main v-else class="workspace page-enter">
      <section class="workspace-main">
        <div class="workspace-title"><div><span class="eyebrow">{{ isExample ? 'EXAMPLE FLOOR PLAN' : 'YOUR FLOOR PLAN' }}</span><h1>{{ plan.meta.name || '我的户型' }}</h1></div><span class="view-description">{{ store.viewMode === 'walk' ? '走进空间，感受真实尺度' : store.viewMode === 'transition' ? '正在切换视角…' : '从上方，看清家的每一个角落' }}</span></div>
        <div class="viewport"><PrototypeCanvas ref="canvasRef" :plan="plan" /><div class="viewport-controls" role="group" aria-label="预览视角"><button :class="{ selected: store.viewMode === 'top' }" :aria-pressed="store.viewMode === 'top'" :disabled="store.viewMode === 'transition'" @click="view('top')">▦ 俯视布局</button><button :class="{ selected: store.viewMode === 'walk' }" :aria-pressed="store.viewMode === 'walk'" :disabled="store.viewMode === 'transition'" @click="view('walk')">↗ 行走体验</button></div><button class="reset-button" :disabled="store.viewMode !== 'top'" aria-label="复位视角" title="复位视角" @click="canvasRef?.resetTopView()">↺</button></div>
      </section>
      <aside class="workspace-sidebar">
        <section class="sidebar-summary"><span class="eyebrow">SPACE OVERVIEW</span><h2>你的空间，一目了然。</h2><div class="summary-stats"><div><strong>{{ plan.rooms.length }}</strong><span>房间</span></div><div><strong>{{ plan.walls.length }}</strong><span>墙段</span></div><div><strong>{{ openings }}</strong><span>门窗</span></div></div></section>
        <section class="room-section"><div class="section-label">房间一览 <span>面积 / m²</span></div><div v-for="(room, i) in plan.rooms" :key="room.id" class="room-row"><span class="room-index">{{ String(i + 1).padStart(2, '0') }}</span><span>{{ room.name }}</span><strong>{{ roomArea(room) }}</strong></div></section>
        <section class="original-section"><div class="section-label">{{ isExample ? '示例平面图' : '上传原图' }}<span>对照参考</span></div><div class="original-image"><PlanIllustration v-if="isExample" /><img v-else :src="imageUrl" alt="上传的户型原图"></div></section>
        <div class="sidebar-bottom"><p v-if="simulated" class="inline-error">当前服务使用模拟模型，展示的户型仅用于流程演示，并非你的图片识别结果。</p><p v-else>{{ isExample ? '这是示例空间。上传自己的户型图，开始探索你的家。' : '预览来自 AI 识别，请对照原图检查。房间面积由识别轮廓估算，仅供参考。' }}</p><button class="button dark full" :disabled="store.viewMode === 'transition'" @click="download">导出当前视角 <span>↓</span></button><button class="text-button full" @click="navigate('upload')">{{ isExample ? '上传我的户型 →' : '重新上传户型 →' }}</button></div>
      </aside>
    </main>
  </div>
</template>
