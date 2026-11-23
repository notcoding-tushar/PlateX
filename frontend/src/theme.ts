import { createTheme } from "@mui/material/styles";

export const palette = {
  plum: "#66545e",
  taupe: "#a39193",
  rose: "#aa6f73",
  peach: "#eea990",
  cream: "#f6e0b5",
  canvas: "#efe8e6",
  surface: "#f5eeec",
  drawing: "#eee4e2",
  ink: "#43343d",
};

export default createTheme({
  palette: {
    primary: { main: palette.plum, contrastText: "#fff8f0" },
    secondary: { main: palette.rose },
    background: { default: palette.canvas, paper: palette.surface },
    text: { primary: palette.ink, secondary: palette.plum },
    success: { main: palette.plum, light: palette.cream },
    warning: { main: "#79504b", light: palette.peach },
    error: { main: "#844751", light: palette.rose },
    info: { main: palette.plum, light: palette.taupe },
    divider: "#d9ccca",
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"IBM Plex Sans", "Segoe UI", sans-serif',
    button: { textTransform: "none", fontWeight: 600 },
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
          "--secondary": palette.plum,
          "--muted": palette.plum,
          "--surface": palette.surface,
          "--drawing": palette.drawing,
          "--accent": palette.plum,
          "--taupe": palette.taupe,
          "--rose": palette.rose,
          "--peach": palette.peach,
          "--cream": palette.cream,
        },
      },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
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
