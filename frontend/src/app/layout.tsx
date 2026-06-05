import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
  title: "OfferGPT - AI Real-Scene English Speaking Coach",
  description:
    "在真实场景中与 AI 角色对话：模拟面试官、餐厅服务员、会议同事……实时纠正发音/语法，生成可量化的口语成长报告。",
  keywords: ["AI英语陪练", "口语训练", "面试模拟", "OfferGPT", "实时语音"],
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
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
