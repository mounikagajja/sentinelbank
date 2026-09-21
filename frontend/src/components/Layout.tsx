import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm ${
    isActive ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
  }`;

export default function Layout() {
  const { user, signOut } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
          <span className="font-semibold">SentinelBank</span>
          <nav className="flex gap-1">
            <NavLink to="/flags" className={linkClass}>
              Flag queue
            </NavLink>
            <NavLink to="/live" className={linkClass}>
              Live
            </NavLink>
            <NavLink to="/assistant" className={linkClass}>
              Assistant
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-400">
              {user?.username}
              <span className="ml-2 rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                {user?.role}
              </span>
            </span>
            <button onClick={signOut} className="text-slate-400 hover:text-slate-200">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}