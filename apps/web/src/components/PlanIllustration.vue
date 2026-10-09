<script setup lang="ts">
import plan from '@roomcraft/shared-schema/fixtures/valid/demo-2br.json'
</script>

<template>
  <svg class="plan-illustration" viewBox="-0.8 -0.8 11.8 10" fill="none" role="img" aria-label="两室两厅示例户型示意图">
    <defs>
      <pattern id="plan-grid" width="0.5" height="0.5" patternUnits="userSpaceOnUse">
        <path d="M .5 0 H 0 V .5" stroke="currentColor" stroke-opacity=".06" stroke-width=".012" />
      </pattern>
    </defs>
    <rect x="-.8" y="-.8" width="11.8" height="10" fill="url(#plan-grid)" />
    <polygon v-for="(room, i) in plan.rooms" :key="room.id" :points="room.polygon.map(p => `${p.x},${p.y}`).join(' ')" fill="currentColor" :fill-opacity="0.04 + i * .013" />
    <g v-for="wall in plan.walls" :key="wall.id">
      <line :x1="wall.p1.x" :y1="wall.p1.y" :x2="wall.p2.x" :y2="wall.p2.y" stroke="currentColor" :stroke-width="wall.thickness * .8" />
    </g>
    <g v-for="room in plan.rooms" :key="room.id + '-label'" fill="currentColor">
      <text :x="room.labelPosition.x" :y="room.labelPosition.y" text-anchor="middle" font-size=".27" font-family="sans-serif" opacity=".65">{{ room.name }}</text>
    </g>
    <g stroke="currentColor" stroke-width=".025" opacity=".35">
      <path d="M 0 -.4 H 10.2 M 0 -.55 V -.25 M 10.2 -.55 V -.25" />
    </g>
    <text x="5.1" y="-.52" text-anchor="middle" fill="currentColor" opacity=".5" font-size=".19">10.20 m</text>
  </svg>
</template>
