"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeftIcon,
  SparklesIcon,
  ChatBubbleLeftIcon,
  LinkIcon,
  TrashIcon,
} from "@heroicons/react/24/outline";
import { format } from "date-fns";
import ScoreBadge from "@/components/ScoreBadge";
import StatusBadge from "@/components/StatusBadge";
import MessageCard from "@/components/MessageCard";
import { useToast } from "@/components/Toast";
import { leadsApi, messagesApi } from "@/lib/api";
import type { Lead, Message } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export default function LeadDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [lead, setLead] = useState<Lead | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        const [leadData, msgsData] = await Promise.all([
          leadsApi.get(id),
          messagesApi.list({ lead_id: id }),
        ]);
        setLead(leadData);
        setMessages(msgsData || []);
      } catch {
        showToast("获取线索详情失败", "error");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user, id, showToast]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const updated = await leadsApi.analyze(id);
      setLead(updated);
      showToast("AI 分析完成", "success");
    } catch {
      showToast("分析失败，请重试", "error");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("确定要删除该线索吗？此操作不可撤销。")) return;
    try {
      await leadsApi.delete(id);
      showToast("线索已删除", "success");
      router.push("/leads");
    } catch {
      showToast("删除失败", "error");
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

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">线索不存在</p>
        <Link href="/leads" className="text-primary hover:underline text-sm mt-2 inline-block">
          返回线索列表
        </Link>
      </div>
    );
  }

  const whatsappLink = lead.whatsapp_number || lead.phone
    ? `https://wa.me/${(lead.whatsapp_number || lead.phone || "").replace(/[^0-9]/g, "")}`
    : null;

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
          <h1 className="text-2xl font-bold text-gray-900">{lead.name}</h1>
          <p className="text-sm text-gray-500">{lead.company || "未填写公司"}</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <SparklesIcon className="h-4 w-4" />
            {analyzing ? "分析中..." : "AI 分析"}
          </button>
          {whatsappLink && (
            <a
              href={whatsappLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
            >
              <LinkIcon className="h-4 w-4" />
              WhatsApp 聊天
            </a>
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Lead Info */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">基本信息</h2>
            <dl className="space-y-3">
              {[
                { label: "姓名", value: lead.name },
                { label: "公司", value: lead.company },
                { label: "电话", value: lead.phone },
                { label: "邮箱", value: lead.email },
                { label: "WhatsApp", value: lead.whatsapp_number },
                { label: "Facebook", value: lead.facebook_profile },
                { label: "来源", value: lead.source },
                { label: "语言", value: lead.language },
                { label: "国家", value: lead.country },
                { label: "行业", value: lead.industry },
              ].map(({ label, value }) => (
                <div key={label} className="flex justify-between">
                  <dt className="text-sm text-gray-500">{label}</dt>
                  <dd className="text-sm font-medium text-gray-900 text-right max-w-[60%] truncate">
                    {value || "-"}
                  </dd>
                </div>
              ))}
              <div className="flex justify-between items-center">
                <dt className="text-sm text-gray-500">状态</dt>
                <dd><StatusBadge status={lead.status} /></dd>
              </div>
              <div className="flex justify-between items-center">
                <dt className="text-sm text-gray-500">评分</dt>
                <dd><ScoreBadge score={lead.score} /></dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-sm text-gray-500">创建时间</dt>
                <dd className="text-sm text-gray-700">
                  {format(new Date(lead.created_at), "yyyy-MM-dd HH:mm")}
                </dd>
              </div>
            </dl>
          </div>

          {lead.notes && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">备注</h2>
              <p className="text-sm text-gray-600 whitespace-pre-wrap">{lead.notes}</p>
            </div>
          )}
        </div>

        {/* Analysis & Messages */}
        <div className="lg:col-span-2 space-y-6">
          {/* AI Analysis */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">AI 分析结果</h2>
            {lead.score !== null && lead.score !== undefined ? (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="relative w-20 h-20">
                    <svg className="w-20 h-20 transform -rotate-90" viewBox="0 0 80 80">
                      <circle
                        cx="40"
                        cy="40"
                        r="34"
                        stroke="#e5e7eb"
                        strokeWidth="8"
                        fill="none"
                      />
                      <circle
                        cx="40"
                        cy="40"
                        r="34"
                        stroke={
                          lead.score >= 80
                            ? "#10b981"
                            : lead.score >= 60
                            ? "#22c55e"
                            : lead.score >= 40
                            ? "#eab308"
                            : "#ef4444"
                        }
                        strokeWidth="8"
                        fill="none"
                        strokeDasharray={`${(lead.score / 100) * 213.6} 213.6`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-lg font-bold text-gray-900">{lead.score}</span>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">意向评分</p>
                    <p className="text-xs text-gray-500">
                      {lead.score >= 80
                        ? "高意向客户"
                        : lead.score >= 60
                        ? "中高意向"
                        : lead.score >= 40
                        ? "中等意向"
                        : "低意向客户"}
                    </p>
                  </div>
                </div>
                {lead.analysis_result && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">
                      {lead.analysis_result}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <SparklesIcon className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">尚未进行 AI 分析</p>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="mt-3 text-sm text-primary hover:underline"
                >
                  {analyzing ? "分析中..." : "立即分析"}
                </button>
              </div>
            )}
          </div>

          {/* Messages */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">消息记录</h2>
              <span className="text-sm text-gray-400">{messages.length} 条消息</span>
            </div>
            {messages.length === 0 ? (
              <div className="text-center py-8">
                <ChatBubbleLeftIcon className="h-10 w-10 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">暂无消息记录</p>
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((msg) => (
                  <MessageCard
                    key={msg.id}
                    message={msg}
                    onApprove={handleApproveMessage}
                    onSend={handleSendMessage}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
