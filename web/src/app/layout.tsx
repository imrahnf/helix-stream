import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/Providers";

export const metadata: Metadata = {
  title: "HelixStream Discovery Lab",
  description: "Distributed Protein Inference Engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-brand-950 text-white antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}