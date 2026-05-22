import { Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../services/api'

interface ReportsPageProps {
  theme: 'light' | 'dark'
}

interface ReportItem {
  id: string
  name: string
  type: 'PDF' | 'CSV'
  status: 'Ready' | 'Generating'
  description: string
  generated_at: string
}

interface ReportsMetrics {
  available_reports: number
  ready_to_download: number
  pending_generation: number
}

interface ReportsResponse {
  metrics: ReportsMetrics
  reports: ReportItem[]
}

function getStatusTone(status: ReportItem['status'], isDark: boolean) {
  if (status === 'Ready') {
    return isDark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-100 text-emerald-700'
  }

  return isDark ? 'bg-amber-500/15 text-amber-200' : 'bg-amber-100 text-amber-700'
}

function getFilenameFromDisposition(disposition: string | null, fallback: string) {
  const match = disposition?.match(/filename="?([^"]+)"?/i)
  return match?.[1] || fallback
}

function triggerBrowserDownload(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  anchor.href = url
  anchor.download = filename
  anchor.click()

  URL.revokeObjectURL(url)
}

export default function ReportsPage({ theme }: ReportsPageProps) {
  const isDark = theme === 'dark'
  const [reports, setReports] = useState<ReportItem[]>([])
  const [metrics, setMetrics] = useState<ReportsMetrics>({
    available_reports: 0,
    ready_to_download: 0,
    pending_generation: 0,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState('')
  const [activeDownloadId, setActiveDownloadId] = useState<string | null>(null)

  const metricCards = useMemo(
    () => [
      {
        label: 'Available Reports',
        value: metrics.available_reports,
        accent: 'Export-ready operational files',
      },
      {
        label: 'Ready To Download',
        value: metrics.ready_to_download,
        accent: 'Instant report downloads enabled',
      },
      {
        label: 'Pending Generation',
        value: metrics.pending_generation,
        accent: 'Waiting for final compilation',
      },
    ],
    [metrics],
  )

  const loadReports = async () => {
    setIsLoading(true)
    setErrorMessage('')

    try {
      const response = await apiFetch('/api/v1/reports')
      if (!response.ok) {
        setErrorMessage('Unable to load reports right now')
        setIsLoading(false)
        return
      }

      const payload = (await response.json()) as ReportsResponse
      setReports(payload.reports)
      setMetrics(payload.metrics)
      setIsLoading(false)
    } catch {
      setErrorMessage('Unable to load reports right now')
      setIsLoading(false)
    }
  }

  useEffect(() => {
    void loadReports()
  }, [])

  const handleDownload = async (report: ReportItem) => {
    if (report.status !== 'Ready') {
      return
    }

    setActiveDownloadId(report.id)

    try {
      const response = await apiFetch(`/api/v1/reports/${report.id}/download`)
      if (!response.ok) {
        setErrorMessage('Unable to download this report right now')
        return
      }

      const blob = await response.blob()
      const fallbackName = `${report.id}.${report.type.toLowerCase()}`
      const filename = getFilenameFromDisposition(response.headers.get('Content-Disposition'), fallbackName)
      triggerBrowserDownload(filename, blob)
    } catch {
      setErrorMessage('Unable to download this report right now')
    } finally {
      setActiveDownloadId(null)
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {metricCards.map((metric) => (
          <article
            key={metric.label}
            className={`rounded-lg border p-5 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <p className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</p>
            <p className={`mt-3 text-3xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{metric.value}</p>
            <p className={`mt-2 text-sm ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>{metric.accent}</p>
          </article>
        ))}
      </section>

      <section
        className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
          isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
        }`}
      >
        <div className="mb-6">
          <h1 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Reports</h1>
          <p className={`mt-2 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
            Download investigation packs, watchlist summaries, and operational exports directly from the dashboard.
          </p>
        </div>

        {errorMessage ? (
          <div
            className={`mb-4 rounded-2xl border px-4 py-3 text-sm ${
              isDark ? 'border-rose-500/30 bg-rose-500/10 text-rose-200' : 'border-rose-200 bg-rose-50 text-rose-700'
            }`}
          >
            {errorMessage}
          </div>
        ) : null}

        <div className="space-y-4">
          {isLoading ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              Loading reports...
            </div>
          ) : reports.length === 0 ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              No reports available yet.
            </div>
          ) : (
            reports.map((report) => {
            const isBusy = activeDownloadId === report.id
            const Icon = report.type === 'CSV' ? FileSpreadsheet : FileText

            return (
              <article
                key={report.id}
                className={`rounded-[1.5rem] border p-5 ${
                  isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                }`}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex items-start gap-4">
                    <div
                      className={`rounded-2xl p-3 ${
                        isDark ? 'bg-slate-900 text-cyan-300' : 'bg-white text-emerald-700'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className={`text-lg font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{report.name}</h2>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${getStatusTone(report.status, isDark)}`}>
                          {report.status}
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            isDark ? 'bg-slate-700 text-slate-200' : 'bg-white text-slate-700 ring-1 ring-slate-200'
                          }`}
                        >
                          {report.type}
                        </span>
                      </div>
                      <p className={`mt-2 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{report.description}</p>
                      <p className={`mt-2 text-xs ${isDark ? 'text-slate-500' : 'text-slate-500'}`}>
                        Generated: {report.generated_at}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    disabled={report.status !== 'Ready' || isBusy}
                    onClick={() => void handleDownload(report)}
                    className={`inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-semibold transition-colors ${
                      report.status === 'Ready'
                        ? isDark
                          ? 'bg-cyan-400 text-slate-950 hover:bg-cyan-300'
                          : 'bg-emerald-700 text-white hover:bg-emerald-600'
                        : isDark
                          ? 'bg-slate-700 text-slate-400'
                          : 'bg-slate-200 text-slate-500'
                    } disabled:cursor-not-allowed disabled:opacity-80`}
                  >
                    {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                    {report.status === 'Ready' ? 'Download' : 'Generating'}
                  </button>
                </div>
              </article>
            )
            })
          )}
        </div>
      </section>
    </div>
  )
}
