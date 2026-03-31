import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Globe, MessageCircle, Camera, Search, UserCircle, Send } from 'lucide-react';
import { campaignApi, personaApi } from '../lib/ipc';

const platforms = [
  { id: 'facebook', name: 'Facebook', icon: Globe, enabled: true },
  { id: 'twitter', name: 'Twitter', icon: MessageCircle, enabled: false, tag: '即将支持' },
  { id: 'instagram', name: 'Instagram', icon: Camera, enabled: false, tag: '即将支持' },
];

const COUNTRIES = [
  { value: '', label: '全部国家/地区' },
  // 北美
  { value: 'United States', label: '美国' },
  { value: 'Canada', label: '加拿大' },
  { value: 'Mexico', label: '墨西哥' },
  // 欧洲
  { value: 'United Kingdom', label: '英国' },
  { value: 'Germany', label: '德国' },
  { value: 'France', label: '法国' },
  { value: 'Italy', label: '意大利' },
  { value: 'Spain', label: '西班牙' },
  { value: 'Netherlands', label: '荷兰' },
  { value: 'Poland', label: '波兰' },
  { value: 'Sweden', label: '瑞典' },
  { value: 'Switzerland', label: '瑞士' },
  { value: 'Turkey', label: '土耳其' },
  { value: 'Russia', label: '俄罗斯' },
  // 亚太
  { value: 'Japan', label: '日本' },
  { value: 'South Korea', label: '韩国' },
  { value: 'India', label: '印度' },
  { value: 'Thailand', label: '泰国' },
  { value: 'Vietnam', label: '越南' },
  { value: 'Philippines', label: '菲律宾' },
  { value: 'Indonesia', label: '印度尼西亚' },
  { value: 'Malaysia', label: '马来西亚' },
  { value: 'Singapore', label: '新加坡' },
  { value: 'Australia', label: '澳大利亚' },
  { value: 'New Zealand', label: '新西兰' },
  { value: 'Pakistan', label: '巴基斯坦' },
  { value: 'Bangladesh', label: '孟加拉国' },
  // 中东
  { value: 'Saudi Arabia', label: '沙特阿拉伯' },
  { value: 'United Arab Emirates', label: '阿联酋' },
  { value: 'Israel', label: '以色列' },
  { value: 'Egypt', label: '埃及' },
  // 南美
  { value: 'Brazil', label: '巴西' },
  { value: 'Argentina', label: '阿根廷' },
  { value: 'Colombia', label: '哥伦比亚' },
  { value: 'Chile', label: '智利' },
  // 非洲
  { value: 'South Africa', label: '南非' },
  { value: 'Nigeria', label: '尼日利亚' },
  { value: 'Kenya', label: '肯尼亚' },
];

interface PersonaOption {
  id: number;
  name: string;
  company_name: string | null;
}

export default function NewCampaign() {
  const navigate = useNavigate();
  const [platform, setPlatform] = useState('facebook');
  const [keywords, setKeywords] = useState('');
  const [region, setRegion] = useState('');
  const [industry, setIndustry] = useState('');
  const [personaId, setPersonaId] = useState('');
  const [sendLimit, setSendLimit] = useState(20);
  const [campaignName, setCampaignName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    personaApi.list()
      .then((data: unknown) => {
        const list = data as PersonaOption[];
        if (Array.isArray(list)) setPersonas(list);
      })
      .catch(() => {});
  }, []);

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError('');
    try {
      await campaignApi.create({
        platform,
        search_keywords: keywords,
        search_region: region,
        search_industry: industry,
        persona_id: personaId ? Number(personaId) : null,
        send_limit: sendLimit,
      });
      navigate('/campaigns');
    } catch {
      setError('创建失败，请重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <Link to="/campaigns" className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f] transition-colors">
          <ArrowLeft className="h-4 w-4" />
          返回任务列表
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">新建获客任务</h1>
        <p className="mt-1 text-sm text-[#86868b]">配置并启动新的自动获客任务</p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="space-y-6">
        {/* Task Name */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">任务名称</h2>
          <input
            type="text"
            value={campaignName}
            onChange={e => setCampaignName(e.target.value)}
            placeholder="例如：Facebook 外贸客户开发"
            className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
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
            {platforms.map(p => (
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
                onChange={e => setKeywords(e.target.value)}
                placeholder="例如：外贸, B2B, 供应商"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">国家/地区</label>
                <select
                  value={region}
                  onChange={e => setRegion(e.target.value)}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
                >
                  {COUNTRIES.map(c => (
                    <option key={c.value} value={c.value}>{c.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">行业</label>
                <input
                  type="text"
                  value={industry}
                  onChange={e => setIndustry(e.target.value)}
                  placeholder="例如：电子商务"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none focus:border-[#0071e3] focus:bg-white"
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
                onChange={e => setPersonaId(e.target.value)}
                className="flex-1 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
              >
                <option value="">选择人设...</option>
                {personas.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.company_name ? ` - ${p.company_name}` : ''}
                  </option>
                ))}
              </select>
            </div>
            {personas.length === 0 && (
              <p className="mt-2 text-xs text-[#86868b]">暂无人设，请先在「人设管理」中创建</p>
            )}
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
              onChange={e => setSendLimit(Number(e.target.value))}
              className="w-32 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none focus:border-[#0071e3] focus:bg-white"
            />
            <span className="ml-2 text-sm text-[#86868b]">条消息</span>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3 pt-2">
          <Link
            to="/campaigns"
            className="rounded-full border border-[#e5e5e7] px-6 py-2.5 text-sm font-medium text-[#1d1d1f] hover:bg-[#f5f5f7]"
          >
            取消
          </Link>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || !campaignName || !keywords}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="h-4 w-4" />
            {isSubmitting ? '创建中...' : '创建任务'}
          </button>
        </div>
      </div>
    </div>
  );
}
