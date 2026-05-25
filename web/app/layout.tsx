import "./globals.css";
import type { Metadata } from "next";
import { Playfair_Display, Epilogue } from "next/font/google";
import { AppShell } from "./components/app-shell";
import { SessionProvider } from "./lib/session-context";

const displayFont = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  style: ["normal", "italic"],
  weight: ["400", "500", "600", "700"],
});
const epilogue = Epilogue({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "TripWise",
  description: "Group expense planning and settlement",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${displayFont.variable} ${epilogue.variable}`}>
      <body>
        <SessionProvider>
          <AppShell>{children}</AppShell>
        </SessionProvider>
      </body>
    </html>
  );
}
