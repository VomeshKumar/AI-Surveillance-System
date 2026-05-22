import { BrowserRouter } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { AuthProvider } from './context/AuthContext'
import AppRoutes from './routes/AppRoutes'

const THEME_STORAGE_KEY = 'aiflow-theme'

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window === 'undefined') {
      return 'light'
    }

    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)
    return storedTheme === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  return (
    <BrowserRouter>
      <AuthProvider>
        <div
          className={`min-h-screen font-sans transition-colors selection:bg-emerald-200 ${
            theme === 'dark' ? 'bg-slate-950' : 'bg-[#f8faf9]'
          }`}
        >
          <AppRoutes
            theme={theme}
            onToggleTheme={() => setTheme((current) => (current === 'light' ? 'dark' : 'light'))}
          />
        </div>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
