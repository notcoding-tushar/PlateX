import { createTheme } from "@mui/material/styles";

export const palette = {
  teal: "#8b4c20",
  line: "#b6b4af",
  slate: "#555b5d",
  sand: "#e9d5b2",
  mint: "#eee9e1",
  canvas: "#eef1ef",
  surface: "#ffffff",
  drawing: "#f3f6f5",
  ink: "#22292c",
};

export default createTheme({
  palette: {
    primary: { main: palette.teal, contrastText: "#ffffff" },
    secondary: { main: palette.slate },
    background: { default: palette.canvas, paper: palette.surface },
    text: { primary: palette.ink, secondary: palette.slate },
    success: { main: "#356553", light: "#e4eee9" },
    warning: { main: "#80561e", light: palette.sand },
    error: { main: "#a13f39" },
    info: { main: "#3f6478" },
    divider: "#dddedb",
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily: '"Instrument Sans", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
    button: { textTransform: "none", fontWeight: 500 },
  },
  transitions: {
    easing: { easeOut: "cubic-bezier(0.22, 1, 0.36, 1)" },
    duration: { shorter: 160, short: 180, standard: 200 },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ":root": {
          "--ink": palette.ink,
          "--secondary": palette.slate,
          "--muted": palette.slate,
          "--surface": palette.surface,
          "--drawing": palette.drawing,
          "--accent": palette.teal,
          "--stroke": palette.line,
          "--warning": palette.sand,
          "--mint": palette.mint,
        },
      },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiToggleButton: { styleOverrides: { root: { textTransform: "none", fontWeight: 500 } } },
    MuiTextField: { defaultProps: { size: "small", fullWidth: true } },
    MuiAccordion: {
      defaultProps: {
        disableGutters: true,
        elevation: 0,
        slotProps: { transition: { timeout: 0 } },
      },
    },
    MuiPaper: { defaultProps: { elevation: 0 } },
  },
});
