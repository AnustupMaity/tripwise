"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PropsWithChildren, useEffect, useRef, useState } from "react";
import { resolveApiBase } from "../lib/api-base";

const API_BASE = resolveApiBase();

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/trips", label: "Trips" },
  { href: "/invite-center", label: "Invite Center" },
  { href: "/past-trips", label: "Past Trips" },
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const hideShell = pathname === "/" || pathname.startsWith("/auth/");
  const [authReady, setAuthReady] = useState(false);
  const hasValidatedForMain = useRef(false);

  useEffect(() => {
    if (hideShell) {
      setAuthReady(true);
      hasValidatedForMain.current = false;
      return;
    }

    let active = true;

    if (!hasValidatedForMain.current) {
      setAuthReady(false);
    }

    async function validateProtectedSession(isInitial: boolean) {
      const token = localStorage.getItem("tripwise_session_token") ?? "";
      if (!token) {
        localStorage.removeItem("tripwise_user_id");
        router.replace("/auth/login");
        return;
      }

      try {
        const response = await fetch(`${API_BASE}/auth/session/validate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "x-session-token": token,
          },
          body: JSON.stringify({ session_token: token }),
        });

        if (!response.ok) {
          throw new Error("session invalid");
        }

        if (active) {
          hasValidatedForMain.current = true;
          if (isInitial) {
            setAuthReady(true);
          }
        }
      } catch {
        if (active) {
          localStorage.removeItem("tripwise_session_token");
          localStorage.removeItem("tripwise_user_id");
          router.replace("/auth/login");
        }
      }
    }

    if (!hasValidatedForMain.current) {
      void validateProtectedSession(true);
    }

    const intervalId = setInterval(() => {
      void validateProtectedSession(false);
    }, 5 * 60 * 1000);

    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [hideShell, pathname, router]);

  if (hideShell) {
    return <>{children}</>;
  }

  if (!authReady) {
    return (
      <main className="screen-root">
        <section className="screen-card">
          <p className="empty-copy">Validating session...</p>
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
      </aside>
      <div className="app-main-content">{children}</div>
    </div>
  );
}
