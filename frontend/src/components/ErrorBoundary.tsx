import React from 'react';
import { Alert, Button, Group, Stack, Text, Title, Box } from '@mantine/core';
import { IconAlertCircle, IconRefresh } from '@tabler/icons-react';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: Error; onRetry: () => void }>;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({
      error,
      errorInfo,
    });

    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('ErrorBoundary caught an error:', error, errorInfo);
    }

    // Here you could also log to an error reporting service
    // logErrorToService(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        const FallbackComponent = this.props.fallback;
        return <FallbackComponent error={this.state.error!} onRetry={this.handleRetry} />;
      }

      // Default error UI
      return (
        <Box p="xl" style={{ minHeight: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Stack align="center" gap="lg" style={{ maxWidth: '500px' }}>
            <IconAlertCircle size={64} color="#fa5252" />
            <Title order={2} c="red" ta="center">
              Something went wrong
            </Title>
            <Text size="lg" c="dimmed" ta="center">
              We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
            </Text>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <Alert icon={<IconAlertCircle size={16} />} title="Error Details" color="red" variant="light">
                <Text size="sm" style={{ fontFamily: 'monospace', wordBreak: 'break-word' }}>
                  {this.state.error.message}
                </Text>
                {this.state.errorInfo && (
                  <details style={{ marginTop: '8px' }}>
                    <summary style={{ cursor: 'pointer', fontSize: '12px' }}>Stack Trace</summary>
                    <pre style={{ fontSize: '11px', marginTop: '4px', whiteSpace: 'pre-wrap' }}>
                      {this.state.errorInfo.componentStack}
                    </pre>
                  </details>
                )}
              </Alert>
            )}

            <Group gap="sm">
              <Button
                variant="light"
                color="blue"
                leftSection={<IconRefresh size={16} />}
                onClick={this.handleRetry}
              >
                Try Again
              </Button>
              <Button
                variant="outline"
                onClick={() => window.location.reload()}
              >
                Refresh Page
              </Button>
            </Group>
          </Stack>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;