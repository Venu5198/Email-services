'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Send, Layers, FileText, Clock,
  Users, Inbox, ShieldOff, BarChart2, Key, Zap, BookUser
} from 'lucide-react'

const nav = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/compose', label: 'Compose', icon: Send },
  { href: '/campaigns', label: 'Campaigns', icon: Layers },
  { href: '/contacts',  label: 'Contacts',  icon: BookUser },
  { href: '/templates', label: 'Templates', icon: FileText },
  { href: '/scheduler', label: 'Scheduler', icon: Clock },
  { href: '/sender-pool', label: 'Sender Pool', icon: Users },
  { href: '/inbox-monitor', label: 'Inbox Monitor', icon: Inbox },
  { href: '/suppressions', label: 'Suppressions', icon: ShieldOff },
  { href: '/analytics', label: 'Analytics', icon: BarChart2 },
  { href: '/api-keys', label: 'API Keys', icon: Key },
]

export default function Sidebar() {
  const path = usePathname()
  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-slate-900 border-r border-slate-800 flex flex-col z-30">
      {/* Logo */}
      <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
          <Zap size={16} className="text-white" />
        </div>
        <div>
          <p className="text-white font-semibold text-sm leading-none">SyncRivo</p>
          <p className="text-slate-500 text-xs mt-0.5">Email Service</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? path === '/' : path.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                active
                  ? 'bg-violet-600/20 text-violet-300 border border-violet-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              <Icon size={16} className={active ? 'text-violet-400' : ''} />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-800">
        <p className="text-slate-600 text-xs text-center">v2.0 — Phase 6</p>
      </div>
    </aside>
  )
}
