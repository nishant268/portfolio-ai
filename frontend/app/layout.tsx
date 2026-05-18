import type { Metadata } from "next";
import "./globals.css";
import { NotificationProvider } from "@/components/ui/Notifications";

export const metadata: Metadata = {
  title: "Portfolio AI — NSE Dashboard",
  description: "AI-powered NSE portfolio evaluator with real-time data",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full">
        <NotificationProvider>
          {children}
        </NotificationProvider>
      </body>
    </html>
  );
}
