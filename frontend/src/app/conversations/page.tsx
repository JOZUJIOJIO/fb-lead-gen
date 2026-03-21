"use client";

import React, { useEffect, useState } from "react";
import {
  ChatBubbleLeftRightIcon,
  ArrowPathIcon,
  PhoneIcon,
} from "@heroicons/react/24/outline";
import { useAuth } from "@/lib/auth";
import { format } from "date-fns";
import clsx from "clsx";

interface ChatMessage {
  id: number;
  role: string;
  content: string;
  created_at: string;
}

interface Conversation {
  id: number;
  lead_id: number;
  profile_url: string;
  stage: string;
  intent_score: number;
  intent_signals: string[];
  turn_count: number;
  max_turns: number;
  whatsapp_pushed: boolean;
  our_company: string;
  our_products: string;
  created_at: string;
  updated_at: string;
  lead_name: string;
  lead_company: string;
  messages: ChatMessage[];
}

interface ConvStats {
  total: number;
  cold: number;
  curious: number;
  interested: number;
  qualified: number;
  ready_to_connect: number;
  converted: number;
  whatsapp_pushed: number;
}

const STAGE_CONFIG: Record<string, { label: string; color: string; emoji: string }> = {
  cold: { label: "冷淡", color: "bg-blue-100 text-blue-700", emoji: "❄️" },
  curious: { label: "好奇", color: "bg-yellow-100 text-yellow-700", emoji: "🤔" },
  interested: { label: "感兴趣", color: "bg-orange-100 text-orange-700", emoji: "👀" },
  qualified: { label: "已确认需求", color: "bg-green-100 text-green-700", emoji: "✅" },
  ready_to_connect: { label: "准备转私域", color: "bg-red-100 text-red-700", emoji: "🔥" },
  converted: { label: "已转化", color: "bg-purple-100 text-purple-700", emoji: "🎉" },
};

export default function ConversationsPage() {
  const { user } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [stats, setStats] = useState<ConvStats | null>(null);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [loading, setLoading] = useState(true);
  const [stageFilter, setStageFilter] = useState("");

  const fetchData = async () => {
    try {
      const params = stageFilter ? `?stage=${stageFilter}` : "";
      const [convRes, statsRes] = await Promise.all([
        fetch(`/api/conversations${params}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        }),
        fetch("/api/conversations/stats", {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        }),
      ]);
      if (convRes.ok) setConversations(await convRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) fetchData();
  }, [user, stageFilter]);

  if (!user) {
    return <div className="flex items-center justify-center h-64 text-gray-400">加载中...</div>;
  }

  const stages = [
    { key: "", label: "全部", count: stats?.total ?? 0 },
    { key: "cold", label: "❄️ 冷淡", count: stats?.cold ?? 0 },
    { key: "curious", label: "🤔 好奇", count: stats?.curious ?? 0 },
    { key: "interested", label: "👀 感兴趣", count: stats?.interested ?? 0 },
    { key: "qualified", label: "✅ 确认需求", count: stats?.qualified ?? 0 },
    { key: "ready_to_connect", label: "🔥 转私域", count: stats?.ready_to_connect ?? 0 },
    { key: "converted", label: "🎉 已转化", count: stats?.converted ?? 0 },
  ];

  return (
    <div className="h-[calc(100vh-2rem)] flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">对话管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            Facebook 私信对话追踪 · 已推送WhatsApp: {stats?.whatsapp_pushed ?? 0} 个
          </p>
        </div>
        <button
          onClick={fetchData}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <ArrowPathIcon className="h-4 w-4" />
          刷新
        </button>
      </div>

      {/* Stage Tabs */}
      <div className="flex gap-1 mb-4 overflow-x-auto pb-1">
        {stages.map((s) => (
          <button
            key={s.key}
            onClick={() => setStageFilter(s.key)}
            className={clsx(
              "px-3 py-1.5 text-xs font-medium rounded-full whitespace-nowrap transition-colors",
              stageFilter === s.key
                ? "bg-primary text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {s.label} ({s.count})
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Conversation List */}
        <div className="w-96 flex-shrink-0 bg-white rounded-xl shadow-sm border border-gray-100 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-gray-400">加载中...</div>
          ) : conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-gray-400">
              <ChatBubbleLeftRightIcon className="h-8 w-8 mb-2" />
              <p className="text-sm">暂无对话</p>
              <p className="text-xs mt-1">通过 OpenClaw 在 WhatsApp 中开始获客</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {conversations.map((conv) => {
                const cfg = STAGE_CONFIG[conv.stage] || STAGE_CONFIG.cold;
                const lastMsg = conv.messages?.[conv.messages.length - 1];
                return (
                  <button
                    key={conv.id}
                    onClick={() => setSelected(conv)}
                    className={clsx(
                      "w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors",
                      selected?.id === conv.id && "bg-blue-50"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm text-gray-900 truncate">
                        {conv.lead_name || `Lead #${conv.lead_id}`}
                      </span>
                      <span className={clsx("text-xs px-2 py-0.5 rounded-full", cfg.color)}>
                        {cfg.emoji} {cfg.label}
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {conv.lead_company || "未知公司"}
                    </div>
                    <div className="flex items-center justify-between mt-1.5">
                      <span className="text-xs text-gray-400 truncate max-w-[200px]">
                        {lastMsg ? `${lastMsg.role === "us" ? "→" : "←"} ${lastMsg.content.slice(0, 40)}...` : "尚未开始"}
                      </span>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <span>{conv.turn_count}/{conv.max_turns}轮</span>
                        <span className="font-medium text-gray-600">{conv.intent_score}分</span>
                        {conv.whatsapp_pushed && <PhoneIcon className="h-3 w-3 text-green-500" />}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Chat Detail */}
        <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-100 flex flex-col min-h-0">
          {selected ? (
            <>
              {/* Header */}
              <div className="px-6 py-4 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="font-semibold text-gray-900">
                      {selected.lead_name}
                      {selected.lead_company && (
                        <span className="text-gray-500 font-normal"> · {selected.lead_company}</span>
                      )}
                    </h2>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                      <span>轮次: {selected.turn_count}/{selected.max_turns}</span>
                      <span>意向: {selected.intent_score}分</span>
                      {selected.intent_signals.length > 0 && (
                        <span>信号: {selected.intent_signals.join(", ")}</span>
                      )}
                      {selected.whatsapp_pushed && (
                        <span className="text-green-600 font-medium">✅ WhatsApp 已推送</span>
                      )}
                    </div>
                  </div>
                  <div>
                    {(() => {
                      const cfg = STAGE_CONFIG[selected.stage] || STAGE_CONFIG.cold;
                      return (
                        <span className={clsx("text-sm px-3 py-1 rounded-full font-medium", cfg.color)}>
                          {cfg.emoji} {cfg.label}
                        </span>
                      );
                    })()}
                  </div>
                </div>
                {/* Intent Score Bar */}
                <div className="mt-3">
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        "h-full rounded-full transition-all",
                        selected.intent_score >= 80
                          ? "bg-green-500"
                          : selected.intent_score >= 60
                          ? "bg-yellow-500"
                          : selected.intent_score >= 40
                          ? "bg-orange-400"
                          : "bg-gray-300"
                      )}
                      style={{ width: `${selected.intent_score}%` }}
                    />
                  </div>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
                {selected.messages.length === 0 ? (
                  <div className="text-center text-gray-400 text-sm py-12">
                    尚无对话消息
                  </div>
                ) : (
                  selected.messages.map((msg) => (
                    <div
                      key={msg.id}
                      className={clsx(
                        "flex",
                        msg.role === "us" ? "justify-end" : "justify-start"
                      )}
                    >
                      <div
                        className={clsx(
                          "max-w-[70%] rounded-2xl px-4 py-2.5 text-sm",
                          msg.role === "us"
                            ? "bg-primary text-white rounded-br-md"
                            : "bg-gray-100 text-gray-900 rounded-bl-md"
                        )}
                      >
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                        <p
                          className={clsx(
                            "text-[10px] mt-1",
                            msg.role === "us" ? "text-blue-200" : "text-gray-400"
                          )}
                        >
                          {format(new Date(msg.created_at), "MM-dd HH:mm")}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-gray-100 bg-gray-50 rounded-b-xl text-xs text-gray-500">
                对话由 AI 自动管理 · 回复通过 WhatsApp 自动发送 · 数据实时同步
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
              <ChatBubbleLeftRightIcon className="h-12 w-12 mb-3" />
              <p className="text-sm">选择一个对话查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
