import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TextField,
  MenuItem,
} from "@mui/material";
import ExpandMore from "@mui/icons-material/ExpandMore";
import type { ReactNode } from "react";

export function Section({
  title,
  children,
  open = false,
  icon,
}: {
  title: string;
  children: ReactNode;
  open?: boolean;
  icon?: ReactNode;
}) {
  return (
    <Accordion defaultExpanded={open}>
      <AccordionSummary expandIcon={<ExpandMore />}>
        {icon}
        <strong>{title}</strong>
      </AccordionSummary>
      <AccordionDetails>
        <div className="fields">{children}</div>
      </AccordionDetails>
    </Accordion>
  );
}
export function Num({
  label,
  value,
  set,
  step = "any",
  min,
}: {
  label: string;
  value: number | null;
  set: (v: number) => void;
  step?: number | string;
  min?: number;
}) {
  return (
    <TextField
      type="number"
      label={label}
      value={value === null || Number.isNaN(value) ? "" : value}
      onChange={(e) =>
        set(e.target.value === "" ? NaN : Number(e.target.value))
      }
      slotProps={{ htmlInput: { step, min } }}
    />
  );
}
export function Select({
  label,
  value,
  set,
  items,
}: {
  label: string;
  value: string;
  set: (v: string) => void;
  items: [string, string][];
}) {
  return (
    <TextField
      select
      label={label}
      value={value}
      onChange={(e) => set(e.target.value)}
    >
      {items.map(([id, name]) => (
        <MenuItem key={id} value={id}>
          {name}
        </MenuItem>
      ))}
    </TextField>
  );
}
export function download(name: string, contents: string, type: string) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const pavementCategories: [string, string][] = [
  ["a", "A · Bituminous, granular base, granular sub-base"],
  ["b", "B · Bituminous, granular crack relief, CTB, CTSB"],
  ["c", "C · Bituminous, SAMI, CTB, CTSB"],
  ["d", "D · Bituminous, stabilised RAP, CTSB"],
  ["e", "E · Bituminous, granular crack relief, CTB, granular sub-base"],
  ["f", "F · Bituminous, granular base, CTSB"],
];
