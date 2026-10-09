/** 双视角控制：俯视（正交相机，可绕竖轴旋转）⇄ 行走（透视相机，拖动视角 + WASD），带平滑过渡。

手势约定（触摸板友好，同地图类产品）：
- 俯视：左键拖动 = 旋转（绕竖轴）；双指滚动 = 平移；捏合 / Ctrl+滚轮 = 朝光标缩放
- 行走：拖动 = 转视角；W/S/A/D 或方向键 = 移动
*/

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { SCENE_DEFAULTS } from './config'

export type RigMode = 'top' | 'walk' | 'transition'

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function lookQuat(from: THREE.Vector3, to: THREE.Vector3): THREE.Quaternion {
  const m = new THREE.Matrix4().lookAt(from, to, new THREE.Vector3(0, 1, 0))
  return new THREE.Quaternion().setFromRotationMatrix(m)
}

export class ViewRig {
  mode: RigMode = 'top'
  /** 行走与过渡动画用透视相机 */
  readonly perspCamera: THREE.PerspectiveCamera
  /** 俯视用正交相机（平面图标准投影，无透视歪斜） */
  readonly orthoCamera: THREE.OrthographicCamera

  private active: 'ortho' | 'persp' = 'ortho'
  private readonly orbit: OrbitControls
  private readonly bbox: THREE.Box3
  private readonly walkEntry: { pos: THREE.Vector3; yaw: number }
  private readonly onModeChange?: (m: RigMode) => void
  private readonly disposers: Array<() => void> = []
  private readonly size = { w: 1, h: 1 }

  private walkYaw = 0
  private walkPitch = 0
  private readonly keys = new Set<string>()
  private drag: { x: number; y: number } | null = null
  private tween: {
    fromPos: THREE.Vector3
    toPos: THREE.Vector3
    fromQ: THREE.Quaternion
    toQ: THREE.Quaternion
    start: number
    dur: number
    onDone: () => void
  } | null = null

  constructor(
    dom: HTMLElement,
    bbox: THREE.Box3,
    walkEntry: { pos: THREE.Vector3; yaw: number },
    onModeChange?: (m: RigMode) => void,
  ) {
    this.bbox = bbox
    this.walkEntry = walkEntry
    this.onModeChange = onModeChange

    this.perspCamera = new THREE.PerspectiveCamera(SCENE_DEFAULTS.walkFov, 1, 0.1, 300)
    this.orthoCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 120)

    this.orbit = new OrbitControls(this.orthoCamera, dom)
    this.orbit.enableDamping = true
    this.orbit.dampingFactor = 0.08
    // 极角放开：默认 45° 俯角，可从近俯视扫到近水平；方位角 360° 无限制
    this.orbit.minPolarAngle = SCENE_DEFAULTS.topMinPolarAngle
    this.orbit.maxPolarAngle = SCENE_DEFAULTS.topMaxPolarAngle
    this.orbit.minDistance = SCENE_DEFAULTS.topMinDistance
    this.orbit.maxDistance = SCENE_DEFAULTS.topMaxDistance
    this.orbit.rotateSpeed = 0.9
    this.orbit.panSpeed = 1.0
    this.orbit.zoomSpeed = 0.7
    // 注意：不启用 zoomToCursor——它会把轨道中心挪到光标处，
    // 导致后续旋转不再绕建筑中心（用户可感知的「转轴不对」）
    this.orbit.zoomToCursor = false

    const onKeyDown = (e: KeyboardEvent): void => {
      if (this.mode !== 'walk') return
      this.keys.add(e.code)
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault()
    }
    const onKeyUp = (e: KeyboardEvent): void => {
      this.keys.delete(e.code)
    }
    const onPointerDown = (e: PointerEvent): void => {
      if (this.mode !== 'walk') return
      this.drag = { x: e.clientX, y: e.clientY }
    }
    const onPointerMove = (e: PointerEvent): void => {
      if (!this.drag || this.mode !== 'walk') return
      const dx = e.clientX - this.drag.x
      const dy = e.clientY - this.drag.y
      this.drag = { x: e.clientX, y: e.clientY }
      this.walkYaw -= dx * 0.005
      this.walkPitch = THREE.MathUtils.clamp(this.walkPitch - dy * 0.005, -1.2, 1.2)
      this.perspCamera.quaternion.setFromEuler(new THREE.Euler(this.walkPitch, this.walkYaw, 0, 'YXZ'))
    }
    const onPointerUp = (): void => {
      this.drag = null
    }
    // 触摸板手势重映射：双指滚动（无 Ctrl）→ 平移；捏合（Ctrl+滚轮）→ 交给 OrbitControls 缩放
    const onWheel = (e: WheelEvent): void => {
      if (this.mode !== 'top') {
        e.preventDefault()
        return
      }
      if (e.ctrlKey) return
      e.preventDefault()
      e.stopImmediatePropagation()
      this.panBy(e.deltaX, e.deltaY)
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    dom.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    dom.addEventListener('wheel', onWheel, { passive: false, capture: true })
    this.disposers.push(() => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      dom.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      dom.removeEventListener('wheel', onWheel, { capture: true })
    })

    this.setTopView()
    this.setMode('top')
  }

  get activeCamera(): THREE.Camera {
    return this.active === 'ortho' ? this.orthoCamera : this.perspCamera
  }

  resize(w: number, h: number): void {
    this.size.w = w
    this.size.h = h
    this.perspCamera.aspect = w / h
    this.perspCamera.updateProjectionMatrix()
    this.fitOrtho()
  }

  /** 回到默认俯视：45° 俯角、以建筑中心为轴、重新适配视锥。 */
  resetTopView(): void {
    if (this.mode !== 'top') return
    this.setTopView()
  }

  /**
   * 俯视视锥适配：把含墙高的包围盒 8 个角投影到相机平面（右/上轴）取最大范围，
   * 按视口宽高比铺满。倾斜视角下墙体高度会占据投影，必须用三维投影而非平面尺寸估算。
   */
  private fitOrtho(): void {
    const cam = this.orthoCamera
    const dir = cam.position.clone().sub(this.orbit.target)
    if (dir.lengthSq() < 1e-9) dir.set(0, 1, 0.001)
    dir.normalize()
    let right: THREE.Vector3
    let up: THREE.Vector3
    if (Math.abs(dir.y) > 0.999) {
      // 近垂直俯视：避免叉积退化；平面「北」（-z）朝屏幕上方
      right = new THREE.Vector3(1, 0, 0)
      up = new THREE.Vector3(0, 0, -1)
    } else {
      right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize()
      up = new THREE.Vector3().crossVectors(right, dir).normalize()
    }
    const size = this.bbox.getSize(new THREE.Vector3())
    // 注意用半尺寸角点（±half）：fit 求的是「中心到最远角」的投影半径，
    // 误用全尺寸会让视锥放大约一倍（表现为户型偏小、四周大量留白）
    const half = size.clone().multiplyScalar(0.5)
    let maxR = 0
    let maxU = 0
    for (const sx of [-1, 1]) {
      for (const sy of [-1, 1]) {
        for (const sz of [-1, 1]) {
          const v = new THREE.Vector3(sx * half.x, sy * half.y, sz * half.z)
          maxR = Math.max(maxR, Math.abs(v.dot(right)))
          maxU = Math.max(maxU, Math.abs(v.dot(up)))
        }
      }
    }
    const aspect = this.size.w / this.size.h
    if (!Number.isFinite(aspect) || aspect <= 0) return
    const halfH = Math.max(maxU, maxR / aspect) * SCENE_DEFAULTS.topFitMargin
    cam.left = -halfH * aspect
    cam.right = halfH * aspect
    cam.top = halfH
    cam.bottom = -halfH
    cam.updateProjectionMatrix()
  }

  /** 默认俯视：45° 俯角、绕建筑中心，方位角 0（从南侧上空看向北）。 */
  private setTopView(): void {
    const center = this.bbox.getCenter(new THREE.Vector3())
    this.orbit.target.copy(center)
    const polar = THREE.MathUtils.degToRad(SCENE_DEFAULTS.topDefaultPolarDeg)
    const r = SCENE_DEFAULTS.topRadius
    this.orthoCamera.up.set(0, 1, 0)
    this.orthoCamera.position.set(
      center.x,
      center.y + r * Math.cos(polar),
      center.z + r * Math.sin(polar),
    )
    this.orbit.update()
    this.fitOrtho()
  }

  /** 与当前正交视野等效的透视机位（过渡起点，保证画面连续）。 */
  private mimicTopPose(): { pos: THREE.Vector3; target: THREE.Vector3 } {
    const cam = this.orthoCamera
    const target = this.orbit.target.clone()
    const dir = cam.position.clone().sub(target).normalize()
    const visibleH = (cam.top - cam.bottom) / cam.zoom
    const d = visibleH / (2 * Math.tan(THREE.MathUtils.degToRad(this.perspCamera.fov / 2)))
    return { pos: target.clone().add(dir.multiplyScalar(d)), target }
  }

  enterWalk(): Promise<void> {
    if (this.mode !== 'top') return Promise.resolve()
    this.orbit.enabled = false
    const mimic = this.mimicTopPose()
    this.perspCamera.up.set(0, 1, 0)
    this.perspCamera.position.copy(mimic.pos)
    this.perspCamera.quaternion.copy(lookQuat(mimic.pos, mimic.target))

    this.walkYaw = this.walkEntry.yaw
    this.walkPitch = THREE.MathUtils.degToRad(SCENE_DEFAULTS.walkInitialPitchDeg)
    const toQ = new THREE.Quaternion().setFromEuler(new THREE.Euler(this.walkPitch, this.walkYaw, 0, 'YXZ'))
    return this.animateTo(
      this.perspCamera.position.clone(),
      this.perspCamera.quaternion.clone(),
      this.walkEntry.pos.clone(),
      toQ,
      () => {
        this.active = 'persp'
        this.setMode('walk')
      },
    )
  }

  exitWalk(): Promise<void> {
    if (this.mode !== 'walk') return Promise.resolve()
    this.keys.clear()
    const mimic = this.mimicTopPose()
    const toQ = lookQuat(mimic.pos, mimic.target)
    return this.animateTo(
      this.perspCamera.position.clone(),
      this.perspCamera.quaternion.clone(),
      mimic.pos.clone(),
      toQ,
      () => {
        this.active = 'ortho'
        this.setMode('top')
        this.orbit.enabled = true
        this.orbit.update()
      },
    )
  }

  private animateTo(
    fromPos: THREE.Vector3,
    fromQ: THREE.Quaternion,
    toPos: THREE.Vector3,
    toQ: THREE.Quaternion,
    onDone: () => void,
  ): Promise<void> {
    this.setMode('transition')
    this.tween = {
      fromPos,
      toPos,
      fromQ,
      toQ,
      start: performance.now(),
      dur: SCENE_DEFAULTS.transitionMs,
      onDone,
    }
    return new Promise((resolve) => {
      const prev = this.tween!.onDone
      this.tween!.onDone = () => {
        prev()
        resolve()
      }
    })
  }

  /** 双指滚动平移：世界坐标随手指移动（保持在地平面内）。 */
  private panBy(dx: number, dy: number): void {
    const cam = this.orthoCamera
    const worldPerPx = (cam.top - cam.bottom) / (cam.zoom * this.size.h)
    if (!Number.isFinite(worldPerPx) || worldPerPx <= 0) return
    const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0)
    const up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1)
    right.y = 0
    up.y = 0
    if (right.lengthSq() < 1e-8 || up.lengthSq() < 1e-8) return
    right.normalize()
    up.normalize()
    const delta = right.multiplyScalar(-dx * worldPerPx).add(up.multiplyScalar(dy * worldPerPx))
    cam.position.add(delta)
    this.orbit.target.add(delta)
  }

  private setMode(m: RigMode): void {
    this.mode = m
    this.onModeChange?.(m)
  }

  update(dt: number): void {
    if (this.tween) {
      const t = Math.min((performance.now() - this.tween.start) / this.tween.dur, 1)
      const k = easeInOutCubic(t)
      this.perspCamera.position.lerpVectors(this.tween.fromPos, this.tween.toPos, k)
      this.perspCamera.quaternion.slerpQuaternions(this.tween.fromQ, this.tween.toQ, k)
      if (t >= 1) {
        const done = this.tween.onDone
        this.tween = null
        done()
      }
      return
    }
    if (this.mode === 'top') {
      this.orbit.update()
    } else if (this.mode === 'walk') {
      const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.perspCamera.quaternion)
      forward.y = 0
      forward.normalize()
      const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0))
      const move = new THREE.Vector3()
      if (this.keys.has('KeyW') || this.keys.has('ArrowUp')) move.add(forward)
      if (this.keys.has('KeyS') || this.keys.has('ArrowDown')) move.sub(forward)
      if (this.keys.has('KeyA') || this.keys.has('ArrowLeft')) move.sub(right)
      if (this.keys.has('KeyD') || this.keys.has('ArrowRight')) move.add(right)
      if (move.lengthSq() > 0) {
        move.normalize().multiplyScalar(SCENE_DEFAULTS.walkSpeed * dt)
        this.perspCamera.position.add(move)
        // M0 无碰撞检测：钳制在户型包围盒内
        const m = SCENE_DEFAULTS.walkMargin
        this.perspCamera.position.x = THREE.MathUtils.clamp(
          this.perspCamera.position.x,
          this.bbox.min.x + m,
          this.bbox.max.x - m,
        )
        this.perspCamera.position.z = THREE.MathUtils.clamp(
          this.perspCamera.position.z,
          this.bbox.min.z + m,
          this.bbox.max.z - m,
        )
        this.perspCamera.position.y = SCENE_DEFAULTS.walkEyeHeight
      }
    }
  }

  dispose(): void {
    for (const d of this.disposers) d()
    this.orbit.dispose()
  }
}
