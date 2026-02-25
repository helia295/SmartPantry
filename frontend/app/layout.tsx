import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartPantry",
  description: "AI-powered kitchen inventory and recipe recommendations",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
