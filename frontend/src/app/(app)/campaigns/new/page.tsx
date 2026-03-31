'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Facebook, Twitter, Instagram, Search, UserCircle, Send } from 'lucide-react';
import Link from 'next/link';
import { campaignApi, personaApi } from '@/lib/api';
import { personaStore } from '@/lib/localStore';

const platforms = [
  { id: 'facebook', name: 'Facebook', icon: Facebook, enabled: true },
  { id: 'twitter', name: 'Twitter', icon: Twitter, enabled: false, tag: '即将支持' },
  { id: 'instagram', name: 'Instagram', icon: Instagram, enabled: false, tag: '即将支持' },
];

interface PersonaOption {
  id: number;
  name: string;
  company_name: string | null;
}

export default function NewCampaignPage() {
  const router = useRouter();
  const [platform, setPlatform] = useState('facebook');
  const [keywords, setKeywords] = useState('');
  const [region, setRegion] = useState('');
  const [industry, setIndustry] = useState('');
  const [personaId, setPersonaId] = useState('');
  const [sendLimit, setSendLimit] = useState(20);
  const [maxPerHour, setMaxPerHour] = useState(10);
  const [reviewMode, setReviewMode] = useState(false);
  const [sendHourStart, setSendHourStart] = useState(9);
  const [sendHourEnd, setSendHourEnd] = useState(18);
  const [campaignName, setCampaignName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    // Load from localStorage first (instant, always available)
    const local = personaStore.list() as PersonaOption[];
    if (local.length > 0) setPersonas(local);
    // Background sync from backend
    personaApi.list()
      .then(res => {
        if (Array.isArray(res.data) && res.data.length > 0) {
          setPersonas(res.data);
        }
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError('');
    try {
      await campaignApi.create({
        name: campaignName,
        platform,
        search_keywords: keywords,
        search_region: region,
        search_industry: industry,
        persona_id: personaId ? Number(personaId) : null,
        send_limit: sendLimit,
        max_per_hour: maxPerHour,
        review_mode: reviewMode,
        send_hour_start: sendHourStart,
        send_hour_end: sendHourEnd,
      });
      router.push('/campaigns');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '创建失败，请重试';
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <Link href="/campaigns" className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f] transition-colors">
          <ArrowLeft className="h-4 w-4" />
          返回任务列表
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">新建获客任务</h1>
        <p className="mt-1 text-sm text-[#86868b]">配置并启动新的自动获客任务</p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Task Name */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">任务名称</h2>
          <input
            type="text"
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder="例如：Facebook 外贸客户开发"
            className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
          />
        </div>

        {/* Step 1: Platform */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">1</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">选择平台</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">选择目标社交媒体平台</p>
          <div className="ml-8 grid grid-cols-3 gap-3">
            {platforms.map((p) => (
              <button
                key={p.id}
                disabled={!p.enabled}
                onClick={() => p.enabled && setPlatform(p.id)}
                className={`relative flex flex-col items-center gap-2 rounded-xl border-2 p-4 transition-all ${
                  platform === p.id
                    ? 'border-[#0071e3] bg-blue-50/50'
                    : p.enabled
                    ? 'border-[#e5e5e7] hover:border-[#86868b]'
                    : 'border-[#e5e5e7] opacity-50 cursor-not-allowed'
                }`}
              >
                <p.icon className={`h-6 w-6 ${platform === p.id ? 'text-[#0071e3]' : 'text-[#86868b]'}`} />
                <span className={`text-sm font-medium ${platform === p.id ? 'text-[#0071e3]' : 'text-[#1d1d1f]'}`}>
                  {p.name}
                </span>
                {p.tag && (
                  <span className="absolute -top-2 right-2 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-[#86868b]">
                    {p.tag}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Step 2: Search Criteria */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">2</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">搜索条件</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">定义目标受众的搜索条件</p>
          <div className="ml-8 space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                <Search className="mr-1.5 inline h-4 w-4 text-[#86868b]" />
                关键词
              </label>
              <input
                type="text"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="例如：外贸, B2B, 供应商"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">国家/地区</label>
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                >
                  <option value="">全部国家/地区</option>
                  <option value="United States">美国</option>
                  <option value="Canada">加拿大</option>
                  <option value="Mexico">墨西哥</option>
                  <option value="United Kingdom">英国</option>
                  <option value="Germany">德国</option>
                  <option value="France">法国</option>
                  <option value="Italy">意大利</option>
                  <option value="Spain">西班牙</option>
                  <option value="Netherlands">荷兰</option>
                  <option value="Poland">波兰</option>
                  <option value="Sweden">瑞典</option>
                  <option value="Switzerland">瑞士</option>
                  <option value="Turkey">土耳其</option>
                  <option value="Russia">俄罗斯</option>
                  <option value="Japan">日本</option>
                  <option value="South Korea">韩国</option>
                  <option value="India">印度</option>
                  <option value="Thailand">泰国</option>
                  <option value="Vietnam">越南</option>
                  <option value="Philippines">菲律宾</option>
                  <option value="Indonesia">印度尼西亚</option>
                  <option value="Malaysia">马来西亚</option>
                  <option value="Singapore">新加坡</option>
                  <option value="Australia">澳大利亚</option>
                  <option value="New Zealand">新西兰</option>
                  <option value="Pakistan">巴基斯坦</option>
                  <option value="Bangladesh">孟加拉国</option>
                  <option value="Saudi Arabia">沙特阿拉伯</option>
                  <option value="United Arab Emirates">阿联酋</option>
                  <option value="Israel">以色列</option>
                  <option value="Egypt">埃及</option>
                  <option value="Brazil">巴西</option>
                  <option value="Argentina">阿根廷</option>
                  <option value="Colombia">哥伦比亚</option>
                  <option value="Chile">智利</option>
                  <option value="South Africa">南非</option>
                  <option value="Nigeria">尼日利亚</option>
                  <option value="Kenya">肯尼亚</option>
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">行业</label>
                <input
                  type="text"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="例如：电子商务"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Step 3: Persona */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">3</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">选择人设</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">选择 AI 销售代表的人设配置</p>
          <div className="ml-8">
            <div className="flex items-center gap-2">
              <UserCircle className="h-4 w-4 text-[#86868b]" />
              <select
                value={personaId}
                onChange={(e) => setPersonaId(e.target.value)}
                className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              >
                <option value="">选择人设...</option>
                {personas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.company_name ? ` - ${p.company_name}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <Link href="/personas/new" className="mt-2 inline-block text-xs text-[#0071e3] hover:underline">
              + 创建新人设
            </Link>
          </div>
        </div>

        {/* Step 4: Send Settings */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">4</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">发送设置</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">控制发送频率和总量</p>
          <div className="ml-8 space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">每小时最多打招呼</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={60}
                  value={maxPerHour}
                  onChange={(e) => setMaxPerHour(Number(e.target.value))}
                  className="w-32 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <span className="text-sm text-[#86868b]">人/小时</span>
              </div>
              <p className="mt-1.5 text-xs text-[#86868b]">消息会随机分散在每小时内发送，模拟真人操作节奏</p>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">总发送上限</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={sendLimit}
                  onChange={(e) => setSendLimit(Number(e.target.value))}
                  className="w-32 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <span className="text-sm text-[#86868b]">条消息</span>
              </div>
            </div>
          </div>
        </div>

        {/* Step 5: Safety Settings */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">5</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">安全设置</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">控制消息发送的安全策略</p>
          <div className="ml-8 space-y-5">
            {/* Review Mode */}
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={reviewMode}
                onChange={(e) => setReviewMode(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[#e5e5e7] text-[#0071e3] focus:ring-[#0071e3]"
              />
              <div>
                <span className="text-sm font-medium text-[#1d1d1f]">消息审核模式</span>
                <p className="text-xs text-[#86868b] mt-0.5">AI 生成消息后不会自动发送，需要你逐条审核批准后才会发出</p>
              </div>
            </label>
            {/* Time Window */}
            <div>
              <span className="text-sm font-medium text-[#1d1d1f]">发送时间窗口</span>
              <p className="text-xs text-[#86868b] mt-0.5 mb-2">只在指定时段内发送消息，避免深夜打扰</p>
              <div className="flex items-center gap-2">
                <select
                  value={sendHourStart}
                  onChange={(e) => setSendHourStart(Number(e.target.value))}
                  className="rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-3 py-2 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{String(i).padStart(2, '0')}:00</option>
                  ))}
                </select>
                <span className="text-sm text-[#86868b]">至</span>
                <select
                  value={sendHourEnd}
                  onChange={(e) => setSendHourEnd(Number(e.target.value))}
                  className="rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-3 py-2 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
                >
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{String(i).padStart(2, '0')}:00</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <Link
            href="/campaigns"
            className="rounded-full border border-[#e5e5e7] px-6 py-2.5 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-[#f5f5f7]"
          >
            取消
          </Link>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !campaignName || !keywords}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
            {isSubmitting ? '创建中...' : '创建任务'}
          </button>
        </div>
      </div>
    </div>
  );
}
