import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck, ShieldQuestion, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useEffect } from "react";
import type { Confidence } from "../lib/types";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 shadow-sm",
  ghost: "text-slate-600 hover:bg-slate-100",
  danger: "bg-white text-rose-700 border border-rose-200 hover:bg-rose-50",
  success: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3.5 py-2 text-sm",
        VARIANTS[variant],
        className,
      )}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>{children}</div>;
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-slate-500 justify-center">
      <Loader2 className="h-4 w-4 animate-spin" /> {label}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="font-medium underline">
          Retry
        </button>
      )}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn" | "ok"; children: ReactNode }) {
  const t = {
    info: "border-brand-100 bg-brand-50 text-brand-700",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
  }[tone];
  return <div className={cx("rounded-lg border p-3 text-sm", t)}>{children}</div>;
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      {icon && <div className="mb-3 text-slate-400">{icon}</div>}
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Pill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", className)}>
      {children}
    </span>
  );
}

const CONF: Record<Confidence, { label: string; cls: string; hint: string }> = {
  verified: { label: "Verified", cls: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200", hint: "Quote found and it supports the claim" },
  corroborated: { label: "Corroborated", cls: "bg-emerald-600 text-white", hint: "Supported by two or more independent sources" },
  weak: { label: "Weak", cls: "bg-amber-50 text-amber-800 ring-1 ring-amber-200", hint: "Quote only partly supports the claim" },
  conflicting: { label: "Conflicting", cls: "bg-orange-100 text-orange-800 ring-1 ring-orange-200", hint: "Another source says something different" },
  unverified: { label: "Unverified", cls: "bg-rose-50 text-rose-700 ring-1 ring-rose-200", hint: "Failed the quote or support check" },
  leaver_attested: { label: "Leaver-attested", cls: "bg-violet-50 text-violet-700 ring-1 ring-violet-200", hint: "From the departing member's interview answer" },
  reviewer_asserted: { label: "Reviewer-asserted", cls: "bg-sky-50 text-sky-700 ring-1 ring-sky-200", hint: "Added or changed by the reviewer beyond the evidence" },
  unknown: { label: "Unknown", cls: "bg-slate-100 text-slate-600 ring-1 ring-slate-200", hint: "Not found in authorised sources" },
};

export function ConfidenceBadge({ value }: { value: Confidence }) {
  const c = CONF[value] ?? CONF.unknown;
  const Icon = value === "verified" || value === "corroborated" ? ShieldCheck : value === "unverified" || value === "unknown" ? ShieldQuestion : null;
  return (
    <Pill className={c.cls}>
      <span title={c.hint} className="inline-flex items-center gap-1">
        {Icon && <Icon className="h-3 w-3" />}
        {c.label}
      </span>
    </Pill>
  );
}

export function LabelBadge({ label }: { label: string }) {
  const cls =
    label === "Restricted"
      ? "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
      : label === "Leads"
        ? "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
        : "bg-slate-100 text-slate-600 ring-1 ring-slate-200";
  return <Pill className={cls}>{label}</Pill>;
}

export function TypeBadge({ type }: { type: string }) {
  return <Pill className="bg-slate-100 text-slate-700 capitalize">{type.replace(/_/g, " ")}</Pill>;
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-10" onClick={onClose}>
      <div
        className={cx("fade-in w-full rounded-xl bg-white shadow-xl", wide ? "max-w-4xl" : "max-w-lg")}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="no-print fixed inset-0 z-50 flex justify-end bg-slate-900/30" onClick={onClose}>
      <aside
        className="drawer-in flex h-full w-full max-w-xl flex-col bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="rounded p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  );
}

export function Highlighted({ text, start, end }: { text: string; start: number | null; end: number | null }) {
  if (start == null || end == null || start < 0 || end > text.length) return <span>{text}</span>;
  return (
    <span>
      {text.slice(0, start)}
      <mark className="hl">{text.slice(start, end)}</mark>
      {text.slice(end)}
    </span>
  );
}

export function Stat({ label, value, tone }: { label: string; value: number | string; tone?: "ok" | "warn" | "bad" }) {
  const c = tone === "ok" ? "text-emerald-600" : tone === "warn" ? "text-amber-600" : tone === "bad" ? "text-rose-600" : "text-slate-900";
  return (
    <Card className="p-4">
      <div className={cx("text-2xl font-semibold", c)}>{value}</div>
      <div className="mt-0.5 text-xs text-slate-500">{label}</div>
    </Card>
  );
}

export function Check({ ok }: { ok: boolean }) {
  return ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <AlertTriangle className="h-4 w-4 text-rose-500" />;
}

export const select =
  "rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
export const input = select + " w-full";
