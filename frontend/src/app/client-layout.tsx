"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/components/Toast";
import Sidebar from "@/components/Sidebar";

const publicPaths = ["/login", "/register"];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = publicPaths.includes(pathname);

  return (
    <AuthProvider>
      <ToastProvider>
        {isPublic ? (
          <main>{children}</main>
        ) : (
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 ml-64">
              <div className="p-6 lg:p-8 max-w-7xl">{children}</div>
            </main>
          </div>
        )}
      </ToastProvider>
    </AuthProvider>
  );
}
