import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "clipforge — AI gameplay clip generator",
  description: "Upload gameplay footage. Get TikTok, YouTube, and trailer clips automatically.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 antialiased">{children}</body>
    </html>
  );
}
