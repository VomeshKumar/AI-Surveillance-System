import { useEffect, useState } from 'react'
import { Expand, Shrink, Plus, X, Loader2 } from 'lucide-react'
import { fetchCameras, createCamera, deleteCamera, Camera, CameraCreatePayload } from '../api/cameras'
import { useAuth } from '../context/AuthContext'

interface CamerasPageProps {
  theme: 'light' | 'dark'
}

export default function CamerasPage({ theme }: CamerasPageProps) {
  const isDark = theme === 'dark'
  const { user } = useAuth()
  const [activeCamera, setActiveCamera] = useState<Camera | null>(null)
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Add Camera Modal State
  const [showAddModal, setShowAddModal] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [newCamera, setNewCamera] = useState<CameraCreatePayload>({
    camera_id: '',
    camera_name: '',
    location: '',
    rtsp_url: '',
    status: 'Online',
  })

  useEffect(() => {
    loadCameras()
  }, [])

  const loadCameras = async () => {
    try {
      setLoading(true)
      const data = await fetchCameras()
      setCameras(data)
    } catch (err: any) {
      setError(err.message || 'Failed to load cameras')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!activeCamera && !showAddModal) return

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveCamera(null)
        setShowAddModal(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [activeCamera, showAddModal])

  const getStatusClasses = (status: string) => {
    switch (status.toLowerCase()) {
      case 'online':
        return 'bg-green-500/20 text-green-400'
      case 'offline':
        return 'bg-red-500/20 text-red-400'
      default:
        return 'bg-yellow-500/20 text-yellow-400'
    }
  }

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setIsSubmitting(true)
      setError('')
      await createCamera(newCamera)
      await loadCameras()
      setShowAddModal(false)
      setNewCamera({ camera_id: '', camera_name: '', location: '', rtsp_url: '', status: 'Online' })
    } catch (err: any) {
      setError(err.message || 'Failed to add camera')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDelete = async (cameraId: string) => {
    if (!window.confirm(`Are you sure you want to delete camera ${cameraId}?`)) return
    try {
      await deleteCamera(cameraId)
      await loadCameras()
    } catch (err: any) {
      alert(err.message || 'Failed to delete camera')
    }
  }

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className={`text-2xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
            Cameras
          </h1>
          <p className={`${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            Multi-camera live surveillance monitoring
          </p>
        </div>

        {user?.role === 'admin' && (
          <button
            onClick={() => setShowAddModal(true)}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              isDark
                ? 'bg-blue-600 text-white hover:bg-blue-500'
                : 'bg-slate-900 text-white hover:bg-slate-800'
            }`}
          >
            <Plus className="h-4 w-4" />
            Add Camera
          </button>
        )}
      </div>

      {error && !showAddModal && (
        <div className="mb-4 rounded-lg bg-red-500/20 p-4 text-red-500">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className={`h-8 w-8 animate-spin ${isDark ? 'text-blue-500' : 'text-slate-900'}`} />
        </div>
      ) : cameras.length === 0 ? (
        <div className={`flex flex-col items-center justify-center rounded-lg border border-dashed py-24 ${isDark ? 'border-slate-700' : 'border-slate-300'}`}>
          <p className={`${isDark ? 'text-slate-400' : 'text-slate-500'} mb-4`}>No cameras found</p>
          {user?.role === 'admin' && (
            <button
              onClick={() => setShowAddModal(true)}
              className="text-blue-500 hover:underline"
            >
              Add your first camera
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {cameras.map((camera) => (
            <article
              key={camera.camera_id}
              className={`rounded-lg border p-6 shadow-sm ${
                isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
              }`}
            >
              <div
                className={`mb-4 h-40 rounded-[1.25rem] flex items-center justify-center overflow-hidden ${
                  isDark ? 'bg-slate-800' : 'bg-slate-100'
                }`}
              >
                {camera.status.toLowerCase() === 'online' && camera.camera_id ? (
                  <img
                    src={`http://localhost:8001/api/v1/cameras/stream?camera_id=${encodeURIComponent(camera.camera_id)}&view=grid`}
                    alt={`Live feed from ${camera.camera_name}`}
                    loading="eager"
                    decoding="async"
                    className="h-full w-full object-cover rounded-[1.25rem]"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                      const fallback = e.currentTarget.parentElement?.querySelector('.fallback-text');
                      if (fallback) fallback.classList.remove('hidden');
                    }}
                  />
                ) : null}
                <span className={`fallback-text ${camera.status.toLowerCase() === 'online' ? 'hidden' : ''} ${isDark ? 'text-slate-500' : 'text-slate-400'} flex flex-col items-center gap-2 text-center px-4`}>
                  <span className="font-medium text-slate-400">● AI Engine Active</span>
                  <span className="text-xs">Waiting for stream...</span>
                </span>
              </div>

              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className={`text-lg font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                    {camera.camera_name}
                  </h2>
                  <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                    {camera.location ? `${camera.location} • ` : ''}{camera.camera_id}
                  </p>
                  <span className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs ${getStatusClasses(camera.status)}`}>
                    {camera.status}
                  </span>
                </div>

                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveCamera(camera)}
                    className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-colors ${
                      isDark
                        ? 'border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700'
                        : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                    }`}
                    aria-label={`Open ${camera.camera_name} in full screen`}
                  >
                    <Expand className="h-4 w-4" />
                  </button>
                  {user?.role === 'admin' && (
                    <button
                      type="button"
                      onClick={() => handleDelete(camera.camera_id)}
                      className="text-xs text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Full Screen Camera View */}
      {activeCamera && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95 p-4">
          <article
            className={`flex h-full w-full max-w-7xl flex-col rounded-3xl border p-6 shadow-2xl ${
              isDark ? 'border-slate-700 bg-slate-900' : 'border-slate-200 bg-white'
            }`}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h1 className={`text-2xl font-semibold ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>
                  {activeCamera.camera_name}
                </h1>
                <p className={`text-sm ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                  {activeCamera.location} • Press ESC to exit full screen
                </p>
              </div>

              <button
                type="button"
                onClick={() => setActiveCamera(null)}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 text-slate-100 hover:bg-slate-700'
                    : 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'
                }`}
              >
                <Shrink className="h-4 w-4" />
                Exit
              </button>
            </div>

            <div
              className={`flex-1 rounded-[1.75rem] overflow-hidden relative ${
                isDark ? 'bg-slate-800' : 'bg-slate-100'
              }`}
            >
              {activeCamera.camera_id ? (
                <img
                  src={`http://localhost:8001/api/v1/cameras/stream?camera_id=${encodeURIComponent(activeCamera.camera_id)}&view=fullscreen`}
                  alt={`Live feed - ${activeCamera.camera_name}`}
                  loading="eager"
                  decoding="async"
                  className="h-full w-full object-contain"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                    const fallback = document.getElementById('fullscreen-fallback');
                    if (fallback) fallback.classList.remove('hidden');
                  }}
                />
              ) : null}
              <div id="fullscreen-fallback" className="hidden absolute inset-0 flex flex-col items-center justify-center gap-3 text-center p-8">
                <span className={`text-lg font-medium ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>● AI Engine Active — No frame yet</span>
                <span className={`text-sm ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>Ensure the AI Engine camera worker is running for this camera</span>
              </div>
            </div>
          </article>
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className={`w-full max-w-md rounded-2xl p-6 ${isDark ? 'bg-slate-900 text-white' : 'bg-white text-slate-900'}`}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-bold">Add New Camera</h2>
              <button onClick={() => setShowAddModal(false)} className="rounded-full p-1 hover:bg-slate-800/20">
                <X className="h-5 w-5" />
              </button>
            </div>

            {error && (
              <div className="mb-4 rounded bg-red-500/20 p-3 text-sm text-red-500">
                {error}
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-4">
              <div>
                <label className={`mb-1 block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Camera ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., CAM_FRONT_DOOR"
                  value={newCamera.camera_id}
                  onChange={(e) => setNewCamera({ ...newCamera, camera_id: e.target.value })}
                  className={`w-full rounded-lg border p-2 focus:outline-none focus:ring-2 ${
                    isDark ? 'border-slate-700 bg-slate-800 focus:ring-blue-500' : 'border-slate-300 bg-white focus:ring-blue-500'
                  }`}
                />
              </div>

              <div>
                <label className={`mb-1 block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Display Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Main Entrance"
                  value={newCamera.camera_name}
                  onChange={(e) => setNewCamera({ ...newCamera, camera_name: e.target.value })}
                  className={`w-full rounded-lg border p-2 focus:outline-none focus:ring-2 ${
                    isDark ? 'border-slate-700 bg-slate-800 focus:ring-blue-500' : 'border-slate-300 bg-white focus:ring-blue-500'
                  }`}
                />
              </div>

              <div>
                <label className={`mb-1 block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>Location</label>
                <input
                  type="text"
                  placeholder="e.g., North Gate"
                  value={newCamera.location}
                  onChange={(e) => setNewCamera({ ...newCamera, location: e.target.value })}
                  className={`w-full rounded-lg border p-2 focus:outline-none focus:ring-2 ${
                    isDark ? 'border-slate-700 bg-slate-800 focus:ring-blue-500' : 'border-slate-300 bg-white focus:ring-blue-500'
                  }`}
                />
              </div>

              <div>
                <label className={`mb-1 block text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>RTSP URL (Optional)</label>
                <input
                  type="text"
                  placeholder="rtsp://admin:pass@192.168.1.100/stream"
                  value={newCamera.rtsp_url}
                  onChange={(e) => setNewCamera({ ...newCamera, rtsp_url: e.target.value })}
                  className={`w-full rounded-lg border p-2 focus:outline-none focus:ring-2 ${
                    isDark ? 'border-slate-700 bg-slate-800 focus:ring-blue-500' : 'border-slate-300 bg-white focus:ring-blue-500'
                  }`}
                />
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className={`rounded-lg px-4 py-2 font-medium transition-colors ${
                    isDark ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                  }`}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className={`inline-flex items-center justify-center rounded-lg px-4 py-2 font-medium text-white transition-colors ${
                    isSubmitting ? 'bg-blue-600/50 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Add Camera
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
