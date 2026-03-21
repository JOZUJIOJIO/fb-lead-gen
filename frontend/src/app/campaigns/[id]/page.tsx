"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeftIcon,
  PlayIcon,
  PauseIcon,
  CheckIcon,
  PaperAirplaneIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import StatusBadge from "@/components/StatusBadge";
import MessageCard from "@/components/MessageCard";
import { useToast } from "@/components/Toast";
import { campaignsApi, messagesApi } from "@/lib/api";
import type { Campaign, Message } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export default function CampaignDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        const [campaignData, msgsData] = await Promise.all([
          campaignsApi.get(id),
          messagesApi.list({ campaign_id: id }),
        ]);
        setCampaign(campaignData);
        setMessages(msgsData || []);
      } catch {
        showToast("获取活动详情失败", "error");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user, id, showToast]);

  const handleLaunch = async () => {
    try {
      const updated = await campaignsApi.launch(id);
      setCampaign(updated);
      showToast("活动已启动", "success");
    } catch {
      showToast("启动失败", "error");
    }
  };

  const handleDelete = async () => {
    if (!confirm("确定要删除该活动吗？")) return;
    try {
      await campaignsApi.delete(id);
      showToast("活动已删除", "success");
      router.push("/campaigns");
    } catch {
      showToast("删除失败", "error");
    }
  };

  const handleBatchApprove = async () => {
    if (selectedIds.size === 0) {
      showToast("请先选择消息", "info");
      return;
    }
    try {
      const res = await messagesApi.batchApprove(Array.from(selectedIds));
      showToast(`已审核 ${res.approved} 条消息`, "success");
      setSelectedIds(new Set());
      const msgsData = await messagesApi.list({ campaign_id: id });
      setMessages(msgsData || []);
    } catch {
      showToast("批量审核失败", "error");
    }
  };

  const handleBatchSend = async () => {
    if (selectedIds.size === 0) {
      showToast("请先选择消息", "info");
      return;
    }
    try {
      const res = await messagesApi.batchSend(Array.from(selectedIds));
      showToast(`已发送 ${res.sent} 条消息`, "success");
      setSelectedIds(new Set());
      const msgsData = await messagesApi.list({ campaign_id: id });
      setMessages(msgsData || []);
    } catch {
      showToast("批量发送失败", "error");
    }
  };

  const handleApproveMessage = async (msgId: number) => {
    try {
      const updated = await messagesApi.approve(msgId);
      setMessages((prev) => prev.map((m) => (m.id === msgId ? updated : m)));
      showToast("消息已审核通过", "success");
    } catch {
      showToast("审核失败", "error");
    }
  };

  const handleSendMessage = async (msgId: number) => {
    try {
      const updated = await messagesApi.send(msgId);
      setMessages((prev) => prev.map((m) => (m.id === msgId ? updated : m)));
      showToast("消息已发送", "success");
    } catch {
      showToast("发送失败", "error");
    }
  };

  const toggleSelect = (msgId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) {
        next.delete(msgId);
      } else {
        next.add(msgId);
      }
      return next;
    });
  };

  if (authLoading || !user || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">活动不存在</p>
      </div>
    );
  }

  const totalMessages = messages.length;
  const sentMessages = messages.filter((m) =>
    ["sent", "delivered", "read", "replied"].includes(m.status)
  ).length;
  const progress = totalMessages > 0 ? (sentMessages / totalMessages) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{campaign.name}</h1>
            <StatusBadge status={campaign.status} />
          </div>
          {campaign.description && (
            <p className="text-sm text-gray-500 mt-1">{campaign.description}</p>
          )}
        </div>
        <div className="flex gap-2">
          {campaign.status === "draft" && (
            <button
              onClick={handleLaunch}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
            >
              <PlayIcon className="h-4 w-4" />
              启动活动
            </button>
          )}
          {campaign.status === "active" && (
            <button className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-yellow-700 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition-colors">
              <PauseIcon className="h-4 w-4" />
              暂停
            </button>
          )}
          <button
            onClick={handleDelete}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
          >
            <TrashIcon className="h-4 w-4" />
            删除
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">{campaign.leads_count}</p>
          <p className="text-sm text-gray-500">目标线索</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">{totalMessages}</p>
          <p className="text-sm text-gray-500">总消息数</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">{campaign.messages_sent}</p>
          <p className="text-sm text-gray-500">已发送</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">{campaign.replies_count}</p>
          <p className="text-sm text-gray-500">已回复</p>
        </div>
      </div>

      {/* Progress */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold text-gray-900">活动进度</h2>
          <span className="text-sm text-gray-500">{progress.toFixed(0)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5">
          <div
            className="bg-primary h-2.5 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            消息列表 ({messages.length})
          </h2>
          <div className="flex gap-2">
            <button
              onClick={handleBatchApprove}
              disabled={selectedIds.size === 0}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <CheckIcon className="h-3.5 w-3.5" />
              批量审核 {selectedIds.size > 0 && `(${selectedIds.size})`}
            </button>
            <button
              onClick={handleBatchSend}
              disabled={selectedIds.size === 0}
              className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg transition-colors disabled:opacity-50"
            >
              <PaperAirplaneIcon className="h-3.5 w-3.5" />
              批量发送 {selectedIds.size > 0 && `(${selectedIds.size})`}
            </button>
          </div>
        </div>

        {messages.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>暂无消息</p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((msg) => (
              <MessageCard
                key={msg.id}
                message={msg}
                onApprove={handleApproveMessage}
                onSend={handleSendMessage}
                selectable
                selected={selectedIds.has(msg.id)}
                onSelect={toggleSelect}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
