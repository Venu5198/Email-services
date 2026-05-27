'use client'
export function StatCard({ icon: Icon, label, value, sub, color = 'violet', trend }) {
  const colors = {
    violet: 'from-violet-500/20 to-violet-600/10 border-violet-500/20 text-violet-400',
    green:  'from-green-500/20 to-green-600/10 border-green-500/20 text-green-400',
    blue:   'from-blue-500/20 to-blue-600/10 border-blue-500/20 text-blue-400',
    orange: 'from-orange-500/20 to-orange-600/10 border-orange-500/20 text-orange-400',
    red:    'from-red-500/20 to-red-600/10 border-red-500/20 text-red-400',
    cyan:   'from-cyan-500/20 to-cyan-600/10 border-cyan-500/20 text-cyan-400',
  }
  return (
    <div className={`bg-gradient-to-br ${colors[color]} border rounded-xl p-5 flex flex-col gap-3`}>
      <div className="flex items-center justify-between">
        <span className="text-slate-400 text-sm font-medium">{label}</span>
        {Icon && <Icon size={18} className={colors[color].split(' ')[3]} />}
      </div>
      <div>
        <p className="text-white text-2xl font-bold">{value ?? '—'}</p>
        {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
      </div>
      {trend !== undefined && (
        <p className={`text-xs font-medium ${trend >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}% vs yesterday
        </p>
      )}
    </div>
  )
}

export function Badge({ children, color = 'slate' }) {
  const c = {
    green:  'bg-green-400/10 text-green-400 border-green-400/20',
    red:    'bg-red-400/10 text-red-400 border-red-400/20',
    yellow: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    blue:   'bg-blue-400/10 text-blue-400 border-blue-400/20',
    orange: 'bg-orange-400/10 text-orange-400 border-orange-400/20',
    violet: 'bg-violet-400/10 text-violet-400 border-violet-400/20',
    slate:  'bg-slate-400/10 text-slate-400 border-slate-400/20',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${c[color]}`}>
      {children}
    </span>
  )
}

export function StatusBadge({ status }) {
  const map = {
    sent: 'green', sending: 'blue', pending: 'yellow', failed: 'red',
    cancelled: 'slate', missed: 'orange', completed: 'green',
    running: 'blue', active: 'green', inactive: 'slate', bounce: 'red',
    unsubscribed: 'orange', spam_complaint: 'red',
  }
  return <Badge color={map[status?.toLowerCase()] || 'slate'}>{status}</Badge>
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}

export function EmptyState({ message = 'No data found', icon: Icon }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-slate-500">
      {Icon && <Icon size={36} className="mb-3 opacity-30" />}
      <p className="text-sm">{message}</p>
    </div>
  )
}

export function SectionTitle({ children, action }) {
  return (
    <div className="flex items-center justify-between mb-5">
      <h2 className="text-white font-semibold text-lg">{children}</h2>
      {action}
    </div>
  )
}

export function Card({ children, className = '' }) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-6 ${className}`}>
      {children}
    </div>
  )
}

export function Btn({ children, onClick, variant = 'primary', size = 'md', disabled, type = 'button', className = '' }) {
  const base = 'inline-flex items-center gap-2 font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed'
  const sizes = { sm: 'px-3 py-1.5 text-sm', md: 'px-4 py-2 text-sm', lg: 'px-5 py-2.5' }
  const variants = {
    primary:  'bg-violet-600 hover:bg-violet-500 text-white',
    secondary:'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700',
    danger:   'bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-500/30',
    ghost:    'hover:bg-slate-800 text-slate-400 hover:text-slate-200',
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}>
      {children}
    </button>
  )
}

export function Input({ label, id, ...props }) {
  return (
    <div>
      {label && <label htmlFor={id} className="block text-sm font-medium text-slate-400 mb-1.5">{label}</label>}
      <input
        id={id}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition"
        {...props}
      />
    </div>
  )
}

export function Select({ label, id, children, ...props }) {
  return (
    <div>
      {label && <label htmlFor={id} className="block text-sm font-medium text-slate-400 mb-1.5">{label}</label>}
      <select
        id={id}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition"
        {...props}
      >
        {children}
      </select>
    </div>
  )
}

export function Textarea({ label, id, ...props }) {
  return (
    <div>
      {label && <label htmlFor={id} className="block text-sm font-medium text-slate-400 mb-1.5">{label}</label>}
      <textarea
        id={id}
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition resize-y"
        {...props}
      />
    </div>
  )
}

export function Table({ headers, children, empty }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-800/50">
            {headers.map(h => (
              <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60">
          {children}
        </tbody>
      </table>
      {empty}
    </div>
  )
}
