/** 从户型 JSON 确定性构建场景：地面、房间地板、墙体、房间标签、灯光。 */

import * as THREE from 'three'
import type { FloorPlan } from '@roomcraft/shared-schema'

import { COLORS, ROOM_FLOOR_PALETTE, SCENE_DEFAULTS } from './config'
import { buildWall, planToWorld } from './wallBuilder'

export interface BuiltScene {
  group: THREE.Group
  bbox: THREE.Box3
  walkEntry: { pos: THREE.Vector3; yaw: number }
}

function computeBBox(plan: FloorPlan, floorHeight: number): THREE.Box3 {
  const pts: THREE.Vector3[] = []
  for (const w of plan.walls) {
    pts.push(planToWorld(w.p1), planToWorld(w.p2))
  }
  for (const r of plan.rooms) {
    for (const p of r.polygon ?? []) pts.push(planToWorld(p))
  }
  const bbox = new THREE.Box3().setFromPoints(pts)
  // 计入墙体高度：倾斜视角的视锥适配需要真实三维包围盒
  bbox.max.y = floorHeight
  return bbox
}

function makeLabelSprite(text: string): THREE.Sprite {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 96
  const ctx = canvas.getContext('2d')!
  ctx.font = '500 40px "PingFang SC", "Microsoft YaHei", sans-serif'
  const metrics = ctx.measureText(text)
  const pillW = Math.min(240, metrics.width + 36)
  ctx.fillStyle = 'rgba(255,255,255,0.86)'
  ctx.beginPath()
  ctx.roundRect((256 - pillW) / 2, 16, pillW, 64, 16)
  ctx.fill()
  ctx.fillStyle = `#${COLORS.label.toString(16).padStart(6, '0')}`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, 128, 50)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true })
  const sprite = new THREE.Sprite(material)
  const worldH = 0.55
  sprite.scale.set((worldH * 256) / 96, worldH, 1)
  return sprite
}

export function buildPlanScene(plan: FloorPlan): BuiltScene {
  const floorHeight = plan.meta.floorHeight ?? SCENE_DEFAULTS.floorHeight
  const group = new THREE.Group()
  const bbox = computeBBox(plan, floorHeight)

  // 地面基板（略大于户型）
  const size = bbox.getSize(new THREE.Vector3())
  const center = bbox.getCenter(new THREE.Vector3())
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(size.x + 8, size.z + 8),
    new THREE.MeshStandardMaterial({ color: COLORS.ground, roughness: 1 }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.set(center.x, -0.02, center.z)
  group.add(ground)

  // 房间地板分色
  plan.rooms.forEach((room, idx) => {
    if (!room.polygon || room.polygon.length < 3) return
    const shape = new THREE.Shape(room.polygon.map((p) => new THREE.Vector2(p.x, -p.y)))
    const mesh = new THREE.Mesh(
      new THREE.ShapeGeometry(shape),
      new THREE.MeshStandardMaterial({
        color: ROOM_FLOOR_PALETTE[idx % ROOM_FLOOR_PALETTE.length],
        roughness: 0.9,
      }),
    )
    mesh.rotation.x = -Math.PI / 2
    mesh.position.y = 0.01
    group.add(mesh)
  })

  // 墙体
  for (const wall of plan.walls) {
    group.add(buildWall(wall, floorHeight))
  }

  // 房间名标签
  for (const room of plan.rooms) {
    if (!room.labelPosition) continue
    const sprite = makeLabelSprite(room.name)
    sprite.position.set(room.labelPosition.x, 1.9, room.labelPosition.y)
    group.add(sprite)
  }

  // 灯光
  group.add(new THREE.AmbientLight(0xffffff, 0.55))
  group.add(new THREE.HemisphereLight(0xffffff, 0x8d8d8d, 0.9))
  const dir = new THREE.DirectionalLight(0xffffff, 1.6)
  dir.position.set(center.x + 8, 16, center.z + 6)
  dir.target.position.copy(center)
  group.add(dir, dir.target)

  // 行走入口：第一个带标签的房间；视线沿房间长轴、朝入口一侧空间更足的方向，
  // 避免开局怼墙角。无多边形时退化为朝户型中心。
  const labeled = plan.rooms.find((r) => r.labelPosition) ?? plan.rooms[0]
  const entryPt = labeled?.labelPosition ?? { x: center.x, y: center.z }
  let dx = center.x - entryPt.x
  let dz = center.z - entryPt.y
  if (labeled?.polygon?.length) {
    let minX = Infinity
    let maxX = -Infinity
    let minZ = Infinity
    let maxZ = -Infinity
    for (const p of labeled.polygon) {
      minX = Math.min(minX, p.x)
      maxX = Math.max(maxX, p.x)
      minZ = Math.min(minZ, p.y)
      maxZ = Math.max(maxZ, p.y)
    }
    if (maxX - minX >= maxZ - minZ) {
      dx = (entryPt.x >= (minX + maxX) / 2 ? minX : maxX) - entryPt.x
      dz = 0
    } else {
      dx = 0
      dz = (entryPt.y >= (minZ + maxZ) / 2 ? minZ : maxZ) - entryPt.y
    }
  }
  const yaw = Math.abs(dx) + Math.abs(dz) < 1e-6 ? 0 : Math.atan2(-dx, -dz)
  const walkEntry = {
    pos: new THREE.Vector3(entryPt.x, SCENE_DEFAULTS.walkEyeHeight, entryPt.y),
    yaw,
  }

  return { group, bbox, walkEntry }
}
