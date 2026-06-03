import type { DueDiligenceReport, ReportEvidenceItem, ReportRiskFactor, RiskLevel, WatchlistItem } from './types'

const WATCHLIST_KEY = 'financial-risk-workbench-watchlist'
const REPORTS_KEY = 'financial-risk-workbench-reports'
const RISK_LEVELS: RiskLevel[] = ['low', 'medium', 'high', 'unknown']

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isRiskLevel(value: unknown): value is RiskLevel {
  return typeof value === 'string' && RISK_LEVELS.includes(value as RiskLevel)
}

function isWatchlistItem(value: unknown): value is WatchlistItem {
  return isObject(value)
    && typeof value.companyName === 'string'
    && typeof value.industry === 'string'
    && isRiskLevel(value.riskLevel)
    && typeof value.summary === 'string'
    && typeof value.updatedAt === 'string'
}

function isReportRiskFactor(value: unknown): value is ReportRiskFactor {
  return isObject(value)
    && isRiskLevel(value.level)
    && typeof value.title === 'string'
    && typeof value.description === 'string'
    && !('id' in value)
    && !('relationIds' in value)
}

function isReportEvidenceItem(value: unknown): value is ReportEvidenceItem {
  return isObject(value)
    && typeof value.title === 'string'
    && typeof value.text === 'string'
    && typeof value.source === 'string'
    && typeof value.confidence === 'number'
    && Number.isFinite(value.confidence)
    && typeof value.date === 'string'
    && !('id' in value)
    && !('relationId' in value)
}

function isDueDiligenceReport(value: unknown): value is DueDiligenceReport {
  return isObject(value)
    && typeof value.id === 'string'
    && typeof value.companyName === 'string'
    && isRiskLevel(value.riskLevel)
    && typeof value.summary === 'string'
    && Array.isArray(value.factors)
    && value.factors.every(isReportRiskFactor)
    && Array.isArray(value.evidence)
    && value.evidence.every(isReportEvidenceItem)
    && typeof value.createdAt === 'string'
}

function readJsonArray<T>(key: string, isItem: (value: unknown) => value is T): T[] {
  const raw = localStorage.getItem(key)
  if (raw === null) {
    return []
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(raw) as unknown
  } catch {
    localStorage.removeItem(key)
    return []
  }

  if (!Array.isArray(parsed) || !parsed.every(isItem)) {
    localStorage.removeItem(key)
    return []
  }

  return parsed
}

function writeJson<T>(key: string, value: T) {
  localStorage.setItem(key, JSON.stringify(value))
}

export function loadWatchlist(): WatchlistItem[] {
  return readJsonArray(WATCHLIST_KEY, isWatchlistItem)
}

export function saveWatchlistItem(item: WatchlistItem) {
  const items = loadWatchlist().filter((entry) => entry.companyName !== item.companyName)
  writeJson(WATCHLIST_KEY, [item, ...items])
}

export function removeWatchlistItem(companyName: string) {
  writeJson(WATCHLIST_KEY, loadWatchlist().filter((entry) => entry.companyName !== companyName))
}

export function loadReports(): DueDiligenceReport[] {
  return readJsonArray(REPORTS_KEY, isDueDiligenceReport)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
}

export function saveReport(report: DueDiligenceReport) {
  const reports = loadReports().filter((entry) => entry.id !== report.id)
  writeJson(REPORTS_KEY, [report, ...reports].sort((a, b) => b.createdAt.localeCompare(a.createdAt)))
}

export function removeReport(reportId: string) {
  writeJson(REPORTS_KEY, loadReports().filter((entry) => entry.id !== reportId))
}
