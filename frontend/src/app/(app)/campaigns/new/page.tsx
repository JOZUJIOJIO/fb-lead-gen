'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Facebook, Twitter, Instagram, Search, UserCircle, Send } from 'lucide-react';
import Link from 'next/link';

const platforms = [
  { id: 'facebook', name: 'Facebook', icon: Facebook, enabled: true },
  { id: 'twitter', name: 'Twitter', icon: Twitter, enabled: false, tag: '即将支持' },
  { id: 'instagram', name: 'Instagram', icon: Instagram, enabled: false, tag: '即将支持' },
];

const mockPersonas = [
  { id: '1', name: '专业商务顾问', company: 'TechBridge' },
  { id: '2', name: '友好销售代表', company: 'LeadFlow' },
  { id: '3', name: '行业专家', company: 'AI Solutions' },
];

export default function NewCampaignPage() {
  const router = useRouter();
  const [platform, setPlatform] = useState('facebook');
  const [keywords, setKeywords] = useState('');
  const [region, setRegion] = useState('');
  const [industry, setIndustry] = useState('');
  const [personaId, setPersonaId] = useState('');
  const [sendLimit, setSendLimit] = useState(20);
  const [campaignName, setCampaignName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      // TODO: Call API
      // await campaignApi.create({ name: campaignName, platform, keywords, region, industry, persona_id: personaId, send_limit: sendLimit });
      console.log('Creating campaign:', { campaignName, platform, keywords, region, industry, personaId, sendLimit });
      router.push('/campaigns');
    } catch (error) {
      console.error('Failed to create campaign:', error);
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
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">地区</label>
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                >
                  <option value="">全部地区</option>
                  <option value="us">美国</option>
                  <option value="uk">英国</option>
                  <option value="eu">欧洲</option>
                  <option value="sea">东南亚</option>
                  <option value="me">中东</option>
                  <option value="global">全球</option>
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
                {mockPersonas.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} - {p.company}
                  </option>
                ))}
              </select>
            </div>
            <Link href="/personas/new" className="mt-2 inline-block text-xs text-[#0071e3] hover:underline">
              + 创建新人设
            </Link>
          </div>
        </div>

        {/* Step 4: Send Limit */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-1 flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0071e3] text-xs font-semibold text-white">4</span>
            <h2 className="text-base font-semibold text-[#1d1d1f]">发送限额</h2>
          </div>
          <p className="mb-4 ml-8 text-sm text-[#86868b]">设置本次任务的最大发送数量</p>
          <div className="ml-8">
            <input
              type="number"
              min={1}
              max={500}
              value={sendLimit}
              onChange={(e) => setSendLimit(Number(e.target.value))}
              className="w-32 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
            />
            <span className="ml-2 text-sm text-[#86868b]">条消息</span>
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
            disabled={isSubmitting || !campaignName}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
            {isSubmitting ? '启动中...' : '启动任务'}
          </button>
        </div>
      </div>
    </div>
  );
}
