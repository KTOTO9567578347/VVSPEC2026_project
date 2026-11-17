import { Component, type ReactNode } from 'react';
import { ru } from '../lib/ru';
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="fatal">
        <h1>{ru.crash}</h1>
        <button onClick={() => location.reload()}>{ru.reload}</button>
      </main>
    ) : (
      this.props.children
    );
  }
}
