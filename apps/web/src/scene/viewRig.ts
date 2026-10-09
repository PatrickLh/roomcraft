/** 双视角控制：俯视（OrbitControls，可绕竖轴旋转）⇄ 行走（拖动视角 + WASD），带平滑过渡。 */

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

import { SCENE_DEFAULTS } from './config'

export type RigMode = 'top' | 'walk' | 'transition'

interface Pose {
  pos: THREE.Vector3
  target: THREE.Vector3
}

function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

function lookQuat(from: THREE.Vector3, to: THREE.Vector3): THREE.Quaternion {
  const m = new THREE.Matrix4().lookAt(from, to, new THREE.Vector3(0, 1, 0))
  return new THREE.Quaternion().setFromRotationMatrix(m)
}

export class ViewRig {
  mode: RigMode = 'top'
  private readonly orbit: OrbitControls
  private readonly bbox: THREE.Box3
  private readonly walkEntry: { pos: THREE.Vector3; yaw: number }
  private readonly onModeChange?: (m: RigMode) => void
  private readonly disposers: Array<() => void> = []

  private topPose: Pose | null = null
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
    private camera: THREE.PerspectiveCamera,
    dom: HTMLElement,
    bbox: THREE.Box3,
    walkEntry: { pos: THREE.Vector3; yaw: number },
    onModeChange?: (m: RigMode) => void,
  ) {
    this.bbox = bbox
    this.walkEntry = walkEntry
    this.onModeChange = onModeChange

    this.orbit = new OrbitControls(camera, dom)
    this.orbit.enableDamping = true
    this.orbit.dampingFactor = 0.08
    this.orbit.maxPolarAngle = SCENE_DEFAULTS.topMaxPolarAngle
    this.orbit.minPolarAngle = 0
    this.orbit.minDistance = SCENE_DEFAULTS.topMinDistance
    this.orbit.maxDistance = SCENE_DEFAULTS.topMaxDistance

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
      this.camera.quaternion.setFromEuler(new THREE.Euler(this.walkPitch, this.walkYaw, 0, 'YXZ'))
    }
    const onPointerUp = (): void => {
      this.drag = null
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    dom.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    this.disposers.push(() => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      dom.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
    })

    this.setTopView()
    this.setMode('top')
  }

  private setMode(m: RigMode): void {
    this.mode = m
    this.onModeChange?.(m)
  }

  /** 俯视：相机位于户型上方，OrbitControls 负责旋转/缩放/平移。 */
  private setTopView(): void {
    const center = this.bbox.getCenter(new THREE.Vector3())
    const size = this.bbox.getSize(new THREE.Vector3())
    const dist = Math.max(size.x, size.z) * 1.05 + SCENE_DEFAULTS.topMinDistance
    this.camera.up.set(0, 1, 0)
    this.orbit.target.copy(center)
    // +0.001 避免 up 与视线方向平行时的万向锁
    this.camera.position.set(center.x, dist, center.z + 0.001)
    this.orbit.update()
    this.topPose = { pos: this.camera.position.clone(), target: center.clone() }
  }

  enterWalk(): Promise<void> {
    if (this.mode !== 'top') return Promise.resolve()
    this.topPose = { pos: this.camera.position.clone(), target: this.orbit.target.clone() }
    this.orbit.enabled = false
    this.walkYaw = this.walkEntry.yaw
    this.walkPitch = 0
    const forward = new THREE.Vector3(-Math.sin(this.walkYaw), 0, -Math.cos(this.walkYaw))
    const toQ = lookQuat(this.walkEntry.pos, this.walkEntry.pos.clone().add(forward))
    return this.animateTo(
      this.camera.position.clone(),
      this.camera.quaternion.clone(),
      this.walkEntry.pos.clone(),
      toQ,
      () => this.setMode('walk'),
    )
  }

  exitWalk(): Promise<void> {
    if (this.mode !== 'walk' || !this.topPose) return Promise.resolve()
    this.orbit.enabled = false
    this.keys.clear()
    const toQ = lookQuat(this.topPose.pos, this.topPose.target)
    return this.animateTo(
      this.camera.position.clone(),
      this.camera.quaternion.clone(),
      this.topPose.pos.clone(),
      toQ,
      () => {
        this.orbit.target.copy(this.topPose!.target)
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
    this.tween = { fromPos, toPos, fromQ, toQ, start: performance.now(), dur: SCENE_DEFAULTS.transitionMs, onDone }
    return new Promise((resolve) => {
      const prev = this.tween!.onDone
      this.tween!.onDone = () => {
        prev()
        resolve()
      }
    })
  }

  update(dt: number): void {
    if (this.tween) {
      const t = Math.min((performance.now() - this.tween.start) / this.tween.dur, 1)
      const k = easeInOutCubic(t)
      this.camera.position.lerpVectors(this.tween.fromPos, this.tween.toPos, k)
      this.camera.quaternion.slerpQuaternions(this.tween.fromQ, this.tween.toQ, k)
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
      const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion)
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
        this.camera.position.add(move)
        // M0 无碰撞检测：钳制在户型包围盒内
        const m = SCENE_DEFAULTS.walkMargin
        this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, this.bbox.min.x + m, this.bbox.max.x - m)
        this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, this.bbox.min.z + m, this.bbox.max.z - m)
        this.camera.position.y = SCENE_DEFAULTS.walkEyeHeight
      }
    }
  }

  dispose(): void {
    for (const d of this.disposers) d()
    this.orbit.dispose()
  }
}
