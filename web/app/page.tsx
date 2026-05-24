import Link from "next/link";

const floating = ["coin", "chart", "ticket", "wallet", "spark"];

export default function HomePage() {
  return (
    <main className="welcome-root">
      {floating.map((item, index) => (
        <span
          key={item}
          className={`floater floater-${index + 1}`}
          aria-hidden="true"
        >
          {item === "coin" ? "R" : item === "chart" ? "S" : item === "ticket" ? "W" : item === "wallet" ? "E" : "*"}
        </span>
      ))}

      <section className="hero-card">
        <p className="hero-tag">The Ledger For The Modern Journey</p>
        <h1>TripWise</h1>
        <p className="hero-copy">
          An elevated platform for group expenditure. Real-time balances, elegant approvals, 
          dispute resolution, and perfectly choreographed settlements.
        </p>
        <div className="hero-actions">
          <Link href="/auth/login" className="btn-primary">
            Login
          </Link>
          <Link href="/auth/register" className="btn-ghost">
            Register
          </Link>
        </div>
      </section>
    </main>
  );
}
