import { apiGet, apiPost } from './client'

export function listJobs() {
  return apiGet<Record<string, unknown>>('/jobs')
}

export function runAkshareJob() {
  return apiPost<Record<string, unknown>>('/jobs/akshare/run')
}
