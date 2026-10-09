import Ajv2020 from 'ajv/dist/2020'
import { describe, expect, it } from 'vitest'

import { schema, type FloorPlan } from '@roomcraft/shared-schema'
import demo from '@roomcraft/shared-schema/fixtures/valid/demo-2br.json'
import duplicateIds from '@roomcraft/shared-schema/fixtures/invalid/duplicate-wall-id.json'
import missingScale from '@roomcraft/shared-schema/fixtures/invalid/missing-scale.json'
import openingOutOfRange from '@roomcraft/shared-schema/fixtures/invalid/opening-out-of-range.json'
import unsupportedVersion from '@roomcraft/shared-schema/fixtures/invalid/unsupported-version.json'

import { loadDemoPlan } from '../scene/planLoader'
import { checkSemantics, isUsable } from '../scene/semanticChecks'

const validate = new Ajv2020({ allErrors: true }).compile(schema)

const asPlan = (v: unknown): FloorPlan => v as FloorPlan

describe('户型 JSON Schema 契约（与 Python 侧共用同一组 fixtures）', () => {
  it('demo 两居室通过 Schema + 语义双道校验，loadDemoPlan 可用', () => {
    expect(validate(demo)).toBe(true)
    expect(isUsable(checkSemantics(asPlan(demo)))).toBe(true)
    expect(() => loadDemoPlan()).not.toThrow()
  })

  it('缺少 scale：JSON Schema 拒绝（无标定不允许出图）', () => {
    expect(validate(missingScale)).toBe(false)
  })

  it('未知 schemaVersion：JSON Schema 拒绝', () => {
    expect(validate(unsupportedVersion)).toBe(false)
  })

  it('门窗洞超出墙长：Schema 表达不了，语义校验必须拦截', () => {
    expect(validate(openingOutOfRange)).toBe(true)
    const issues = checkSemantics(asPlan(openingOutOfRange))
    expect(isUsable(issues)).toBe(false)
    expect(issues.some((i) => i.code === 'opening_out_of_range')).toBe(true)
  })

  it('墙体 ID 重复：Schema 表达不了，语义校验必须拦截', () => {
    expect(validate(duplicateIds)).toBe(true)
    const issues = checkSemantics(asPlan(duplicateIds))
    expect(isUsable(issues)).toBe(false)
    expect(issues.some((i) => i.code === 'duplicate_wall_id')).toBe(true)
  })
})
