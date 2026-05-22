import { Archive, Image as ImageIcon, Pencil, Plus, Shield, Trash2, User } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useAuth } from '../context/AuthContext'
import { apiFetch } from '../services/api'

interface FaceDataPageProps {
  theme: 'light' | 'dark'
}

interface FaceIdentity {
  id: number
  name: string
  category: string
  registered_by: string | null
  has_image: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

interface FaceIdentityFormState {
  name: string
  category: string
  imageFile: File | null
}

interface ApiErrorPayload {
  detail?: string
}

const emptyForm: FaceIdentityFormState = {
  name: '',
  category: '',
  imageFile: null,
}

async function parseApiError(response: Response) {
  try {
    const payload = (await response.json()) as ApiErrorPayload
    return payload.detail || 'Unable to complete the request right now'
  } catch {
    return 'Unable to complete the request right now'
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatCategoryLabel(value: string) {
  return value.replace(/_/g, ' ')
}

function getCategoryTone(category: string, isDark: boolean) {
  if (category === 'priority') {
    return isDark ? 'bg-rose-500/15 text-rose-300' : 'bg-rose-100 text-rose-700'
  }

  if (category === 'monitor') {
    return isDark ? 'bg-amber-400/15 text-amber-200' : 'bg-amber-100 text-amber-700'
  }

  return isDark ? 'bg-cyan-400/10 text-cyan-300' : 'bg-emerald-100 text-emerald-700'
}

export default function FaceDataPage({ theme }: FaceDataPageProps) {
  const isDark = theme === 'dark'
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [identities, setIdentities] = useState<FaceIdentity[]>([])
  const [identityImageUrls, setIdentityImageUrls] = useState<Record<number, string>>({})
  const [form, setForm] = useState<FaceIdentityFormState>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')

  const filteredIdentities = useMemo(() => {
    const query = searchQuery.trim().toLowerCase()

    return identities.filter((identity) => {
      const matchesQuery =
        !query ||
        [identity.name, identity.category, identity.registered_by ?? '', identity.is_active ? 'active' : 'inactive'].some((value) =>
          value.toLowerCase().includes(query),
        )

      const matchesCategory = categoryFilter === 'all' || identity.category === categoryFilter

      return matchesQuery && matchesCategory
    })
  }, [categoryFilter, identities, searchQuery])

  const activeCount = useMemo(() => identities.filter((identity) => identity.is_active).length, [identities])
  const withImageCount = useMemo(() => identities.filter((identity) => identity.has_image).length, [identities])
  const withOperatorCount = useMemo(() => identities.filter((identity) => Boolean(identity.registered_by)).length, [identities])

  const resetForm = () => {
    setForm(emptyForm)
    setEditingId(null)
    setImagePreviewUrl('')
  }

  useEffect(() => {
    if (!form.imageFile) {
      setImagePreviewUrl('')
      return
    }

    const previewUrl = URL.createObjectURL(form.imageFile)
    setImagePreviewUrl(previewUrl)

    return () => {
      URL.revokeObjectURL(previewUrl)
    }
  }, [form.imageFile])

  const loadIdentities = async () => {
    setIsLoading(true)
    setErrorMessage('')

    try {
      const response = await apiFetch('/api/v1/faces?limit=100')

      if (!response.ok) {
        setIsLoading(false)
        setErrorMessage(await parseApiError(response))
        return
      }

      const payload = (await response.json()) as FaceIdentity[]
      setIdentities(payload)
      setIsLoading(false)
    } catch {
      setIsLoading(false)
      setErrorMessage('Unable to load face identities right now')
    }
  }

  useEffect(() => {
    void loadIdentities()
  }, [])

  useEffect(() => {
    const imageUrlsToCleanup: string[] = []
    let isCancelled = false

    const loadIdentityImages = async () => {
      const identitiesWithImages = identities.filter((identity) => identity.has_image)

      if (!identitiesWithImages.length) {
        setIdentityImageUrls({})
        return
      }

      const imageEntries = await Promise.all(
        identitiesWithImages.map(async (identity) => {
          try {
            const response = await apiFetch(`/api/v1/faces/${identity.id}/image`)
            if (!response.ok) {
              return [identity.id, ''] as const
            }

            const blob = await response.blob()
            const objectUrl = URL.createObjectURL(blob)
            imageUrlsToCleanup.push(objectUrl)
            return [identity.id, objectUrl] as const
          } catch {
            return [identity.id, ''] as const
          }
        }),
      )

      if (!isCancelled) {
        setIdentityImageUrls(
          Object.fromEntries(imageEntries.filter(([, imageUrl]) => Boolean(imageUrl))),
        )
      }
    }

    void loadIdentityImages()

    return () => {
      isCancelled = true
      imageUrlsToCleanup.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [identities])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const trimmedForm = {
      name: form.name.trim(),
      category: form.category.trim().toLowerCase(),
      imageFile: form.imageFile,
    }

    if (!trimmedForm.name) {
      setErrorMessage('Name is required')
      return
    }

    if (!trimmedForm.category) {
      setErrorMessage('Category is required')
      return
    }

    if (editingId === null && !trimmedForm.imageFile) {
      setErrorMessage('Image file is required')
      return
    }

    setIsSubmitting(true)
    setErrorMessage('')

    const endpoint = editingId === null ? '/api/v1/faces/enroll' : `/api/v1/faces/${editingId}`
    const method = editingId === null ? 'POST' : 'PATCH'

    try {
      const body = new FormData()
      body.set('name', trimmedForm.name)
      body.set('category', trimmedForm.category)

      if (trimmedForm.imageFile) {
        body.set('image', trimmedForm.imageFile)
      }

      const response = await apiFetch(endpoint, {
        method,
        body,
      })

      if (!response.ok) {
        setIsSubmitting(false)
        setErrorMessage(await parseApiError(response))
        return
      }

      const savedIdentity = (await response.json()) as FaceIdentity

      setIdentities((current) =>
        editingId === null
          ? [savedIdentity, ...current]
          : current.map((identity) => (identity.id === editingId ? savedIdentity : identity)),
      )

      setIsSubmitting(false)
      resetForm()
    } catch {
      setIsSubmitting(false)
      setErrorMessage('Unable to save face identity right now')
    }
  }

  const handleEdit = (identity: FaceIdentity) => {
    setEditingId(identity.id)
    setForm({
      name: identity.name,
      category: identity.category,
      imageFile: null,
    })
    setErrorMessage('')
  }

  const handleDelete = async (identity: FaceIdentity) => {
    setErrorMessage('')

    try {
      const response = await apiFetch(`/api/v1/faces/${identity.id}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        return
      }

      setIdentities((current) =>
        current.map((item) =>
          item.id === identity.id
            ? {
                ...item,
                is_active: false,
              }
            : item,
        ),
      )

      if (editingId === identity.id) {
        resetForm()
      }
    } catch {
      setErrorMessage('Unable to deactivate face identity right now')
    }
  }

  const handleActivate = async (identity: FaceIdentity) => {
    setErrorMessage('')

    try {
      const response = await apiFetch(`/api/v1/faces/${identity.id}/activate`, {
        method: 'PATCH',
      })

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        return
      }

      setIdentities((current) =>
        current.map((item) =>
          item.id === identity.id
            ? {
                ...item,
                is_active: true,
              }
            : item,
        ),
      )
    } catch {
      setErrorMessage('Unable to activate face identity right now')
    }
  }

  const handlePermanentDelete = async (identity: FaceIdentity) => {
    setErrorMessage('')

    try {
      const response = await apiFetch(`/api/v1/faces/${identity.id}/permanent`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        setErrorMessage(await parseApiError(response))
        return
      }

      setIdentities((current) => current.filter((item) => item.id !== identity.id))

      if (editingId === identity.id) {
        resetForm()
      }
    } catch {
      setErrorMessage('Unable to permanently delete face identity right now')
    }
  }

  return (
    <div className="space-y-6">
      {isAdmin ? (
        <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
          {[
            { label: 'Total Identities', value: identities.length, accent: 'Live rows from face_identities' },
            { label: 'Active Records', value: activeCount, accent: 'Currently marked active' },
            { label: 'Image Attached', value: withImageCount, accent: 'Rows with image binary data' },
            { label: 'Registered By User', value: withOperatorCount, accent: 'Rows with registered_by populated' },
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
      ) : null}

      <section className={`grid gap-6 ${isAdmin ? 'xl:grid-cols-[1fr_1.35fr]' : ''}`}>
        {isAdmin ? (
          <article
            className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <h1 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  Face Identity Control
                </h1>
              </div>
              <div
                className={`rounded-2xl p-3 ${
                  isDark ? 'bg-cyan-400/10 text-cyan-300' : 'bg-emerald-50 text-emerald-700'
                }`}
              >
                <Shield className="h-6 w-6" />
              </div>
            </div>

            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block md:col-span-2">
                  <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                    Full Name <span className="text-rose-500">*</span>
                  </span>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    placeholder="Enter identity name"
                    className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                        : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                    }`}
                  />
                </label>

                <label className="block md:col-span-2">
                  <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                    Category <span className="text-rose-500">*</span>
                  </span>
                  <input
                    type="text"
                    value={form.category}
                    onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
                    placeholder="Enter category, for example suspect"
                    className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                        : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                    }`}
                  />
                </label>

                <label className="block md:col-span-2">
                  <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                    Image Upload {editingId === null ? <span className="text-rose-500">*</span> : null}
                  </span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        imageFile: event.target.files?.[0] ?? null,
                      }))
                    }
                    className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition-colors file:mr-4 file:rounded-xl file:border-0 file:px-3 file:py-2 file:text-sm file:font-medium ${
                      isDark
                        ? 'border-slate-700 bg-slate-800 text-slate-100 file:bg-slate-700 file:text-slate-100'
                        : 'border-slate-200 bg-slate-50 text-slate-900 file:bg-white file:text-slate-700'
                    }`}
                  />
                  <p className={`mt-2 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {form.imageFile
                      ? `Selected file: ${form.imageFile.name}`
                      : editingId === null
                        ? 'Image file is required and will be stored in the face_identities.image column.'
                        : 'Choose a new image only if you want to replace the existing one.'}
                  </p>
                </label>

                <div
                  className={`md:col-span-2 rounded-[1.25rem] border p-4 ${
                    isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <p className={`mb-3 text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Image Preview</p>
                  {imagePreviewUrl ? (
                    <div className="overflow-hidden rounded-[1rem] border border-slate-200/20">
                      <img src={imagePreviewUrl} alt="Selected face preview" className="h-56 w-full object-cover" />
                    </div>
                  ) : (
                    <div
                      className={`flex h-56 items-center justify-center rounded-[1rem] border border-dashed text-sm ${
                        isDark ? 'border-slate-600 text-slate-400' : 'border-slate-300 text-slate-500'
                      }`}
                    >
                      Select an image file to preview it here.
                    </div>
                  )}
                </div>
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
                  className={`inline-flex rounded-2xl px-5 py-3 text-sm font-semibold text-white transition-colors ${
                    isDark ? 'bg-cyan-500 hover:bg-cyan-400' : 'bg-emerald-700 hover:bg-emerald-600'
                  } disabled:cursor-not-allowed disabled:opacity-70`}
                >
                  {isSubmitting ? 'Saving...' : editingId !== null ? 'Update Identity' : 'Create Identity'}
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
        ) : null}

        <article
          className={`rounded-lg border p-6 shadow-[0_3px_10px_rgba(15,23,42,0.5)] ${
            isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
          }`}
        >
          <div className="mb-5 flex flex-col gap-4">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div
                  className={`rounded-2xl p-3 ${
                    isDark ? 'bg-slate-800 text-cyan-300' : 'bg-slate-50 text-emerald-700'
                  }`}
                >
                  <Archive className="h-5 w-5" />
                </div>
                <div>
                  <h2 className={`text-xl font-bold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                    Face Identities
                  </h2>
                </div>
              </div>

              <button
                type="button"
                onClick={() => void loadIdentities()}
                className={`inline-flex items-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700'
                    : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                }`}
              >
                <Plus className="h-4 w-4" />
                Refresh
              </button>
            </div>

            <div className="grid gap-3 md:grid-cols-[1.4fr_1fr]">
              <input
                type="text"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search by name, category"
                className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-500'
                    : 'border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400'
                }`}
              />

              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
                className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
                  isDark ? 'border-slate-700 bg-slate-800 text-slate-100' : 'border-slate-200 bg-slate-50 text-slate-900'
                }`}
              >
                <option value="all">All categories</option>
                {Array.from(new Set(identities.map((identity) => identity.category).filter(Boolean))).map((option) => (
                  <option key={option} value={option}>
                    {formatCategoryLabel(option)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {isLoading ? (
            <div
              className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
              }`}
            >
              Loading face identities...
            </div>
          ) : (
            <div className="space-y-3">
              {filteredIdentities.map((identity) => (
                <div
                  key={identity.id}
                  className={`rounded-[1.5rem] border p-4 ${
                    isDark ? 'border-slate-700 bg-slate-800' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex flex-1 flex-col gap-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className={`text-lg font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                          {identity.name}
                        </h3>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${getCategoryTone(identity.category, isDark)}`}>
                          {formatCategoryLabel(identity.category)}
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            isDark ? 'bg-slate-700 text-slate-200' : 'bg-slate-200 text-slate-700'
                          }`}
                        >
                          ID #{identity.id}
                        </span>
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-semibold ${
                            identity.is_active
                              ? isDark
                                ? 'bg-emerald-500/15 text-emerald-300'
                                : 'bg-emerald-100 text-emerald-700'
                              : isDark
                                ? 'bg-slate-700 text-slate-300'
                                : 'bg-slate-200 text-slate-600'
                          }`}
                        >
                          {identity.is_active ? 'Active' : 'Deactivated'}
                        </span>
                      </div>

                      <div className={`grid gap-2 text-sm md:grid-cols-2 ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
                        <p className="inline-flex items-center gap-2">
                          <User className="h-4 w-4" />
                          Registered by: {identity.registered_by || 'System'}
                        </p>
                        <p className="inline-flex items-center gap-2">
                          <ImageIcon className="h-4 w-4" />
                          Image data: {identity.has_image ? 'Available' : 'Not attached'}
                        </p>
                        <p>Created: {formatDate(identity.created_at)}</p>
                        <p>Updated: {formatDate(identity.updated_at)}</p>
                      </div>
                    </div>

                    <div className="flex flex-col items-stretch gap-3 sm:flex-row lg:flex-col lg:items-end">
                      <div
                        className={`flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-[1.25rem] border ${
                          isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
                        }`}
                      >
                        {identityImageUrls[identity.id] ? (
                          <img
                            src={identityImageUrls[identity.id]}
                            alt={`${identity.name} face`}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <span className={`px-2 text-center text-xs ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                            No image
                          </span>
                        )}
                      </div>

                      {isAdmin ? (
                        <div className="flex gap-3">
                          <button
                            type="button"
                            onClick={() => handleEdit(identity)}
                            className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                              isDark
                                ? 'bg-slate-700 text-slate-100 hover:bg-slate-600'
                                : 'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-100'
                            }`}
                          >
                            <Pencil className="h-4 w-4" />
                            Edit
                          </button>
                          {identity.is_active ? (
                            <button
                              type="button"
                              onClick={() => void handleDelete(identity)}
                              className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                                isDark ? 'bg-rose-500/15 text-rose-300 hover:bg-rose-500/25' : 'bg-rose-50 text-rose-700 hover:bg-rose-100'
                              }`}
                            >
                              <Trash2 className="h-4 w-4" />
                              Deactivate
                            </button>
                          ) : (
                            <button
                              type="button"
                              onClick={() => void handleActivate(identity)}
                              className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                                isDark ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                              }`}
                            >
                              <Shield className="h-4 w-4" />
                              Activate
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => void handlePermanentDelete(identity)}
                            className={`inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-semibold transition-colors ${
                              isDark ? 'bg-rose-700/40 text-rose-100 hover:bg-rose-700/60' : 'bg-rose-700 text-white hover:bg-rose-600'
                            }`}
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}

              {filteredIdentities.length === 0 ? (
                <div
                  className={`rounded-[1.5rem] border border-dashed p-8 text-center ${
                    isDark ? 'border-slate-700 bg-slate-800 text-slate-400' : 'border-slate-300 bg-slate-50 text-slate-600'
                  }`}
                >
                  No face identities found for the current search or category filter.
                </div>
              ) : null}
            </div>
          )}
        </article>
      </section>
    </div>
  )
}
