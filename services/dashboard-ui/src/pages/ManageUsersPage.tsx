import { Pencil, ShieldCheck, Trash2, UserCog } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { apiFetch } from '../services/api'

interface ManageUsersPageProps {
  theme: 'light' | 'dark'
}

interface SecurityPersonnel {
  id: number
  name: string
  email: string
  operatorId: string
  isActive: boolean
}

interface UserFormState {
  name: string
  email: string
  operatorId: string
  password: string
  isActive: boolean
}

interface ApiErrorPayload {
  detail?: string
}

const emptyForm: UserFormState = {
  name: '',
  email: '',
  operatorId: '',
  password: '',
  isActive: true,
}

async function parseApiError(response: Response) {
  try {
    const payload = (await response.json()) as ApiErrorPayload
    return payload.detail || 'Unable to complete the request right now'
  } catch {
    return 'Unable to complete the request right now'
  }
}

export default function ManageUsersPage({ theme }: ManageUsersPageProps) {
  const isDark = theme === 'dark'
  const [personnel, setPersonnel] = useState<SecurityPersonnel[]>([])
  const [form, setForm] = useState<UserFormState>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const filteredPersonnel = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()

    if (!query) {
      return personnel
    }

    return personnel.filter((person) =>
      [person.name, person.email, person.operatorId, person.isActive ? 'active' : 'inactive'].some((value) =>
        value.toLowerCase().includes(query),
      ),
    )
  }, [personnel, searchQuery])

  const resetForm = () => {
    setForm(emptyForm)
    setEditingId(null)
  }

  const loadPersonnel = async () => {
    setIsLoading(true)
    setErrorMessage('')

    try {
      const response = await apiFetch('/api/v1/auth/users')

      if (!response.ok) {
        setIsLoading(false)
        setErrorMessage(await parseApiError(response))
        return
      }

      const payload = (await response.json()) as SecurityPersonnel[]
      setPersonnel(payload)
      setIsLoading(false)
    } catch {
      setIsLoading(false)
      setErrorMessage('Unable to load operators right now')
    }
  }

  useEffect(() => {
    void loadPersonnel()
  }, [])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedForm = {
      name: form.name.trim(),
      email: form.email.trim(),
      password: form.password.trim(),
      isActive: form.isActive,
    }

    if (!trimmedForm.name || !trimmedForm.email) {
      setErrorMessage('Name and email are required')
      return
    }

    if (editingId === null && !trimmedForm.password) {
      setErrorMessage('Password is required for a new operator')
      return
    }

    setIsSubmitting(true)
    setErrorMessage('')

    const endpoint = editingId === null ? '/api/v1/auth/users' : `/api/v1/auth/users/${editingId}`
    const method = editingId === null ? 'POST' : 'PUT'

    try {
      const response = await apiFetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...trimmedForm,
          password: trimmedForm.password || undefined,
        }),
      })

      if (!response.ok) {
        setIsSubmitting(false)
        setErrorMessage(await parseApiError(response))
        return
      }

      const savedPerson = (await response.json()) as SecurityPersonnel

      setPersonnel((current) =>
        editingId === null
          ? [savedPerson, ...current]
          : current.map((person) => (person.id === editingId ? savedPerson : person)),
      )

      setIsSubmitting(false)
      resetForm()
    } catch {
      setIsSubmitting(false)
      setErrorMessage('Unable to save operator right now')
    }
  }

  const handleEdit = (person: SecurityPersonnel) => {
    setEditingId(person.id)
    setForm({
      name: person.name,
      email: person.email,
      operatorId: person.operatorId,
      password: '',
      isActive: person.isActive,
    })
    setErrorMessage('')
  }

  const handleDelete = async (id: number) => {
    setErrorMessage('')

    try {
      const response = await apiFetch(`/api/v1/auth/users/${id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        return
      }

      setPersonnel((current) => current.filter((person) => person.id !== id))

      if (editingId === id) {
        resetForm()
      }
    } catch {
      setErrorMessage('Unable to delete operator right now')
    }
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {[
          { label: 'Total Operators', value: personnel.length, accent: 'All registered users' },
          { label: 'Login IDs', value: personnel.length, accent: 'Accounts ready for access' },
          { label: 'On Search Result', value: filteredPersonnel.length, accent: 'Matching current filter' },
        ].map((metric) => (
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

      <section className="grid gap-6 xl:grid-cols-[1fr_1.35fr]">
        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                Manage Users
              </h1>
            </div>
            <div
              className={`rounded-2xl p-3 ${
                isDark ? 'bg-cyan-400/10 text-cyan-300' : 'bg-emerald-50 text-emerald-700'
              }`}
            >
              <ShieldCheck className="h-6 w-6" />
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Full Name
                </span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="Enter operator name"
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                    isDark
                      ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                      : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </label>

              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Email
                </span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
                  placeholder="name@example.com"
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                    isDark
                      ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                      : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </label>

              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Operator ID
                </span>
                <input
                  type="text"
                  value={form.operatorId}
                  readOnly
                  placeholder={editingId === null ? 'Auto-generated on save' : 'Generated login ID'}
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                    isDark
                      ? 'border-slate-700 bg-slate-900/70 text-slate-300 placeholder:text-slate-500'
                      : 'border-slate-200 bg-slate-100 text-slate-700 placeholder:text-slate-400'
                  }`}
                />
              </label>

              <label className="block">
                <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                  Password
                </span>
                <input
                  type="text"
                  value={form.password}
                  onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                  placeholder={editingId === null ? 'Create password' : 'Leave blank to keep current password'}
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                    isDark ? 'border-slate-700 bg-slate-800 text-slate-100' : 'border-slate-200 bg-slate-50 text-slate-900'
                  }`}
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

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className={`rounded-2xl px-5 py-3 text-sm font-semibold text-white transition-colors ${
                  isDark ? 'bg-cyan-500 hover:bg-cyan-400' : 'bg-emerald-700 hover:bg-emerald-600'
                } disabled:cursor-not-allowed disabled:opacity-70`}
              >
                {isSubmitting ? 'Saving...' : editingId !== null ? 'Update Operator' : 'Add Operator'}
              </button>
              <button
                type="button"
                onClick={resetForm}
                className={`rounded-2xl border px-5 py-3 text-sm font-semibold transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-200 hover:bg-slate-700'
                    : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                }`}
              >
                Clear Form
              </button>
            </div>
          </form>
        </article>

        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`rounded-2xl p-3 ${
                  isDark ? 'bg-slate-800 text-cyan-300' : 'bg-slate-50 text-emerald-700'
                }`}
              >
                <UserCog className="h-5 w-5" />
              </div>
              <div>
                <h2 className={`text-xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  Operators
                </h2>
              </div>
            </div>

            <input
              type="text"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search operators"
              className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none sm:max-w-xs ${
                isDark
                  ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                  : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
              }`}
            />
          </div>

          {isLoading ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              Loading operators...
            </div>
          ) : (
            <div className="space-y-3">
              {filteredPersonnel.map((person) => (
                <div
                  key={person.id}
                  className={`rounded-[1.5rem] border p-4 ${
                    isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <h3 className={`text-lg font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                        {person.name}
                      </h3>
                      <p className={`text-sm ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>{person.email}</p>
                      <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                        ID: {person.operatorId}
                      </p>
                      <p className={`text-sm font-medium ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>
                        Status: {person.isActive ? 'Active' : 'Inactive'}
                      </p>
                    </div>

                    <div className="flex gap-3">
                      <button
                        type="button"
                        onClick={() => handleEdit(person)}
                        className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                          isDark
                            ? 'bg-slate-700 text-slate-100 hover:bg-slate-600'
                            : 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        <Pencil className="h-4 w-4" />
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDelete(person.id)}
                        className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                          isDark ? 'bg-rose-500/15 text-rose-300 hover:bg-rose-500/25' : 'bg-rose-50 text-rose-700 hover:bg-rose-100'
                        }`}
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}

              {filteredPersonnel.length === 0 ? (
                <div
                  className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                    isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
                  }`}
                >
                  No operators found for the current search.
                </div>
              ) : null}
            </div>
          )}
        </article>
      </section>
    </div>
  )
}
