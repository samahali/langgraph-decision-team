import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { failed: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("React render failed", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="grid min-h-screen place-items-center p-6">
        <section className="max-w-md rounded-xl border bg-card p-6 text-center shadow-lg">
          <h1 className="font-display text-2xl font-semibold">Something went wrong</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Reload the page to restore the decision workspace.
          </p>
          <button
            className="mt-5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
            onClick={() => window.location.reload()}
            type="button"
          >
            Reload page
          </button>
        </section>
      </main>
    );
  }
}
