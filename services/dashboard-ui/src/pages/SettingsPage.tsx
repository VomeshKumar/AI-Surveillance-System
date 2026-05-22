import { KeyRound, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { changePassword } from '../api/auth'
import { useAuth } from '../context/AuthContext'

interface SettingsPageProps {
  theme: 'light' | 'dark'
}

interface ChangePasswordFormState {
  currentPassword: string
  newPassword: string
  confirmPassword: string
}

const initialFormState: ChangePasswordFormState = {
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
}

export default function SettingsPage({ theme }: SettingsPageProps) {
  const isDark = theme === 'dark'
  const { user } = useAuth()
  const [form, setForm] = useState<ChangePasswordFormState>(initialFormState)
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!form.currentPassword || !form.newPassword || !form.confirmPassword) {
      setSuccessMessage('')
      setErrorMessage('All password fields are required')
      return
    }

    if (form.newPassword.length < 6) {
      setSuccessMessage('')
      setErrorMessage('New password must be at least 6 characters long')
      return
    }

    if (form.newPassword !== form.confirmPassword) {
      setSuccessMessage('')
      setErrorMessage('New password and confirm password do not match')
      return
    }

    if (form.currentPassword === form.newPassword) {
      setSuccessMessage('')
      setErrorMessage('New password must be different from the current password')
      return
    }

    setIsSubmitting(true)
    setErrorMessage('')
    setSuccessMessage('')

    try {
      const message = await changePassword(form)
      setSuccessMessage(message)
      setForm(initialFormState)
      setIsSubmitting(false)
    } catch (error) {
      setSuccessMessage('')
      setErrorMessage(error instanceof Error ? error.message : 'Unable to change password right now')
      setIsSubmitting(false)
    }
  }

  const inputClassName = `w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
    isDark
      ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
      : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
  }`

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: 'Signed In As', value: user?.name ?? 'Unknown', accent: 'Current operator account' },
          { label: 'Access Role', value: user?.role === 'admin' ? 'Admin' : 'Security Officer', accent: 'Role-based access active' },
          { label: 'Password Policy', value: 'Min 6 Chars', accent: 'Choose a stronger password regularly' },
        ].map((metric) => (
          <article
            key={metric.label}
            className={`rounded-lg border p-5 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <p className={`text-sm font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>{metric.label}</p>
            <p className={`mt-3 break-words text-2xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{metric.value}</p>
            <p className={`mt-2 text-sm ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>{metric.accent}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.95fr_1.25fr]">
        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="flex items-start gap-4">
            <div
              className={`rounded-2xl p-3 ${
                isDark ? 'bg-cyan-400/10 text-cyan-300' : 'bg-emerald-50 text-emerald-700'
              }`}
            >
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div className="space-y-2">
              <h1 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                Settings
              </h1>
              <p className={`text-sm leading-6 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                Update your account password from here. For security, we verify your current password before saving the new one.
              </p>
            </div>
          </div>
        </article>

        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h2 className={`text-xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Change Password</h2>
              <p className={`mt-2 text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Use your current password and set a new secure password for this account.
              </p>
            </div>
            <div
              className={`rounded-2xl p-3 ${
                isDark ? 'bg-slate-800 text-cyan-300' : 'bg-slate-50 text-emerald-700'
              }`}
            >
              <KeyRound className="h-5 w-5" />
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                Current Password
              </span>
              <input
                type="password"
                value={form.currentPassword}
                onChange={(event) => setForm((current) => ({ ...current, currentPassword: event.target.value }))}
                placeholder="Enter current password"
                autoComplete="current-password"
                className={inputClassName}
              />
            </label>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  New Password
                </span>
                <input
                  type="password"
                  value={form.newPassword}
                  onChange={(event) => setForm((current) => ({ ...current, newPassword: event.target.value }))}
                  placeholder="Create a new password"
                  autoComplete="new-password"
                  className={inputClassName}
                />
              </label>

              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Confirm Password
                </span>
                <input
                  type="password"
                  value={form.confirmPassword}
                  onChange={(event) => setForm((current) => ({ ...current, confirmPassword: event.target.value }))}
                  placeholder="Re-enter new password"
                  autoComplete="new-password"
                  className={inputClassName}
                />
              </label>
            </div>

            {errorMessage ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark ? 'border-rose-500/30 bg-rose-500/10 text-rose-200' : 'border-rose-200 bg-rose-50 text-rose-700'
                }`}
              >
                {errorMessage}
              </div>
            ) : null}

            {successMessage ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                    : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                }`}
              >
                {successMessage}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className={`rounded-2xl px-5 py-3 text-sm font-semibold text-white transition-colors ${
                  isDark ? 'bg-cyan-500 hover:bg-cyan-400' : 'bg-emerald-700 hover:bg-emerald-600'
                } disabled:cursor-not-allowed disabled:opacity-70`}
              >
                {isSubmitting ? 'Updating...' : 'Update Password'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setForm(initialFormState)
                  setErrorMessage('')
                  setSuccessMessage('')
                }}
                className={`rounded-2xl border px-5 py-3 text-sm font-semibold transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
                    : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                }`}
              >
                Clear
              </button>
            </div>
          </form>
        </article>
      </section>
    </div>
  )
}
