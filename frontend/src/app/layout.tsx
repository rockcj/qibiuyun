import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/contexts/AuthContext";
import { LocaleProvider } from "@/i18n/LocaleContext";
import { ToastProvider } from "@/contexts/ToastContext";
import AppShell from "@/components/AppShell";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SpeakUp AI · 英语口语实战教练",
  description:
    "SpeakUp AI — 多场景 AI 英语口语陪练。面试、点餐、会议，实时语音对话 + 多维纠错 + 量化评分。",
  keywords: ["AI英语陪练", "口语训练", "面试模拟", "SpeakUp AI", "实时语音"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="h-full flex flex-col">
        <AuthProvider>
          <LocaleProvider>
            <ToastProvider>
              <AppShell>{children}</AppShell>
              <LanguageSwitcher />
            </ToastProvider>
          </LocaleProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
