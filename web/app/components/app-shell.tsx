"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { PropsWithChildren, useEffect, useRef, useState } from "react";
import { resolveApiBase } from "../lib/api-base";
import { DashboardIcon, TripIcon, InviteIcon, PastIcon, LogoutIcon, SparklesIcon, UserIcon } from "./icons";

const API_BASE = resolveApiBase();

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: DashboardIcon },
  { href: "/dashboard/trips", label: "Trips", icon: TripIcon },
  { href: "/dashboard/invite-center", label: "Invite Center", icon: InviteIcon },
  { href: "/dashboard/past-trips", label: "Past Trips", icon: PastIcon },
  { href: "/dashboard/profile", label: "Manage Profile", icon: UserIcon },
];

export function AppShell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  const router = useRouter();
  const hideShell = pathname === "/" || pathname.startsWith("/auth/");
  
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Initialize synchronously from localStorage so there is ZERO 0ms blocking loader after mounting!
  const [authReady, setAuthReady] = useState(() => {
    if (typeof window === "undefined") return true;
    if (pathname === "/" || pathname.startsWith("/auth/")) return true;
    return Boolean(localStorage.getItem("tripwise_session_token"));
  });

  const hasValidatedForMain = useRef(false);

  function logout() {
    localStorage.removeItem("tripwise_session_token");
    localStorage.removeItem("tripwise_user_id");
    localStorage.removeItem("tripwise_trip_currencies");
    router.push("/auth/login");
  }

  useEffect(() => {
    if (hideShell) {
      setAuthReady(true);
      hasValidatedForMain.current = false;
      return;
    }

    let active = true;

    const token = localStorage.getItem("tripwise_session_token") ?? "";
    if (!token) {
      localStorage.removeItem("tripwise_user_id");
      router.replace("/auth/login");
      return;
    }

    // If we have a token, render instantly in 0ms without waiting!
    if (!hasValidatedForMain.current) {
      setAuthReady(true);
    }

    async function validateProtectedSession() {
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
        }
      } catch {
        if (active && !hasValidatedForMain.current) {
          localStorage.removeItem("tripwise_session_token");
          localStorage.removeItem("tripwise_user_id");
          router.replace("/auth/login");
        }
      }
    }

    if (!hasValidatedForMain.current) {
      void validateProtectedSession();
    }

    const intervalId = setInterval(() => {
      void validateProtectedSession();
    }, 5 * 60 * 1000);

    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [hideShell, pathname, router]);

  if (hideShell) {
    return <>{children}</>;
  }

  if (!isMounted || !authReady) {
    return (
      <main className="screen-root">
        <section className="screen-card" style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem", padding: "3rem" }}>
          <div className="skeleton-box" style={{ width: "40px", height: "40px", borderRadius: "50%" }} />
          <p className="empty-copy" style={{ color: "#fff", fontWeight: 600 }}>Connecting to TripWise Ledger...</p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell-root">
      <aside className="app-sidebar">
        <div className="brand-block" style={{ marginBottom: "1.8rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
            <SparklesIcon size={18} style={{ color: "var(--accent)" }} />
            <p className="brand-kicker" style={{ color: "var(--accent)", fontWeight: 700, letterSpacing: "0.15em" }}>TRIPWISE</p>
          </div>
          <h2 style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0.2rem 0 0.4rem", color: "#fff" }}>The Ledger</h2>
          <p style={{ fontSize: "0.82rem", color: "#8A9BA8", lineHeight: 1.4 }}>Orchestrating shares, resolving disputes, and executing settlements.</p>
        </div>
        <nav className="side-nav">
          {navItems.map((item) => {
            const active = pathname === item.href;
            const IconComponent = item.icon;
            return (
              <Link key={item.href} href={item.href} className={`side-link ${active ? "active" : ""}`}>
                <IconComponent size={18} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="side-footer">
          <button className="tw-btn tw-btn-muted" type="button" onClick={logout} style={{ width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.6rem" }}>
            <LogoutIcon size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
      <div className="app-main-content">{children}</div>
    </div>
  );
}
