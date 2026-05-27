import { Geist } from 'next/font/google'
import './globals.css'
import Sidebar from '@/components/Sidebar'
import Providers from '@/components/Providers'

const geist = Geist({ subsets: ['latin'] })

export const metadata = {
  title: 'SyncRivo Email Service',
  description: 'Centralized Email Service Admin Dashboard',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className={`${geist.className} bg-slate-950 text-white antialiased`}>
        <Providers>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 ml-60 p-8 min-h-screen">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  )
}
