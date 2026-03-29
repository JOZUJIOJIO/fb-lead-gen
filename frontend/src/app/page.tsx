'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { settingsApi, authApi } from '@/lib/api';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    checkSetup();
  }, []);

  async function checkSetup() {
    try {
      // Try to login with default credentials and check if API key is configured
      const token = localStorage.getItem('auth_token');
      if (!token) {
        // Try default login
        const res = await authApi.login('admin@leadflow.ai', 'admin123456');
        localStorage.setItem('auth_token', res.data.access_token);
      }

      const settings = await settingsApi.get();
      const s = settings.data;

      // Check if any API key is set
      const hasKey =
        s.openai_api_key_set || s.anthropic_api_key_set || s.kimi_api_key_set;

      if (hasKey) {
        router.replace('/dashboard');
      } else {
        router.replace('/setup');
      }
    } catch {
      // Backend not ready or first time — go to setup
      router.replace('/setup');
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f5f7] flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">LeadFlow AI</h1>
        <p className="text-gray-400 text-sm">加载中...</p>
      </div>
    </div>
  );
}
