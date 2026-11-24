import { initializeComponent } from "./api/streamlit";
import { createRoot } from "react-dom/client";
import { CssBaseline, ThemeProvider } from "@mui/material";
import theme from "./theme";
import App from "./App";
import "./style.css";
const mount = () => createRoot(document.getElementById("root")!).render(
  <ThemeProvider theme={theme}>
    <CssBaseline />
    <App />
  </ThemeProvider>,
);

if (import.meta.env.MODE === "streamlit") initializeComponent(mount);
else mount();
