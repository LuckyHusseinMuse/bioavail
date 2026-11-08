"use client";
// Small design-system pieces shared by every screen (shadcn-style: Radix + Tailwind + cn()).
import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { clsx, type ClassValue } from "clsx";
import { motion } from "motion/react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { twMerge } from "tailwind-merge";

export const cn = (...c: ClassValue[]) => twMerge(clsx(c));

export function Card({ className, ...p }: ComponentProps<"section">) {
  return <section className={cn("rounded-2xl border border-border bg-surface shadow-card", className)} {...p} />;
}

type BtnVariant = "primary" | "secondary" | "ghost" | "danger" | "outline";
const BTN: Record<BtnVariant, string> = {
  primary: "bg-primary text-primary-ink hover:bg-primary-strong shadow-[0_8px_18px_color-mix(in_oklab,var(--primary)_22%,transparent)]",
  secondary: "bg-surface-2 text-ink hover:bg-surface-3",
  ghost: "text-primary hover:bg-surface-2",
  danger: "bg-inhibitor text-white",
  outline: "border border-border bg-surface text-ink hover:bg-surface-2",
};
export function Button({ variant = "primary", size = "md", className, href, children, ...p }:
  ComponentProps<"button"> & { variant?: BtnVariant; size?: "sm" | "md" | "lg"; href?: string }) {
  const cls = cn(
    "inline-flex select-none items-center justify-center gap-2 rounded-[14px] font-bold transition-colors active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45",
    size === "lg" ? "min-h-[54px] px-5 text-[15px]" : size === "md" ? "min-h-11 px-4 text-sm" : "min-h-9 px-3 text-[13px]",
    BTN[variant], className,
  );
  if (href) return <Link href={href} className={cls}>{children}</Link>;
  return <button className={cls} {...p}>{children}</button>;
}

const TONE = {
  red: "bg-inhibitor/12 text-inhibitor",
  green: "bg-enhancer/14 text-enhancer",
  amber: "bg-amber/16 text-[color-mix(in_oklab,var(--amber)_70%,var(--text))]",
  blue: "bg-blue/14 text-blue",
  purple: "bg-purple/14 text-purple",
  grey: "bg-surface-2 text-muted",
} as const;
export type Tone = keyof typeof TONE;

export function Chip({ tone = "grey", icon, children, className, ...p }: ComponentProps<"span"> & { tone?: Tone; icon?: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold", TONE[tone], className)} {...p}>
      {icon}{children}
    </span>
  );
}

/** Tinted round icon badge, like the reference screenshot's coloured circles. */
export function IconBadge({ tone = "green", children, size = 40 }: { tone?: Tone; children: ReactNode; size?: number }) {
  return <span className={cn("grid shrink-0 place-items-center rounded-full", TONE[tone])} style={{ width: size, height: size }}>{children}</span>;
}

export function NotMedical({ className }: { className?: string }) {
  return <span className={cn("text-[11px] text-faint", className)}>Not medical advice</span>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="text-[11px] font-bold uppercase tracking-[0.08em] text-primary">{children}</p>;
}

/** Segmented control with an animated sliding pill (Radix ToggleGroup + motion layoutId). */
export function Segmented<T extends string>({ value, onChange, options, id, className, size = "md" }:
  { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode }[]; id: string; className?: string; size?: "sm" | "md" }) {
  return (
    <ToggleGroup.Root type="single" value={value} onValueChange={(v) => v && onChange(v as T)}
      className={cn("relative grid rounded-[14px] bg-surface-2 p-1", className)} style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      {options.map((o) => (
        <ToggleGroup.Item key={o.value} value={o.value}
          className={cn("relative z-0 rounded-[10px] font-semibold transition-colors", size === "sm" ? "h-8 text-xs" : "h-10 text-[13px]", value === o.value ? "text-ink" : "text-muted")}>
          {value === o.value && (
            <motion.span layoutId={`seg-${id}`} className="absolute inset-0 -z-10 rounded-[10px] bg-surface shadow-sm" transition={{ type: "spring", stiffness: 500, damping: 38 }} />
          )}
          {o.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}

export function Switch({ checked, onCheckedChange, label }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: string }) {
  return (
    <SwitchPrimitive.Root checked={checked} onCheckedChange={onCheckedChange} aria-label={label}
      className="relative h-7 w-12 shrink-0 rounded-full bg-surface-3 transition-colors data-[state=checked]:bg-primary">
      <SwitchPrimitive.Thumb className="block h-6 w-6 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}

export function SelectChips<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: T[]; label: string }) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-semibold">{label}</legend>
      <ToggleGroup.Root type="single" value={value} onValueChange={(v) => v && onChange(v as T)} className="flex flex-wrap gap-2">
        {options.map((o) => (
          <ToggleGroup.Item key={o} value={o}
            className="min-h-10 rounded-full border border-border bg-surface px-3.5 text-[13px] font-semibold text-muted data-[state=on]:border-primary data-[state=on]:bg-primary/10 data-[state=on]:text-primary">
            {o}
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
    </fieldset>
  );
}

export function PageTitle({ eyebrow, title, right }: { eyebrow?: string; title: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-end justify-between gap-3">
      <div>
        {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
        <h1 className="mt-1 text-[26px] font-extrabold leading-tight tracking-[-0.02em]">{title}</h1>
      </div>
      {right}
    </div>
  );
}

/** Animated donut (reference-screenshot style ring) showing a percentage. */
export function Ring({ value, max, size = 92, stroke = 9, color = "var(--primary)", children }:
  { value: number; max: number; size?: number; stroke?: number; color?: string; children?: ReactNode }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = Math.max(0.015, Math.min(1, value / max));
  return (
    <div className="relative grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - frac) }} transition={{ duration: 1.1, ease: [0.2, 0.8, 0.2, 1] }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

/** Horizontal animated bar (before/after, waterfall rows). */
export function Bar({ pct, color, delay = 0, dashed }: { pct: number; color: string; delay?: number; dashed?: boolean }) {
  return (
    <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-surface-2">
      <motion.div className="h-full rounded-full" style={{ background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 6px, transparent 6px 9px)` : color }}
        initial={{ width: 0 }} animate={{ width: `${Math.max(2, Math.min(100, pct))}%` }} transition={{ duration: 0.9, delay, ease: [0.2, 0.8, 0.2, 1] }} />
    </div>
  );
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <IconBadge tone="grey" size={64}>{icon}</IconBadge>
      <p className="mt-4 font-bold">{title}</p>
      {body && <p className="mt-1 text-sm text-muted">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
