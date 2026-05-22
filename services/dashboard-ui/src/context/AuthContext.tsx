import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { clearStoredAuthSession, persistAuthSession, restoreStoredAuthSession, type StoredAuthUser } from '../auth/session'
import { clearApiAccessToken, setApiAccessToken } from '../services/api'

export type UserRole = 'admin' | 'security_officer'

export type AuthUser = StoredAuthUser

interface AuthContextValue {
  user: AuthUser | null
  isAuthenticated: boolean
  isAuthResolved: boolean
  login: (user: AuthUser, rememberMe?: boolean) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isAuthResolved, setIsAuthResolved] = useState(false)

  useEffect(() => {
    const restoredUser = restoreStoredAuthSession()

    if (restoredUser) {
      setUser(restoredUser)
      setApiAccessToken(restoredUser.accessToken, restoredUser.tokenType)
    } else {
      clearApiAccessToken()
    }

    setIsAuthResolved(true)
  }, [])

  const login = (nextUser: AuthUser, rememberMe = false) => {
    setUser(nextUser)
    persistAuthSession(nextUser, rememberMe)
    setApiAccessToken(nextUser.accessToken, nextUser.tokenType)
  }

  const logout = () => {
    setUser(null)
    clearStoredAuthSession()
    clearApiAccessToken()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: Boolean(user),
        isAuthResolved,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return context
}
