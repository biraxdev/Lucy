import { useEffect, useState } from 'react'
import { RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { router } from './routes'
import OnboardingWizard from './components/OnboardingWizard'
import api from './api/client'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 10_000 } },
})

function AppInner() {
  const [showWizard, setShowWizard] = useState(false)

  useEffect(() => {
    const raw = localStorage.getItem('lucy-auth')
    if (!raw) return
    try {
      const parsed = JSON.parse(raw)
      if (!parsed?.state?.accessToken) return
    } catch {
      return
    }
    api.get('/setup/status')
      .then((res) => {
        if (!res.data.setup_complete) setShowWizard(true)
      })
      .catch(() => {})
  }, [])

  return (
    <>
      <RouterProvider router={router} />
      {showWizard && <OnboardingWizard onClose={() => setShowWizard(false)} />}
    </>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInner />
    </QueryClientProvider>
  )
}
