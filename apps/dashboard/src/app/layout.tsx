import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RIRI · XAUUSD Trading Intelligence",
  description: "Live market intelligence, execution state, and permanent trade history for RIRI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="id"
      className="h-full"
    >
      <body>{children}</body>
    </html>
  );
}
