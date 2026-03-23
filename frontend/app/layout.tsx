import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartPantry | AI-Assisted Kitchen Inventory",
  description:
    "Keep track of your kitchen in one place with AI-assisted pantry updates, photo review, and recipe discovery.",
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
