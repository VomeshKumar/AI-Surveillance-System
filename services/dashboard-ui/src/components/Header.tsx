import React, { useState } from 'react';
import { LogOut, Moon, Sun, X, Power, RotateCw } from 'lucide-react';
import aiflowLogo from '../assets/aiflow-logo.png';

interface HeaderProps {
  logoText?: string;
  navItems?: Array<{ label: string; href: string }>;
  logoIcon?: React.ReactNode;
  onLogoClick?: () => void;
  onNavClick?: (href: string) => void;
  onToggleTheme?: () => void;
  userName?: string;
  onLogout?: () => void;
  onShutdown?: () => void;
  onRestart?: () => void;
  theme?: 'light' | 'dark';
}

export const Header: React.FC<HeaderProps> = ({
  logoText = "AI Surveillance System",
  navItems = [
    { label: "Home", href: "#home" },
    { label: "About Us", href: "#about" },
    { label: "Features", href: "#features" },
    { label: "Dashboard", href: "#dashboard" },
    { label: "Login", href: "#login" },
  ],
  logoIcon,
  onLogoClick,
  onNavClick,
  onToggleTheme,
  userName,
  onLogout,
  onShutdown,
  onRestart,
  theme = 'light',
}) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const isDark = theme === 'dark';
  const hasNavItems = navItems.length > 0;
  const hasAuthActions = Boolean(userName && onLogout);

  const handleNavClick = (href: string) => {
    onNavClick?.(href);
    setIsMenuOpen(false);
  };

  return (
    <header
      className={`shrink-0 shadow-lg transition-colors ${
        isDark
          ? 'bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900'
          : 'bg-gradient-to-r from-teal-700 to-teal-800'
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-3 py-3 sm:px-6 sm:py-4 lg:px-8">
        <button
          type="button"
          onClick={onLogoClick}
          className="flex min-w-0 items-center"
          aria-label="Go to landing page"
        >
          {logoIcon || (
            <img
              src={aiflowLogo}
              alt={logoText}
              className="h-10 w-auto rounded-lg object-contain sm:h-12 lg:h-14"
            />
          )}
        </button>

        <div className="hidden items-center gap-4 md:flex">
          {hasNavItems ? (
            <nav className="flex items-center gap-8">
              {navItems.map((item) => (
                <a
                  key={item.label}
                  href={item.href}
                  onClick={(e) => {
                    e.preventDefault();
                    handleNavClick(item.href);
                  }}
                  className={`text-sm font-medium transition-colors duration-200 ${
                    isDark
                      ? 'text-slate-300 hover:text-white'
                      : 'text-orange-300 hover:text-orange-200'
                  }`}
                >
                  {item.label}
                </a>
              ))}
            </nav>
          ) : null}
          <button
            type="button"
            onClick={onToggleTheme}
            className={`rounded-full border p-2 transition-colors ${
              isDark
                ? 'border-slate-600 bg-slate-800 text-amber-300 hover:bg-slate-700'
                : 'border-white/40 bg-white/10 text-white hover:bg-white/20'
            }`}
            aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          {hasAuthActions ? (
            <>
              <span className={`text-sm font-semibold ${isDark ? 'text-slate-100' : 'text-white'}`}>
                {userName}
              </span>
              {onRestart && (
                <button
                  type="button"
                  onClick={onRestart}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                    isDark
                      ? 'border-yellow-900 bg-yellow-950/50 text-yellow-400 hover:bg-yellow-900/50 hover:text-yellow-300'
                      : 'border-yellow-300/40 bg-yellow-500/20 text-yellow-100 hover:bg-yellow-500/40'
                  }`}
                  title="Restart System"
                >
                  <RotateCw className="h-4 w-4" />
                  Restart
                </button>
              )}
              {onShutdown && (
                <button
                  type="button"
                  onClick={onShutdown}
                  className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                    isDark
                      ? 'border-red-900 bg-red-950/50 text-red-400 hover:bg-red-900/50 hover:text-red-300'
                      : 'border-red-300/40 bg-red-500/20 text-red-100 hover:bg-red-500/40'
                  }`}
                  title="Shutdown System"
                >
                  <Power className="h-4 w-4" />
                  Shutdown
                </button>
              )}
              <button
                type="button"
                onClick={onLogout}
                className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-colors ${
                  isDark
                    ? 'border-slate-600 bg-slate-800 text-slate-100 hover:bg-slate-700'
                    : 'border-white/40 bg-white/10 text-white hover:bg-white/20'
                }`}
              >
                <LogOut className="h-4 w-4" />
                Logout
              </button>
            </>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2 md:hidden">
          <button
            type="button"
            onClick={onToggleTheme}
            className={`rounded-full border p-2 transition-colors ${
              isDark
                ? 'border-slate-600 bg-slate-800 text-amber-300 hover:bg-slate-700'
                : 'border-white/40 bg-white/10 text-white hover:bg-white/20'
            }`}
            aria-label={`Switch to ${isDark ? 'light' : 'dark'} theme`}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          {hasAuthActions ? (
            <>
              <span className={`max-w-[84px] truncate text-sm font-semibold sm:max-w-[120px] ${isDark ? 'text-slate-100' : 'text-white'}`}>
                {userName}
              </span>
              <button
                type="button"
                onClick={onLogout}
                className={`rounded-full border p-2 transition-colors ${
                  isDark
                    ? 'border-slate-600 bg-slate-800 text-slate-100 hover:bg-slate-700'
                    : 'border-white/40 bg-white/10 text-white hover:bg-white/20'
                }`}
                aria-label="Logout"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </>
          ) : null}
          {hasNavItems ? (
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className={`rounded-lg p-2 transition-colors ${
                isDark ? 'text-slate-100 hover:bg-slate-700' : 'text-white hover:bg-teal-600'
              }`}
              aria-label="Toggle menu"
            >
              {isMenuOpen ? (
                <X className="h-6 w-6" />
              ) : (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          ) : null}
        </div>
      </div>

      {isMenuOpen && hasNavItems && (
        <div
          className={`animate-in fade-in slide-in-from-top-2 md:hidden ${
            isDark ? 'border-t border-slate-700 bg-slate-900' : 'border-t border-teal-600 bg-teal-800'
          }`}
        >
          <nav className="flex flex-col space-y-2 p-4">
            {navItems.map((item) => (
              <a
                key={item.label}
                href={item.href}
                onClick={(e) => {
                  e.preventDefault();
                  handleNavClick(item.href);
                }}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  isDark
                    ? 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    : 'text-orange-300 hover:bg-teal-700 hover:text-orange-200'
                }`}
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
};

export default Header;
