import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Renderer error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          background: '#0a0a0f',
          color: '#f0f0f5',
          fontFamily: 'Inter, sans-serif',
        }}>
          <div style={{ maxWidth: 560, textAlign: 'center' }}>
            <h2 style={{ marginBottom: 12 }}>RUDRA hit a renderer error</h2>
            <p style={{ color: '#a0a0b8', marginBottom: 16 }}>
              The desktop UI could not start properly. The error has been logged to the console.
            </p>
            <pre style={{
              background: '#111118',
              padding: 12,
              borderRadius: 8,
              overflow: 'auto',
              textAlign: 'left',
              color: '#ef4444',
              fontSize: 12,
            }}>
              {this.state.error?.message || 'Unknown error'}
            </pre>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
