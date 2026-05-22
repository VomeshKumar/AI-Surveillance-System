export default function LandingPage() {
  return (
    <main className="flex-1 max-w-7xl mx-auto px-8 pt-12 pb-24 grid grid-cols-1 lg:grid-cols-2 gap-12 items-center w-full">
      <div className="flex flex-col justify-center pr-0 lg:pr-12 mt-12 lg:mt-0">
        <h1 className="text-5xl lg:text-6xl font-extrabold text-slate-900 leading-[1.1] mb-6 tracking-tight">
          Secure transit networks with precision.
        </h1>
        <p className="text-lg text-slate-600 mb-8 max-w-md leading-relaxed">
          Join leading railway authorities who rely on our centralized microservices for fast, real-time facial recognition and threat orchestration.
        </p>
        <div>
          <button className="bg-emerald-900 text-white px-8 py-3.5 rounded-full text-sm font-semibold hover:bg-emerald-800 transition-colors flex items-center gap-2">
            Launch Console <span className="text-lg leading-none">-&gt;</span>
          </button>
        </div>

        <div className="flex gap-16 mt-16">
          <div>
            <div className="text-3xl font-bold text-slate-900 mb-1">1,200+</div>
            <div className="text-sm text-slate-500 font-medium">Active Camera Nodes</div>
          </div>
          <div>
            <div className="text-3xl font-bold text-slate-900 mb-1">8.4M</div>
            <div className="text-sm text-slate-500 font-medium">Daily Face Scans</div>
          </div>
        </div>

        <div className="mt-16 flex items-center gap-6 border-t border-slate-200 pt-8">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Trusted By</span>
          <div className="flex gap-6 text-slate-400 font-semibold text-lg grayscale opacity-60">
            <span>Northern Railway</span>
            <span>Metro Auth</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6 mt-12 lg:mt-0">
        <div className="bg-[#064e3b] rounded-[2rem] p-8 text-white h-[280px] flex flex-col justify-between relative overflow-hidden shadow-lg">
          <div className="absolute top-8 right-8 w-32 h-32 bg-emerald-800/50 rounded-full blur-2xl"></div>
          <div className="flex items-center gap-2 text-emerald-300 text-sm font-semibold tracking-wide uppercase relative z-10">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
            </svg>
            Live Vision
          </div>
          <div className="text-2xl font-semibold leading-snug relative z-10 pr-4">
            Real-time OpenCV integration keeps stations safe.
          </div>
        </div>

        <div className="bg-gradient-to-br from-teal-400 to-emerald-500 rounded-[2rem] p-8 text-white h-[280px] flex flex-col justify-end relative overflow-hidden shadow-lg">
          <div className="absolute top-4 right-4 flex gap-2 opacity-50">
            <div className="w-16 h-16 bg-white rounded-full mix-blend-overlay"></div>
            <div className="w-8 h-8 bg-white rounded-full mix-blend-overlay mt-8"></div>
          </div>
          <div className="text-sm font-medium text-emerald-100 mb-2">Watchlist</div>
          <div className="text-2xl font-semibold leading-snug pr-4">
            Centralized identity tracking globally.
          </div>
        </div>

        <div className="bg-white rounded-[2rem] p-8 col-span-2 shadow-sm border border-slate-100 flex flex-col justify-between h-[320px]">
          <div>
            <div className="text-sm font-medium text-slate-500 mb-1">Active Alerts</div>
            <div className="flex items-baseline gap-2">
              <div className="text-4xl font-bold text-slate-900">84</div>
              <div className="text-sm font-semibold text-emerald-500">+ 12% Today</div>
            </div>
          </div>

          <div className="flex items-end gap-3 h-32 mt-6">
            {[20, 35, 25, 60, 45, 80, 50, 95].map((height, index) => (
              <div
                key={index}
                className="flex-1 bg-emerald-100 rounded-t-md relative group hover:bg-emerald-200 transition-colors"
                style={{ height: `${height}%` }}
              >
                {index === 7 ? (
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-xs py-1 px-2 rounded opacity-0 group-hover:opacity-100 transition-opacity">
                    Peak
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  )
}
