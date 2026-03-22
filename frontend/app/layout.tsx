import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SmartPantry | Cozy Pantry Assistant",
  description: "A cheerful pantry companion for image-assisted inventory tracking and recipe discovery.",
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
