import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, Lock, Mail, Shield, User, UserCircle2 } from 'lucide-react'
import { Navigate, useNavigate } from 'react-router-dom'
import { loginWithBackend, requestPasswordResetOtp, resetPasswordWithOtp } from '../api/auth'
import { useAuth, type UserRole } from '../context/AuthContext'
import { getDefaultRouteForRole } from '../routes/routeConfig'

const roles: Array<{ id: UserRole; label: string }> = [
  { id: 'admin', label: 'Admin' },
  { id: 'security_officer', label: 'Operator' },
]

interface LoginPageProps {
  theme?: 'light' | 'dark'
}

export default function LoginPage({ theme = 'light' }: LoginPageProps) {
  const { user, isAuthenticated, isAuthResolved, login } = useAuth()
  const navigate = useNavigate()
  const [selectedRole, setSelectedRole] = useState<UserRole>('security_officer')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isForgotPasswordMode, setIsForgotPasswordMode] = useState(false)
  const [resetEmail, setResetEmail] = useState('')
  const [resetOtp, setResetOtp] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [forgotPasswordMessage, setForgotPasswordMessage] = useState('')
  const [forgotPasswordError, setForgotPasswordError] = useState('')
  const [isSendingOtp, setIsSendingOtp] = useState(false)
  const [isResettingPassword, setIsResettingPassword] = useState(false)
  const isDark = theme === 'dark'

  if (!isAuthResolved) {
    return null
  }

  if (isAuthenticated && user) {
    return <Navigate to={getDefaultRouteForRole(user.role)} replace />
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setErrorMessage('')
    setInfoMessage('')

    const trimmedUserId = userId.trim()
    if (!trimmedUserId || !password) {
      setErrorMessage('User ID and password are required')
      return
    }

    setIsSubmitting(true)

    try {
      const authenticatedUser = await loginWithBackend(trimmedUserId, password)

      if (authenticatedUser.role !== selectedRole) {
        setErrorMessage('Selected role does not match this account')
        return
      }

      login(authenticatedUser, rememberMe)
      setPassword('')
      navigate(getDefaultRouteForRole(authenticatedUser.role), { replace: true })
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unable to sign in right now')
    } finally {
      setIsSubmitting(false)
    }
  }

  const resetForgotPasswordFeedback = () => {
    setForgotPasswordMessage('')
    setForgotPasswordError('')
  }

  const handleSendOtp = async () => {
    const normalizedEmail = resetEmail.trim().toLowerCase()
    resetForgotPasswordFeedback()
    setInfoMessage('')

    if (!normalizedEmail) {
      setForgotPasswordError('Registered email is required')
      return
    }

    setIsSendingOtp(true)

    try {
      const message = await requestPasswordResetOtp({ email: normalizedEmail })
      setResetEmail(normalizedEmail)
      setForgotPasswordMessage(message)
      window.alert(message)
    } catch (error) {
      setForgotPasswordError(error instanceof Error ? error.message : 'Unable to send OTP right now')
    } finally {
      setIsSendingOtp(false)
    }
  }

  const handleResetPassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    resetForgotPasswordFeedback()

    const normalizedEmail = resetEmail.trim().toLowerCase()

    if (!normalizedEmail || !resetOtp.trim() || !newPassword || !confirmPassword) {
      setForgotPasswordError('Email, OTP, new password and confirm password are required')
      return
    }

    if (newPassword !== confirmPassword) {
      setForgotPasswordError('New password and confirm password do not match')
      return
    }

    setIsResettingPassword(true)

    try {
      const message = await resetPasswordWithOtp({
        email: normalizedEmail,
        otp: resetOtp.trim(),
        newPassword,
        confirmPassword,
      })

      setInfoMessage(message)
      setResetOtp('')
      setNewPassword('')
      setConfirmPassword('')
      setIsForgotPasswordMode(false)
      window.alert(message)
    } catch (error) {
      setForgotPasswordError(error instanceof Error ? error.message : 'Unable to reset password right now')
    } finally {
      setIsResettingPassword(false)
    }
  }

  const handleToggleForgotPasswordMode = () => {
    setIsForgotPasswordMode((current) => !current)
    setErrorMessage('')
    resetForgotPasswordFeedback()
  }

  return (
    <main
      className={`flex w-full flex-grow items-center justify-center p-6 transition-colors ${
        isDark ? 'bg-slate-950' : 'bg-[#f8faf9]'
      }`}
    >
      <div
        className={`w-full max-w-md rounded-lg p-8 shadow-[0_3px_10px_rgba(15,23,42,0.5)] transition-colors sm:p-10 ${
          isDark ? 'border border-slate-700 bg-slate-900' : 'border border-slate-300 bg-white'
        }`}
      >
        <div className="mb-8 flex items-center gap-3">
          <div
            className={`flex h-12 w-12 items-center justify-center rounded-2xl shadow-md ${
              isDark ? 'bg-cyan-400 text-slate-950' : 'bg-emerald-900 text-white'
            }`}
          >
            <Shield className="h-6 w-6" />
          </div>
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? 'text-cyan-300' : 'text-emerald-700'}`}>
              Secure Access
            </p>
            <h1 className={`text-3xl font-bold tracking-tight ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>Sign in</h1>
          </div>
        </div>

        <div className={`mb-8 rounded-2xl p-1.5 ${isDark ? 'bg-slate-800' : 'bg-slate-100'}`}>
          <div className="grid grid-cols-2 gap-2">
            {roles.map((role) => {
              const isActive = selectedRole === role.id

              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => setSelectedRole(role.id)}
                  className={`rounded-xl px-4 py-3 text-left transition-colors ${
                    isActive
                      ? isDark
                        ? 'bg-slate-700 text-slate-100 shadow-sm ring-1 ring-slate-600'
                        : 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200'
                      : isDark
                        ? 'text-slate-400 hover:text-slate-200'
                        : 'text-slate-500 hover:text-slate-700'
                  }`}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    {role.id === 'admin' ? <Shield className="h-4 w-4" /> : <User className="h-4 w-4" />}
                    {role.label}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        {!isForgotPasswordMode ? (
          <form className="space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>
                {selectedRole === 'admin' ? 'Admin ID' : 'Operator ID'}
              </span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <UserCircle2 className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="text"
                  value={userId}
                  onChange={(event) => setUserId(event.target.value)}
                  placeholder={selectedRole === 'admin' ? 'Enter admin ID' : 'Enter operator ID'}
                  disabled={isSubmitting}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </div>
            </label>

            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Password</span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <Lock className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  disabled={isSubmitting}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  className={`transition-colors ${isDark ? 'text-slate-500 hover:text-slate-200' : 'text-slate-400 hover:text-slate-700'}`}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            </label>

            <div className="flex items-center justify-between text-sm">
              <label className={`flex items-center gap-3 ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(event) => setRememberMe(event.target.checked)}
                  className={`h-4 w-4 rounded ${
                    isDark
                      ? 'border-slate-600 bg-slate-800 text-cyan-400 focus:ring-cyan-400'
                      : 'border-slate-300 bg-white text-emerald-700 focus:ring-emerald-500'
                  }`}
                />
                Remember me
              </label>
              <button
                type="button"
                onClick={handleToggleForgotPasswordMode}
                className={`font-medium transition-colors ${
                  isDark ? 'text-cyan-300 hover:text-cyan-200' : 'text-emerald-700 hover:text-emerald-900'
                }`}
              >
                Forgot password?
              </button>
            </div>

            {errorMessage ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark ? 'border-red-500/30 bg-red-500/10 text-red-200' : 'border-red-200 bg-red-50 text-red-700'
                }`}
              >
                {errorMessage}
              </div>
            ) : null}

            {infoMessage ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                }`}
              >
                {infoMessage}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className={`w-full rounded-2xl px-5 py-4 text-sm font-semibold transition-colors ${
                isDark
                  ? 'bg-cyan-400 text-slate-950 hover:bg-cyan-300'
                  : 'bg-emerald-900 text-white hover:bg-emerald-800'
              } ${isSubmitting ? 'cursor-not-allowed opacity-80' : ''}`}
            >
              {isSubmitting
                ? 'Signing in...'
                : selectedRole === 'admin'
                  ? 'Sign in as Admin'
                  : 'Sign in as Operator'}
            </button>
          </form>
        ) : (
          <form className="space-y-5" onSubmit={handleResetPassword}>
            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Registered email</span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <Mail className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="email"
                  value={resetEmail}
                  onChange={(event) => setResetEmail(event.target.value)}
                  placeholder="Enter registered email"
                  disabled={isSendingOtp || isResettingPassword}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </div>
            </label>

            <button
              type="button"
              onClick={handleSendOtp}
              disabled={isSendingOtp || isResettingPassword}
              className={`w-full rounded-2xl px-5 py-4 text-sm font-semibold transition-colors ${
                isDark
                  ? 'bg-slate-100 text-slate-950 hover:bg-white'
                  : 'bg-slate-900 text-white hover:bg-slate-800'
              } ${(isSendingOtp || isResettingPassword) ? 'cursor-not-allowed opacity-80' : ''}`}
            >
              {isSendingOtp ? 'Sending OTP...' : 'Send OTP'}
            </button>

            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>OTP</span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <Shield className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="text"
                  value={resetOtp}
                  onChange={(event) => setResetOtp(event.target.value)}
                  placeholder="Enter OTP"
                  disabled={isResettingPassword}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </div>
            </label>

            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>New password</span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <Lock className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="Enter new password"
                  disabled={isResettingPassword}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </div>
            </label>

            <label className="block">
              <span className={`mb-2 block text-sm font-medium ${isDark ? 'text-slate-200' : 'text-slate-700'}`}>Confirm password</span>
              <div
                className={`flex items-center gap-3 rounded-2xl border px-4 transition-colors ${
                  isDark
                    ? 'border-slate-700 bg-slate-800 focus-within:border-cyan-400'
                    : 'border-slate-200 bg-slate-50 focus-within:border-emerald-400 focus-within:bg-white'
                }`}
              >
                <Lock className={`h-5 w-5 ${isDark ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm new password"
                  disabled={isResettingPassword}
                  className={`w-full bg-transparent py-4 text-sm outline-none ${
                    isDark ? 'text-slate-100 placeholder:text-slate-500' : 'text-slate-900 placeholder:text-slate-400'
                  }`}
                />
              </div>
            </label>

            {forgotPasswordError ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark ? 'border-red-500/30 bg-red-500/10 text-red-200' : 'border-red-200 bg-red-50 text-red-700'
                }`}
              >
                {forgotPasswordError}
              </div>
            ) : null}

            {forgotPasswordMessage ? (
              <div
                className={`rounded-2xl border px-4 py-3 text-sm ${
                  isDark ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                }`}
              >
                {forgotPasswordMessage}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={isResettingPassword}
              className={`w-full rounded-2xl px-5 py-4 text-sm font-semibold transition-colors ${
                isDark
                  ? 'bg-cyan-400 text-slate-950 hover:bg-cyan-300'
                  : 'bg-emerald-900 text-white hover:bg-emerald-800'
              } ${isResettingPassword ? 'cursor-not-allowed opacity-80' : ''}`}
            >
              {isResettingPassword ? 'Updating password...' : 'Update password'}
            </button>

            <button
              type="button"
              onClick={handleToggleForgotPasswordMode}
              className={`w-full text-sm font-medium transition-colors ${
                isDark ? 'text-slate-300 hover:text-slate-100' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Back to sign in
            </button>
          </form>
        )}
      </div>
    </main>
  )
}
