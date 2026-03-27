"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PlusIcon } from "@heroicons/react/24/outline";
import { format } from "date-fns";
import StatusBadge from "@/components/StatusBadge";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { campaignsApi, templatesApi } from "@/lib/api";
import type { Campaign, Template, CampaignCreateRequest } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export default function CampaignsPageWrapper() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><div className="text-gray-400">加载中...</div></div>}>
      <CampaignsPage />
    </Suspense>
  );
}

function CampaignsPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const searchParams = useSearchParams();

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<CampaignCreateRequest>({
    name: "",
    description: "",
    template_id: undefined,
    target_score_min: undefined,
    target_status: "",
  });

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        const [campaignData, templateData] = await Promise.all([
          campaignsApi.list(),
          templatesApi.list(),
        ]);
        setCampaigns(campaignData || []);
        setTemplates(templateData || []);
      } catch {
        showToast("获取活动列表失败", "error");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user, showToast]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      showToast("请输入活动名称", "error");
      return;
    }
    setCreating(true);
    try {
      const newCampaign = await campaignsApi.create(form);
      setCampaigns((prev) => [newCampaign, ...prev]);
      setCreateOpen(false);
      setForm({ name: "", description: "", template_id: undefined, target_score_min: undefined, target_status: "" });
      showToast("活动创建成功", "success");
    } catch {
      showToast("创建失败，请重试", "error");
    } finally {
      setCreating(false);
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">营销活动</h1>
          <p className="text-sm text-gray-500 mt-1">创建和管理营销活动</p>
        </div>
        <button
          onClick={() => setCreateOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors"
        >
          <PlusIcon className="h-4 w-4" />
          创建活动
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-400">加载中...</div>
        </div>
      ) : campaigns.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
          <MegaphoneIconPlaceholder />
          <p className="text-gray-500 mt-2">暂无营销活动</p>
          <button
            onClick={() => setCreateOpen(true)}
            className="mt-4 text-sm text-primary hover:underline"
          >
            创建第一个活动
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {campaigns.map((campaign) => (
            <Link
              key={campaign.id}
              href={`/campaigns/${campaign.id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-gray-900 truncate flex-1">
                  {campaign.name}
                </h3>
                <StatusBadge status={campaign.status} />
              </div>
              {campaign.description && (
                <p className="text-sm text-gray-500 line-clamp-2 mb-4">
                  {campaign.description}
                </p>
              )}
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-lg font-bold text-gray-900">{campaign.leads_count}</p>
                  <p className="text-xs text-gray-500">目标线索</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-lg font-bold text-gray-900">{campaign.messages_sent}</p>
                  <p className="text-xs text-gray-500">已发消息</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-lg font-bold text-gray-900">{campaign.replies_count}</p>
                  <p className="text-xs text-gray-500">回复数</p>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-3">
                创建于 {format(new Date(campaign.created_at), "yyyy-MM-dd")}
              </p>
            </Link>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="创建营销活动">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              活动名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如：Q1 东南亚客户推广"
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              活动描述
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              rows={3}
              placeholder="活动目标和说明"
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm resize-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              消息模板
            </label>
            <select
              value={form.template_id || ""}
              onChange={(e) =>
                setForm({ ...form, template_id: e.target.value ? Number(e.target.value) : undefined })
              }
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
            >
              <option value="">不使用模板</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.language})
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                最低评分
              </label>
              <input
                type="number"
                min={0}
                max={100}
                value={form.target_score_min ?? ""}
                onChange={(e) =>
                  setForm({ ...form, target_score_min: e.target.value ? Number(e.target.value) : undefined })
                }
                placeholder="0"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                目标状态
              </label>
              <select
                value={form.target_status}
                onChange={(e) => setForm({ ...form, target_status: e.target.value })}
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
              >
                <option value="">全部状态</option>
                <option value="new">新线索</option>
                <option value="analyzed">已分析</option>
                <option value="contacted">已联系</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {creating ? "创建中..." : "创建活动"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

function MegaphoneIconPlaceholder() {
  return (
    <svg
      className="h-12 w-12 text-gray-300 mx-auto"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38c-.551.318-1.26.117-1.527-.461a20.845 20.845 0 01-1.44-4.282m3.102.069a18.03 18.03 0 01-.59-4.59c0-1.586.205-3.124.59-4.59m0 9.18a23.848 23.848 0 018.835 2.535M10.34 6.66a23.847 23.847 0 008.835-2.535m0 0A23.74 23.74 0 0018.795 3m.38 1.125a23.91 23.91 0 011.014 5.395m-1.014 8.855c-.118.38-.245.754-.38 1.125m.38-1.125a23.91 23.91 0 001.014-5.395m0-3.46c.495.413.811 1.035.811 1.73 0 .695-.316 1.317-.811 1.73m0-3.46a24.347 24.347 0 010 3.46"
      />
    </svg>
  );
}
