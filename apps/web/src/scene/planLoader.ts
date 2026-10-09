/** 方案加载：JSON Schema（ajv，draft 2020-12）+ 语义校验双道门。 */

import Ajv2020 from 'ajv/dist/2020'
import { schema, type FloorPlan } from '@roomcraft/shared-schema'
import demoPlanJson from '@roomcraft/shared-schema/fixtures/valid/demo-2br.json'

import { checkSemantics, isUsable } from './semanticChecks'

export class PlanValidationError extends Error {
  constructor(
    message: string,
    public readonly issues: string[],
  ) {
    super(message)
    this.name = 'PlanValidationError'
  }
}

export function validatePlan(plan: unknown): FloorPlan {
  const ajv = new Ajv2020({ allErrors: true })
  const validate = ajv.compile<unknown>(schema)
  if (!validate(plan)) {
    const detail = (validate.errors ?? [])
      .map((e) => `${e.instancePath || '/'} ${e.message ?? ''}`)
      .slice(0, 8)
      .join('; ')
    throw new PlanValidationError('JSON Schema 校验未通过', [detail])
  }
  const issues = checkSemantics(plan as FloorPlan)
  if (!isUsable(issues)) {
    throw new PlanValidationError('语义校验未通过', issues.map((i) => `${i.code}: ${i.message}`))
  }
  return plan as FloorPlan
}

/** M0 原型入口：加载仓库内的示例户型（与 Spike/CI 共用同一份 fixture）。 */
export function loadDemoPlan(): FloorPlan {
  return validatePlan(demoPlanJson)
}
