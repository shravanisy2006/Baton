export default function Logo({ light = false }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <img src="/baton.svg" alt="" className="h-7 w-7" />
      <span className={light ? "text-lg font-semibold text-white" : "text-lg font-semibold text-slate-900"}>Baton</span>
    </span>
  );
}
