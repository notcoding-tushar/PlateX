import { Component, type ErrorInfo, type ReactNode } from "react";
import { Alert, Button } from "@mui/material";

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Workbench rendering failed", error, info);
  }

  render() {
    if (this.state.failed) {
      return <Alert severity="error" action={<Button onClick={() => this.setState({ failed: false })}>Retry</Button>}>
        This section could not be displayed. Retry, or reload the page if the problem continues.
      </Alert>;
    }
    return this.props.children;
  }
}
