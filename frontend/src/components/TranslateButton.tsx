'use client';

import { useState } from 'react';
import { Languages, Loader2 } from 'lucide-react';
import { settingsApi } from '@/lib/api';

interface TranslateButtonProps {
  text: string;
  onTranslated: (translated: string) => void;
  targetLang?: string;
}

export default function TranslateButton({ text, onTranslated, targetLang = 'en' }: TranslateButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleTranslate = async () => {
    if (!text.trim() || loading) return;
    setLoading(true);
    try {
      const res = await settingsApi.translate(text, targetLang);
      if (res.data.success && res.data.translated) {
        onTranslated(res.data.translated);
      }
    } catch {
      // silent fail
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleTranslate}
      disabled={!text.trim() || loading}
      title="翻译为英文"
      className="inline-flex items-center justify-center rounded-lg border border-[#e5e5e7] p-2 text-[#86868b] transition-colors hover:bg-[#f5f5f7] hover:text-[#0071e3] disabled:opacity-30 disabled:cursor-not-allowed"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Languages className="h-4 w-4" />}
    </button>
  );
}
