<script setup lang="ts">
import { ref } from 'vue'

import PrototypeCanvas from '@/components/PrototypeCanvas.vue'
import { useAppStore } from '@/store/app'

const canvasRef = ref<InstanceType<typeof PrototypeCanvas>>()
const store = useAppStore()

async function toggleWalk(): Promise<void> {
  await canvasRef.value?.toggleWalk()
}

function backToTop(): void {
  if (store.viewMode === 'walk') void toggleWalk()
}

function enterWalk(): void {
  if (store.viewMode === 'top') void toggleWalk()
}

function downloadSnapshot(): void {
  const url = canvasRef.value?.snapshot()
  if (!url) return
  const a = document.createElement('a')
  a.href = url
  a.download = 'roomcraft-scene.png'
  a.click()
}
</script>

<template>
  <el-container class="app">
    <el-header class="header" height="56px">
      <div class="brand">
        RoomCraft
        <span class="tag">M0 技术原型 · 假户型双视角</span>
      </div>
      <div class="actions">
        <el-button-group>
          <el-button :type="store.viewMode === 'top' ? 'primary' : 'default'" @click="backToTop">
            俯视
          </el-button>
          <el-button
            :type="store.viewMode === 'walk' ? 'primary' : 'default'"
            :disabled="store.viewMode === 'transition'"
            @click="enterWalk"
          >
            行走
          </el-button>
        </el-button-group>
        <el-button :disabled="store.viewMode === 'transition'" @click="downloadSnapshot">
          导出截图
        </el-button>
      </div>
    </el-header>
    <el-main class="main">
      <el-alert
        v-if="store.planError"
        type="error"
        :title="store.planError"
        :closable="false"
        class="error"
      />
      <PrototypeCanvas v-else ref="canvasRef" />
    </el-main>
  </el-container>
</template>

<style scoped>
.app {
  height: 100%;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  background: #fff;
}

.brand {
  font-size: 17px;
  font-weight: 600;
  color: #1f2d3d;
}

.tag {
  margin-left: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  font-weight: 400;
}

.actions {
  display: flex;
  gap: 12px;
}

.main {
  padding: 0;
  position: relative;
}

.error {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  z-index: 10;
}
</style>
