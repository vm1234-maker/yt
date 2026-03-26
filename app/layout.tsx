import type { Metadata } from "next";
import { Geist_Mono, Syne } from "next/font/google";
import "./globals.css";
import Nav from "@/components/nav";

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "NemoClaw — YouTube Automation",
  description: "AI-powered ambient channel automation dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${syne.variable} ${geistMono.variable} h-full`}
    >
      <body className="h-full flex">
        <Nav />
        <main className="flex-1 overflow-y-auto min-h-full">
          {children}
        </main>
      </body>
    </html>
  );
}
