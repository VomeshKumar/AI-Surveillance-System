import {
  Activity,
  AlertTriangle,
  BarChart3,
  Camera,
  FileText,
  Shield,
  LayoutDashboard,
  MapPin,
  Settings,
  Users,
} from 'lucide-react'
import { type LucideIcon } from 'lucide-react'
import type { UserRole } from '../context/AuthContext'

export interface DashboardRouteItem {
  label: string
  path: string
  icon: LucideIcon
  roles: UserRole[]
}

export const dashboardRoutes: DashboardRouteItem[] = [
  {
    label: 'Dashboard',
    path: '/dashboard',
    icon: LayoutDashboard,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Alerts',
    path: '/alerts',
    icon: AlertTriangle,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Track',
    path: '/track',
    icon: MapPin,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Cameras',
    path: '/cameras',
    icon: Camera,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Manage Users',
    path: '/manage-users',
    icon: Users,
    roles: ['admin'],
  },
  {
    label: 'Face Data',
    path: '/face-data',
    icon: Shield,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Analysis',
    path: '/analytics',
    icon: BarChart3,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Reports',
    path: '/reports',
    icon: FileText,
    roles: ['admin', 'security_officer'],
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: Settings,
    roles: ['admin', 'security_officer'],
  },
]

export function getAccessibleDashboardRoutes(role: UserRole) {
  return dashboardRoutes.filter((route) => route.roles.includes(role))
}

export function getDefaultRouteForRole(role: UserRole) {
  return getAccessibleDashboardRoutes(role)[0]?.path ?? '/dashboard'
}

export const overviewMetrics = [
  { label: 'Active Alerts', value: '84', icon: AlertTriangle },
  { label: 'Online Cameras', value: '312', icon: Camera },
  { label: 'Resolved Cases', value: '126', icon: Activity },
  { label: 'Face Data Records', value: '19', icon: Shield },
]
