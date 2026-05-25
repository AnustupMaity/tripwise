"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren } from "react";
import { useSession } from "../lib/session-context";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/trips", label: "Trips" },
  { href: "/invite-center", label: "Invite Center" },
  { href: "/past-trips", label: "Past Trips" },
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const { loading, isAuthenticated, logout } = useSession();
  const hideShell = pathname === "/" || pathname.startsWith("/auth/");

  // Public routes – no auth required, render children directly.
  if (hideShell) {
    return <>{children}</>;
  }

  // Protected route – still loading initial session validation.
  if (loading) {
    return (
      <main className="screen-root">
        <section className="screen-card">
          <p className="empty-copy">Validating session...</p>
        </section>
      </main>
    );
  }

  // Protected route – not authenticated → context already redirects,
  // but guard the UI just in case.
  if (!isAuthenticated) {
    return (
      <main className="screen-root">
        <section className="screen-card">
          <p className="empty-copy">Redirecting to login...</p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell-root">
      <aside className="app-sidebar">
        <div className="brand-block">
          <p className="brand-kicker">TRIPWISE</p>
          <h2>The Ledger</h2>
          <p>Orchestrating shares, resolving disputes, and executing exact settlements.</p>
        </div>
        <nav className="side-nav">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link key={item.href} href={item.href} className={`side-link ${active ? "active" : ""}`}>
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="side-footer">
          <button className="tw-btn tw-btn-muted" type="button" onClick={logout}>
            Logout
          </button>
        </div>
      </aside>
      <div className="app-main-content">{children}</div>
    </div>
  );
}
