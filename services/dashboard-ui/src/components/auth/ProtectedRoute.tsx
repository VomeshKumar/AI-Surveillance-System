import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth, type UserRole } from '../../context/AuthContext'
import { getDefaultRouteForRole } from '../../routes/routeConfig'

interface ProtectedRouteProps {
  allowedRoles?: UserRole[]
}

export default function ProtectedRoute({ allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isAuthResolved, user } = useAuth()
  const location = useLocation()

  if (!isAuthResolved) {
    return null
  }

  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />
  }

  return <Outlet />
}
