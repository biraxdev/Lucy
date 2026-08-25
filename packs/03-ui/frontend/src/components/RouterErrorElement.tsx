import { useRouteError } from 'react-router-dom'
import { useEffect } from 'react'

export default function RouterErrorElement() {
  const error = useRouteError()

  useEffect(() => {
    const err = error as any
    console.error('[RouterError] type:', typeof err)
    console.error('[RouterError] value:', err)
    console.error('[RouterError] message:', err?.message || err?.statusText || 'no message')
    console.error('[RouterError] stack:', err?.stack || 'no stack')
    console.error('[RouterError] toString:', String(err))
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-100 p-6">
      <div className="card bg-base-200 max-w-lg w-full p-6 space-y-4">
        <h2 className="text-xl font-bold text-error">Router error</h2>
        <p className="text-sm text-base-content/70">
          {typeof error === 'string' ? error : (error as any)?.message || (error as any)?.statusText || 'Unexpected router error'}
        </p>
        <button className="btn btn-primary btn-sm" onClick={() => window.location.reload()}>
          Reload application
        </button>
      </div>
    </div>
  )
}
