'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export default function Providers({ children }) {
  const [qc] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: 1, staleTime: 30000 } }
  }))
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}
