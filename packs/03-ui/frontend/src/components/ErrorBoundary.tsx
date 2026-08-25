import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (!this.state.hasError) return this.props.children

    if (this.props.fallback) return this.props.fallback

    return (
      <div className="min-h-screen flex items-center justify-center bg-base-100 p-6">
        <div className="card bg-base-200 max-w-lg w-full p-6 space-y-4">
          <h2 className="text-xl font-bold text-error">Something went wrong</h2>
          <p className="text-sm text-base-content/70">
            {this.state.error?.message || 'Unexpected application error'}
          </p>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => window.location.reload()}
          >
            Reload application
          </button>
        </div>
      </div>
    )
  }
}
