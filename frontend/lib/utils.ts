import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes safely (shadcn/ui convention). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a Date or ISO string to "DD MMM YYYY, HH:mm". */
export function formatDateTime(value: string | Date): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

/** Convert snake_case type to a human-readable label. */
export function violationLabel(type: string): string {
  const map: Record<string, string> = {
    no_helmet: "No Helmet",
    no_vest: "No Safety Vest",
    no_gloves: "No Gloves",
    no_boots: "No Safety Boots",
    no_mask: "No Mask",
    multiple: "Multiple Violations",
  };
  return map[type] ?? type.replace(/_/g, " ");
}

/** Return a Tailwind colour class based on confidence score. */
export function confidenceColor(score: number): string {
  if (score >= 0.8) return "text-red-500";
  if (score >= 0.6) return "text-orange-400";
  return "text-yellow-400";
}
