"use client";

import React, { Suspense, useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  MagnifyingGlassIcon,
  ArrowUpTrayIcon,
  SparklesIcon,
} from "@heroicons/react/24/outline";
import { format } from "date-fns";
import DataTable, { Column } from "@/components/DataTable";
import ScoreBadge from "@/components/ScoreBadge";
import StatusBadge from "@/components/StatusBadge";
import Modal from "@/components/Modal";
import FileUpload from "@/components/FileUpload";
import { useToast } from "@/components/Toast";
import { leadsApi } from "@/lib/api";
import type { Lead } from "@/lib/types";
import { useAuth } from "@/lib/auth";

const statusTabs = [
  { key: "", label: "全部" },
  { key: "new", label: "新线索" },
  { key: "analyzed", label: "已分析" },
  { key: "contacted", label: "已联系" },
  { key: "replied", label: "已回复" },
  { key: "converted", label: "已转化" },
];

export default function LeadsPageWrapper() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-64"><div className="text-gray-400">加载中...</div></div>}>
      <LeadsPage />
    </Suspense>
  );
}

function LeadsPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();
  const searchParams = useSearchParams();

  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    if (searchParams.get("action") === "import") {
      setImportModalOpen(true);
    }
  }, [searchParams]);

  const fetchLeads = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const res = await leadsApi.list({
        page,
        page_size: 20,
        status: status || undefined,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setLeads(res.items || []);
      setTotalPages(res.pages || 1);
    } catch {
      showToast("获取线索列表失败", "error");
    } finally {
      setLoading(false);
    }
  }, [user, page, status, search, sortBy, sortOrder, showToast]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(key);
      setSortOrder("desc");
    }
    setPage(1);
  };

  const handleImport = async (file: File) => {
    setImporting(true);
    try {
      const res = await leadsApi.import(file);
      showToast(`成功导入 ${res.imported} 条线索`, "success");
      setImportModalOpen(false);
      fetchLeads();
    } catch {
      showToast("导入失败，请检查文件格式", "error");
    } finally {
      setImporting(false);
    }
  };

  const handleBatchAnalyze = async () => {
    if (selectedIds.size === 0) {
      showToast("请先选择要分析的线索", "info");
      return;
    }
    setAnalyzing(true);
    try {
      const res = await leadsApi.batchAnalyze(Array.from(selectedIds));
      showToast(`成功分析 ${res.analyzed} 条线索`, "success");
      setSelectedIds(new Set());
      fetchLeads();
    } catch {
      showToast("分析失败，请重试", "error");
    } finally {
      setAnalyzing(false);
    }
  };

  const columns: Column<Lead>[] = [
    {
      key: "name",
      label: "姓名",
      render: (lead: Lead) => (
        <Link
          href={`/leads/${lead.id}`}
          className="font-medium text-gray-900 hover:text-primary"
        >
          {lead.name}
        </Link>
      ),
    },
    { key: "company", label: "公司" },
    { key: "phone", label: "电话" },
    {
      key: "score",
      label: "评分",
      sortable: true,
      render: (lead: Lead) => <ScoreBadge score={lead.score} />,
    },
    {
      key: "status",
      label: "状态",
      render: (lead: Lead) => <StatusBadge status={lead.status} />,
    },
    { key: "language", label: "语言" },
    { key: "source", label: "来源" },
    {
      key: "created_at",
      label: "创建时间",
      sortable: true,
      render: (lead: Lead) => (
        <span className="text-xs text-gray-400">
          {format(new Date(lead.created_at), "yyyy-MM-dd HH:mm")}
        </span>
      ),
    },
  ];

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
          <h1 className="text-2xl font-bold text-gray-900">线索管理</h1>
          <p className="text-sm text-gray-500 mt-1">管理和分析您的客户线索</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleBatchAnalyze}
            disabled={analyzing || selectedIds.size === 0}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <SparklesIcon className="h-4 w-4" />
            {analyzing ? "分析中..." : `AI 分析${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>
          <button
            onClick={() => setImportModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors"
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            导入 CSV
          </button>
        </div>
      </div>

      {/* Status Tabs */}
      <div className="flex items-center gap-1 bg-white rounded-lg p-1 shadow-sm border border-gray-100 w-fit">
        {statusTabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => {
              setStatus(tab.key);
              setPage(1);
            }}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
              status === tab.key
                ? "bg-primary text-white"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="搜索姓名、公司、电话..."
          className="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-gray-200 focus:ring-2 focus:ring-primary focus:border-primary outline-none"
        />
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={leads as unknown as Record<string, unknown>[]}
        keyField="id"
        selectable
        selectedIds={selectedIds}
        onSelectionChange={setSelectedIds}
        sortBy={sortBy}
        sortOrder={sortOrder}
        onSort={handleSort}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        loading={loading}
        emptyMessage="暂无线索数据，请导入 CSV 文件"
      />

      {/* Import Modal */}
      <Modal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        title="导入线索"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            上传 CSV 或 Excel 文件，系统将自动解析并导入线索数据。
            文件应包含以下列：姓名、公司、电话、邮箱、来源、语言等。
          </p>
          <FileUpload onFileSelect={handleImport} />
          {importing && (
            <div className="text-center text-sm text-gray-500">
              正在导入，请稍候...
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
