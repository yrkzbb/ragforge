import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./console.css";
import "./overrides.css";
import "./agent-loop.css";
import "./chat-polish.css";
import FeedbackDialogHost from "./feedback-dialog";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RAGForge — Agent 知识引擎",
  description: "可观测、可评测、持续进化的企业级 Agent RAG 工作台。",
  openGraph: {
    title: "RAGForge — Agent 知识引擎",
    description: "可观测、可评测、持续进化的企业级 Agent RAG 工作台。",
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "RAGForge — Agent 知识引擎",
    description: "可观测、可评测、持续进化的企业级 Agent RAG 工作台。",
    images: ["/og.png"],
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
        <FeedbackDialogHost />
      </body>
    </html>
  );
}
