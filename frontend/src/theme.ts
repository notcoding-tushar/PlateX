import { createTheme } from "@mui/material/styles";
export default createTheme({
  palette: {
    primary: { main: "#006e60" },
    secondary: { main: "#16424d" },
    background: { default: "#f4f6f5", paper: "#fff" },
    text: { primary: "#172d33", secondary: "#50666c" },
  },
  shape: { borderRadius: 9 },
  typography: {
    fontFamily: 'Inter, "Segoe UI", sans-serif',
    button: { textTransform: "none", fontWeight: 650 },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiTextField: { defaultProps: { size: "small", fullWidth: true } },
    MuiAccordion: { defaultProps: { disableGutters: true, elevation: 0 } },
    MuiPaper: { defaultProps: { elevation: 0 } },
  },
});
