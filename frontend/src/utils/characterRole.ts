export const ROLE_OPTIONS = [
  { value: 'protagonist', label: '主角' },
  { value: 'supporting', label: '配角' },
  { value: 'antagonist', label: '反派' },
  { value: 'mentor', label: '导师' },
  { value: 'ally', label: '盟友' },
  { value: 'extra', label: '路人' },
] as const

const ROLE_LABEL_MAP: Record<string, string> = {
  protagonist: '主角',
  supporting: '配角',
  antagonist: '反派',
  mentor: '导师',
  ally: '盟友',
  extra: '路人',
  organization: '组织',
  主角: '主角',
  配角: '配角',
  反派: '反派',
  导师: '导师',
  盟友: '盟友',
  路人: '路人',
  组织: '组织',
}

const ROLE_VALUE_MAP: Record<string, string> = {
  protagonist: 'protagonist',
  supporting: 'supporting',
  antagonist: 'antagonist',
  mentor: 'mentor',
  ally: 'ally',
  extra: 'extra',
  主角: 'protagonist',
  配角: 'supporting',
  反派: 'antagonist',
  导师: 'mentor',
  盟友: 'ally',
  路人: 'extra',
  组织: 'organization',
}

export function normalizeRoleType(roleType?: string, fallback = 'supporting') {
  if (!roleType?.trim()) return fallback
  const normalized = ROLE_VALUE_MAP[roleType.trim()]
  return normalized || roleType.trim()
}

export function getRoleDisplayName(roleType?: string, fallback = '路人') {
  if (!roleType?.trim()) return fallback
  return ROLE_LABEL_MAP[roleType.trim()] || roleType.trim()
}
