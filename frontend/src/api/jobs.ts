import { apiGet, apiPost } from './client'
import type { JobListResponse, JobRun } from './types'

export function listJobs() {
  return apiGet<JobListResponse>('/jobs')
}

export function runAkshareJob() {
  return apiPost<JobRun>('/jobs/akshare/run')
}

export function getJob(jobRunId: string) {
  return apiGet<JobRun>(`/jobs/${encodeURIComponent(jobRunId)}`)
}
