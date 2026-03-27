"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  BoltIcon,
  MagnifyingGlassIcon,
  RocketLaunchIcon,
  ChatBubbleLeftRightIcon,
  ArrowPathIcon,
  PlayIcon,
  StopIcon,
  SignalIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import { automationApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AutomationStatus, TaskResult, ActiveConversation } from "@/lib/types";

const stageLabels: Record<string, { label: string; color: string }> = {
  cold: { label: "冷淡", color: "bg-gray-100 text-gray-700" },
  curious: { label: "好奇", color: "bg-yellow-100 text-yellow-700" },
  interested: { label: "有兴趣", color: "bg-blue-100 text-blue-700" },
  qualified: { label: "已确认", color: "bg-green-100 text-green-700" },
  ready_to_connect: { label: "准备成交", color: "bg-orange-100 text-orange-700" },
  converted: { label: "已转化", color: "bg-emerald-100 text-emerald-700" },
};

export default function AutomationPage() {
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusError, setStatusError] = useState(false);

  // Task states
  const [searchRunning, setSearchRunning] = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [followUpRunning, setFollowUpRunning] = useState(false);
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);

  // Form inputs
  const [searchQuery, setSearchQuery] = useState("");
  const [pipelineKeyword, setPipelineKeyword] = useState("");
  const [ourCompany, setOurCompany] = useState("");
  const [ourProducts, setOurProducts] = useState("");
  const [maxDm, setMaxDm] = useState(5);
  const [pollerInterval, setPollerInterval] = useState(5);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await automationApi.status();
      setStatus(data);
      setStatusError(false);
    } catch {
      setStatusError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [user, fetchStatus]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearchRunning(true);
    setTaskResult(null);
    try {
      const result = await automationApi.search({
        query: searchQuery,
        auto_import: true,
      });
      setTaskResult(result);
      fetchStatus();
    } catch (e: unknown) {
      setTaskResult({ success: false, message: `请求失败: ${e instanceof Error ? e.message : "未知错误"}` });
    } finally {
      setSearchRunning(false);
    }
  };

  const handlePipeline = async () => {
    if (!pipelineKeyword.trim()) return;
    setPipelineRunning(true);
    setTaskResult(null);
    try {
      const result = await automationApi.pipeline({
        keyword: pipelineKeyword,
        our_company: ourCompany,
        our_products: ourProducts,
        max_dm: maxDm,
        auto_dm: true,
      });
      setTaskResult(result);
      fetchStatus();
    } catch (e: unknown) {
      setTaskResult({ success: false, message: `请求失败: ${e instanceof Error ? e.message : "未知错误"}` });
    } finally {
      setPipelineRunning(false);
    }
  };

  const handleFollowUp = async () => {
    setFollowUpRunning(true);
    setTaskResult(null);
    try {
      const result = await automationApi.followUpAll();
      setTaskResult(result);
      fetchStatus();
    } catch (e: unknown) {
      setTaskResult({ success: false, message: `请求失败: ${e instanceof Error ? e.message : "未知错误"}` });
    } finally {
      setFollowUpRunning(false);
    }
  };

  const handlePollerToggle = async () => {
    try {
      if (status?.poller.running) {
        const result = await automationApi.stopPoller();
        setTaskResult(result);
      } else {
        const result = await automationApi.startPoller(pollerInterval);
        setTaskResult(result);
      }
      setTimeout(fetchStatus, 1000);
    } catch (e: unknown) {
      setTaskResult({ success: false, message: `操作失败: ${e instanceof Error ? e.message : "未知错误"}` });
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
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BoltIcon className="h-7 w-7 text-primary" />
          自动化控制台
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          一键操控 Facebook 搜索、客户触达、AI 自动回复
        </p>
      </div>

      {/* System Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusCard
          label="浏览器引擎"
          value={status?.browser.opencli_ready ? "OpenCLI (Chrome)" : status?.browser.playwright_available ? "Playwright" : "未就绪"}
          ok={!statusError && (status?.browser.opencli_ready || status?.browser.playwright_available || false)}
          loading={loading}
          error={statusError}
        />
        <StatusCard
          label="Auto Poller"
          value={status?.poller.running ? "运行中" : "已停止"}
          ok={status?.poller.running || false}
          loading={loading}
          error={statusError}
        />
        <StatusCard
          label="活跃对话"
          value={`${status?.conversations.active ?? 0} / ${status?.conversations.total ?? 0}`}
          ok={!statusError}
          loading={loading}
          error={statusError}
        />
      </div>

      {statusError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <ExclamationTriangleIcon className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">自动化服务未连接</p>
            <p className="text-xs text-amber-600 mt-1">
              请确保 Automation API 已启动：<code className="bg-amber-100 px-1 rounded">python mcp-server/http_api.py</code>
            </p>
          </div>
        </div>
      )}

      {/* Task Result Toast */}
      {taskResult && (
        <div
          className={`rounded-xl p-4 flex items-start gap-3 ${
            taskResult.success
              ? "bg-green-50 border border-green-200"
              : "bg-red-50 border border-red-200"
          }`}
        >
          {taskResult.success ? (
            <CheckCircleIcon className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
          ) : (
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <p className={`text-sm font-medium ${taskResult.success ? "text-green-800" : "text-red-800"}`}>
              {taskResult.message}
            </p>
            {taskResult.data && (
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
                {Object.entries(taskResult.data).map(([key, val]) =>
                  typeof val === "number" ? (
                    <div key={key} className="text-xs">
                      <span className="text-gray-500">{key}: </span>
                      <span className="font-medium">{val}</span>
                    </div>
                  ) : null
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => setTaskResult(null)}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            &times;
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Facebook Search */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <MagnifyingGlassIcon className="h-5 w-5 text-blue-500" />
            Facebook 搜索客户
          </h2>
          <div className="space-y-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="输入搜索关键词，如: LED importer Southeast Asia"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button
              onClick={handleSearch}
              disabled={searchRunning || !searchQuery.trim() || statusError}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-blue-500 hover:bg-blue-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {searchRunning ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  搜索中...
                </>
              ) : (
                <>
                  <MagnifyingGlassIcon className="h-4 w-4" />
                  搜索并导入
                </>
              )}
            </button>
          </div>
        </div>

        {/* Full Pipeline */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <RocketLaunchIcon className="h-5 w-5 text-orange-500" />
            一键全自动获客
          </h2>
          <div className="space-y-3">
            <input
              type="text"
              value={pipelineKeyword}
              onChange={(e) => setPipelineKeyword(e.target.value)}
              placeholder="搜索关键词: electronics wholesale Vietnam"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                value={ourCompany}
                onChange={(e) => setOurCompany(e.target.value)}
                placeholder="你的公司名"
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
              <input
                type="text"
                value={ourProducts}
                onChange={(e) => setOurProducts(e.target.value)}
                placeholder="你的产品"
                className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500">最多私信</label>
              <select
                value={maxDm}
                onChange={(e) => setMaxDm(Number(e.target.value))}
                className="px-2 py-1 border border-gray-200 rounded text-sm"
              >
                <option value={3}>3 人</option>
                <option value={5}>5 人</option>
                <option value={10}>10 人</option>
                <option value={20}>20 人</option>
              </select>
            </div>
            <button
              onClick={handlePipeline}
              disabled={pipelineRunning || !pipelineKeyword.trim() || statusError}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-orange-500 hover:bg-orange-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {pipelineRunning ? (
                <>
                  <ArrowPathIcon className="h-4 w-4 animate-spin" />
                  执行中 (搜索→分析→筛选→私信)...
                </>
              ) : (
                <>
                  <RocketLaunchIcon className="h-4 w-4" />
                  启动全自动流水线
                </>
              )}
            </button>
          </div>
        </div>

        {/* Follow-up All */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <ChatBubbleLeftRightIcon className="h-5 w-5 text-green-500" />
            一键跟进对话
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            检查所有活跃对话是否有新回复，自动用 AI 生成并发送回复。
          </p>
          <button
            onClick={handleFollowUp}
            disabled={followUpRunning || statusError}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-green-500 hover:bg-green-600 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {followUpRunning ? (
              <>
                <ArrowPathIcon className="h-4 w-4 animate-spin" />
                正在跟进所有对话...
              </>
            ) : (
              <>
                <ArrowPathIcon className="h-4 w-4" />
                跟进所有对话
              </>
            )}
          </button>
        </div>

        {/* Auto Poller Control */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
            <ClockIcon className="h-5 w-5 text-purple-500" />
            自动回复守护进程
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            开启后每隔 N 分钟自动检查新消息并 AI 回复，无需手动操作。
          </p>
          <div className="flex items-center gap-3 mb-4">
            <label className="text-sm text-gray-600">检查间隔</label>
            <select
              value={pollerInterval}
              onChange={(e) => setPollerInterval(Number(e.target.value))}
              className="px-2 py-1 border border-gray-200 rounded text-sm"
              disabled={status?.poller.running}
            >
              <option value={2}>2 分钟</option>
              <option value={5}>5 分钟</option>
              <option value={10}>10 分钟</option>
              <option value={15}>15 分钟</option>
            </select>
          </div>
          <button
            onClick={handlePollerToggle}
            disabled={statusError}
            className={`w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-white rounded-lg transition-colors ${
              status?.poller.running
                ? "bg-red-500 hover:bg-red-600"
                : "bg-purple-500 hover:bg-purple-600"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {status?.poller.running ? (
              <>
                <StopIcon className="h-4 w-4" />
                停止自动回复
              </>
            ) : (
              <>
                <PlayIcon className="h-4 w-4" />
                开启自动回复
              </>
            )}
          </button>
        </div>
      </div>

      {/* Active Conversations */}
      {status && status.conversations.items.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            活跃对话 ({status.conversations.active} 个进行中)
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">客户</th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">公司</th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">阶段</th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">意向分</th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">轮次</th>
                  <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">WhatsApp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {status.conversations.items.map((conv: ActiveConversation) => {
                  const stage = stageLabels[conv.stage] || { label: conv.stage, color: "bg-gray-100 text-gray-600" };
                  return (
                    <tr key={conv.lead_id} className="hover:bg-gray-50">
                      <td className="py-2.5 text-sm font-medium text-gray-900">{conv.lead_name}</td>
                      <td className="py-2.5 text-sm text-gray-500">{conv.lead_company || "-"}</td>
                      <td className="py-2.5">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${stage.color}`}>
                          {stage.label}
                        </span>
                      </td>
                      <td className="py-2.5 text-sm font-medium">
                        <span className={conv.intent_score >= 60 ? "text-green-600" : conv.intent_score >= 40 ? "text-yellow-600" : "text-gray-500"}>
                          {conv.intent_score}
                        </span>
                      </td>
                      <td className="py-2.5 text-sm text-gray-500">{conv.turn_count}/10</td>
                      <td className="py-2.5">
                        {conv.whatsapp_sent ? (
                          <CheckCircleIcon className="h-4 w-4 text-green-500" />
                        ) : (
                          <span className="text-xs text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Sub-components ---

function StatusCard({
  label,
  value,
  ok,
  loading,
  error,
}: {
  label: string;
  value: string;
  ok: boolean;
  loading: boolean;
  error: boolean;
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 flex items-center gap-3">
      <div className={`w-3 h-3 rounded-full flex-shrink-0 ${loading ? "bg-gray-300 animate-pulse" : error ? "bg-amber-400" : ok ? "bg-green-400" : "bg-red-400"}`} />
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-sm font-medium text-gray-900 truncate">
          {loading ? "检测中..." : error ? "未连接" : value}
        </p>
      </div>
    </div>
  );
}
