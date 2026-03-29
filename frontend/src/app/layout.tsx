import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'LeadFlow AI - 智能获客助手',
  description: '社交媒体智能线索获取平台',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="bg-[#f5f5f7]">
        {children}
      </body>
    </html>
  );
}
