import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="text-5xl font-semibold text-slate-300">404</p>
      <p className="text-slate-600">This page doesn't exist.</p>
      <Link to="/" className="font-medium text-brand-700 hover:underline">
        Go to the home page
      </Link>
    </div>
  );
}
