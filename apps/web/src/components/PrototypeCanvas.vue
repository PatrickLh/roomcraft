<script setup lang="ts">
import * as THREE from 'three'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import { buildPlanScene } from '@/scene/buildPlanScene'
import { loadDemoPlan } from '@/scene/planLoader'
import { ViewRig } from '@/scene/viewRig'
import { useAppStore } from '@/store/app'

const host = ref<HTMLDivElement>()
const store = useAppStore()

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let rig: ViewRig | null = null
let raf = 0
let resizeObserver: ResizeObserver | null = null

function onResize(): void {
  if (!host.value || !renderer) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight
  renderer.setSize(w, h, false)
  rig?.resize(w, h)
}

onMounted(() => {
  if (!host.value) return
  const plan = loadDemoPlan()
  store.planName = plan.meta.name ?? '示例户型'
  store.planError = null

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xeef1f4)
  const built = buildPlanScene(plan)
  scene.add(built.group)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  host.value.appendChild(renderer.domElement)

  rig = new ViewRig(renderer.domElement, built.bbox, built.walkEntry, (m) => {
    store.viewMode = m
  })

  resizeObserver = new ResizeObserver(onResize)
  resizeObserver.observe(host.value)
  onResize()

  const clock = new THREE.Clock()
  const loop = (): void => {
    raf = requestAnimationFrame(loop)
    rig?.update(clock.getDelta())
    if (renderer && scene && rig) renderer.render(scene, rig.activeCamera)
  }
  loop()

  // 测试/演示钩子：?view=walk 直接进入行走视角
  if (new URLSearchParams(window.location.search).get('view') === 'walk') {
    void rig.enterWalk()
  }
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  resizeObserver?.disconnect()
  rig?.dispose()
  renderer?.dispose()
})

async function toggleWalk(): Promise<void> {
  if (!rig) return
  if (store.viewMode === 'top') await rig.enterWalk()
  else if (store.viewMode === 'walk') await rig.exitWalk()
}

/** 场景截图（Spike B 的场景输入也来自这里）。 */
function snapshot(): string | null {
  if (!renderer || !scene || !rig) return null
  renderer.render(scene, rig.activeCamera)
  return renderer.domElement.toDataURL('image/png')
}

defineExpose({ toggleWalk, snapshot })
</script>

<template>
  <div ref="host" class="canvas-host">
    <div v-if="store.viewMode === 'top'" class="hint">
      左键拖动旋转 · 双指滚动平移 · 捏合 / Ctrl+滚轮缩放
    </div>
    <div v-else-if="store.viewMode === 'walk'" class="hint">拖动转视角 · W/S/A/D 或方向键移动</div>
  </div>
</template>

<style scoped>
.canvas-host {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.canvas-host :deep(canvas) {
  display: block;
  touch-action: none;
}

.hint {
  position: absolute;
  left: 12px;
  bottom: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.82);
  color: #4a5560;
  font-size: 13px;
  pointer-events: none;
  user-select: none;
}
</style>
