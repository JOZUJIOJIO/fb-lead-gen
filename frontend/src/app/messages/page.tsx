"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  CheckIcon,
  PaperAirplaneIcon,
} from "@heroicons/react/24/outline";
import MessageCard from "@/components/MessageCard";
import { useToast } from "@/components/Toast";
import { messagesApi } from "@/lib/api";
import type { Message } from "@/lib/types";
import { useAuth } from "@/lib/auth";

const statusTabs = [
  { key: "", label: "全部" },
  { key: "pending_approval", label: "待审核" },
  { key: "approved", label: "已审核" },
  { key: "sent", label: "已发送" },
  { key: "delivered", label: "已送达" },
  { key: "read", label: "已读" },
  { key: "replied", label: "已回复" },
  { key: "failed", label: "失败" },
];

export default function MessagesPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();

  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const fetchMessages = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const data = await messagesApi.list({
        status: statusFilter || undefined,
      });
      setMessages(data || []);
    } catch {
      showToast("获取消息列表失败", "error");
    } finally {
      setLoading(false);
    }
  }, [user, statusFilter, showToast]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  const handleApprove = async (msgId: number) => {
    try {
      const updated = await messagesApi.approve(msgId);
      setMessages((prev) => prev.map((m) => (m.id === msgId ? updated : m)));
      showToast("消息已审核通过", "success");
    } catch {
      showToast("审核失败", "error");
    }
  };

  const handleSend = async (msgId: number) => {
    try {
      const updated = await messagesApi.send(msgId);
      setMessages((prev) => prev.map((m) => (m.id === msgId ? updated : m)));
      showToast("消息已发送", "success");
    } catch {
      showToast("发送失败", "error");
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
      fetchMessages();
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
      fetchMessages();
    } catch {
      showToast("批量发送失败", "error");
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

  const selectAll = () => {
    if (selectedIds.size === messages.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(messages.map((m) => m.id)));
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
          <h1 className="text-2xl font-bold text-gray-900">消息中心</h1>
          <p className="text-sm text-gray-500 mt-1">管理所有 WhatsApp 消息</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleBatchApprove}
            disabled={selectedIds.size === 0}
            className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors disabled:opacity-50"
          >
            <CheckIcon className="h-4 w-4" />
            批量审核 {selectedIds.size > 0 && `(${selectedIds.size})`}
          </button>
          <button
            onClick={handleBatchSend}
            disabled={selectedIds.size === 0}
            className="inline-flex items-center gap-1 px-3 py-2 text-sm font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg transition-colors disabled:opacity-50"
          >
            <PaperAirplaneIcon className="h-4 w-4" />
            批量发送 {selectedIds.size > 0 && `(${selectedIds.size})`}
          </button>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-1 bg-white rounded-lg p-1 shadow-sm border border-gray-100 overflow-x-auto">
        {statusTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setStatusFilter(tab.key);
              setSelectedIds(new Set());
            }}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors whitespace-nowrap ${
              statusFilter === tab.key
                ? "bg-primary text-white"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Select All */}
      {messages.length > 0 && (
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={selectedIds.size === messages.length && messages.length > 0}
              onChange={selectAll}
              className="rounded border-gray-300 text-primary focus:ring-primary"
            />
            全选
          </label>
          <span className="text-sm text-gray-400">
            共 {messages.length} 条消息
          </span>
        </div>
      )}

      {/* Messages */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-400">加载中...</div>
        </div>
      ) : messages.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
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
              d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
            />
          </svg>
          <p className="text-gray-500 mt-2">暂无消息</p>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.map((msg) => (
            <MessageCard
              key={msg.id}
              message={msg}
              onApprove={handleApprove}
              onSend={handleSend}
              selectable
              selected={selectedIds.has(msg.id)}
              onSelect={toggleSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
