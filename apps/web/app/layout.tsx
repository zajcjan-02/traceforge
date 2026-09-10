import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "TraceForge",
  description: "Trace investigation",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="app-header">
          <a className="brand" href="/traces">TraceForge</a>
          <nav><a href="/traces">Traces</a></nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
