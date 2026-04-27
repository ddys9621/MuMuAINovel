export interface NormalizedAnalysisData {
  plot_analysis?: string
  summary?: string
  character_status?: Array<{ name: string; status: string }>
  emotion_curve?: Array<{ label: string; value: number }>
  score?: number
  suggestions?: string[]
  hooks?: Array<Record<string, unknown>>
  foreshadows?: Array<Record<string, unknown>>
  narrative_state: {
    causal_links: Array<Record<string, unknown>>
    promises: Array<Record<string, unknown>>
    timeline_events: Array<Record<string, unknown>>
    relationship_graph: {
      nodes: Array<Record<string, unknown>>
      edges: Array<Record<string, unknown>>
    }
  }
  consistency_audit: {
    summary: {
      total: number
      critical: number
      high: number
      medium: number
      low: number
    }
    issues: Array<Record<string, unknown>>
  }
  [key: string]: unknown
}

function normalizeCurveValue(value: unknown) {
  const numeric = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numeric)) return 0
  if (numeric <= 1) return Math.round(numeric * 100)
  if (numeric <= 10) return Math.round(numeric * 10)
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
}

function toRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter(Boolean).map(item => toRecord(item))
    : []
}

export function normalizeAnalysisData(payload: Record<string, unknown>): NormalizedAnalysisData {
  const payloadSource = toRecord(payload)
  const analysisSource = toRecord(payloadSource.analysis ?? payloadSource)

  const characterStates = Array.isArray(analysisSource.character_states)
    ? analysisSource.character_states
    : Array.isArray(analysisSource.character_status)
      ? analysisSource.character_status
      : []

  const emotionCurveSource = analysisSource.emotion_curve
  const emotionCurve = Array.isArray(emotionCurveSource)
    ? emotionCurveSource.map((item, index) => ({
        label: String((item as Record<string, unknown>).label || `节点${index + 1}`),
        value: normalizeCurveValue((item as Record<string, unknown>).value),
      }))
    : emotionCurveSource && typeof emotionCurveSource === 'object'
      ? Object.entries(emotionCurveSource as Record<string, unknown>).map(([label, value]) => ({
          label,
          value: normalizeCurveValue(value),
        }))
      : []

  const emotionalArc = toRecord(analysisSource.emotional_arc)
  const normalizedEmotionCurve = emotionCurve.length > 0
    ? emotionCurve
    : emotionalArc.primary_emotion
      ? [{
          label: String(emotionalArc.primary_emotion),
          value: normalizeCurveValue(emotionalArc.intensity),
        }]
      : []

  const narrativeStateSource = toRecord(payloadSource.narrative_state ?? analysisSource.narrative_state)
  const relationshipGraphSource = toRecord(narrativeStateSource.relationship_graph)
  const consistencyAuditSource = toRecord(payloadSource.consistency_audit ?? analysisSource.consistency_audit)
  const consistencySummary = toRecord(consistencyAuditSource.summary)

  return {
    ...analysisSource,
    plot_analysis:
      typeof analysisSource.plot_analysis === 'string' && analysisSource.plot_analysis.trim()
        ? analysisSource.plot_analysis
        : typeof analysisSource.analysis_report === 'string'
          ? analysisSource.analysis_report
          : '',
    summary: typeof analysisSource.summary === 'string' ? analysisSource.summary : '',
    character_status: characterStates.map((item, index) => {
      const entry = item as Record<string, unknown>
      const name = String(entry.character_name || entry.name || `角色 ${index + 1}`)
      const status = String(
        entry.state_after ||
        entry.status ||
        entry.psychological_change ||
        entry.state_before ||
        ''
      )
      return { name, status }
    }),
    emotion_curve: normalizedEmotionCurve,
    score:
      typeof analysisSource.score === 'number'
        ? analysisSource.score
        : typeof analysisSource.overall_quality_score === 'number'
          ? analysisSource.overall_quality_score
          : typeof toRecord(analysisSource.scores).overall === 'number'
            ? Number(toRecord(analysisSource.scores).overall)
            : undefined,
    suggestions: Array.isArray(analysisSource.suggestions)
      ? analysisSource.suggestions.filter(Boolean).map(String)
      : [],
    hooks: toRecordArray(analysisSource.hooks),
    foreshadows: toRecordArray(analysisSource.foreshadows),
    narrative_state: {
      causal_links: toRecordArray(narrativeStateSource.causal_links),
      promises: toRecordArray(narrativeStateSource.promises),
      timeline_events: toRecordArray(narrativeStateSource.timeline_events),
      relationship_graph: {
        nodes: toRecordArray(relationshipGraphSource.nodes),
        edges: toRecordArray(relationshipGraphSource.edges),
      },
    },
    consistency_audit: {
      summary: {
        total: Number(consistencySummary.total || 0),
        critical: Number(consistencySummary.critical || 0),
        high: Number(consistencySummary.high || 0),
        medium: Number(consistencySummary.medium || 0),
        low: Number(consistencySummary.low || 0),
      },
      issues: toRecordArray(consistencyAuditSource.issues),
    },
  }
}
