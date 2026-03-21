"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import { format } from "date-fns";
import Modal from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { templatesApi } from "@/lib/api";
import type { Template, TemplateCreateRequest } from "@/lib/types";
import { useAuth } from "@/lib/auth";

const sampleData: Record<string, string> = {
  name: "John Smith",
  company: "Acme Corp",
  product: "LED Lights",
  price: "$10.99",
};

function highlightVariables(text: string) {
  return text.replace(
    /\{\{(\w+)\}\}/g,
    '<span class="bg-blue-100 text-blue-700 px-1 rounded font-mono text-xs">{{$1}}</span>'
  );
}

function renderPreview(body: string) {
  let preview = body;
  Object.entries(sampleData).forEach(([key, value]) => {
    preview = preview.replace(new RegExp(`\\{\\{${key}\\}\\}`, "g"), value);
  });
  // Highlight remaining unresolved variables
  preview = preview.replace(
    /\{\{(\w+)\}\}/g,
    '<span class="bg-yellow-100 text-yellow-700 px-1 rounded text-xs">[未知: $1]</span>'
  );
  return preview;
}

export default function TemplatesPage() {
  const { user, loading: authLoading } = useAuth();
  const { showToast } = useToast();

  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<Template | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<TemplateCreateRequest>({
    name: "",
    language: "en",
    body: "",
  });

  const fetchTemplates = useCallback(async () => {
    if (!user) return;
    try {
      const data = await templatesApi.list();
      setTemplates(data || []);
    } catch {
      showToast("获取模板列表失败", "error");
    } finally {
      setLoading(false);
    }
  }, [user, showToast]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const openCreate = () => {
    setEditingId(null);
    setForm({ name: "", language: "en", body: "" });
    setModalOpen(true);
  };

  const openEdit = (template: Template) => {
    setEditingId(template.id);
    setForm({ name: template.name, language: template.language, body: template.body });
    setModalOpen(true);
  };

  const openPreview = (template: Template) => {
    setPreviewTemplate(template);
    setPreviewOpen(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.body.trim()) {
      showToast("请填写模板名称和内容", "error");
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        const updated = await templatesApi.update(editingId, form);
        setTemplates((prev) => prev.map((t) => (t.id === editingId ? updated : t)));
        showToast("模板已更新", "success");
      } else {
        const created = await templatesApi.create(form);
        setTemplates((prev) => [created, ...prev]);
        showToast("模板创建成功", "success");
      }
      setModalOpen(false);
    } catch {
      showToast("保存失败，请重试", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("确定要删除该模板吗？")) return;
    try {
      await templatesApi.delete(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
      showToast("模板已删除", "success");
    } catch {
      showToast("删除失败", "error");
    }
  };

  const languageLabels: Record<string, string> = {
    en: "English",
    zh: "中文",
    es: "Espanol",
    ar: "Arabic",
    pt: "Portugues",
    fr: "Francais",
    de: "Deutsch",
    ja: "日本語",
    ko: "한국어",
    th: "ภาษาไทย",
    vi: "Tieng Viet",
    id: "Bahasa Indonesia",
    ms: "Bahasa Melayu",
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
          <h1 className="text-2xl font-bold text-gray-900">模板管理</h1>
          <p className="text-sm text-gray-500 mt-1">
            创建和管理消息模板，支持 {"{{变量}}"} 语法
          </p>
        </div>
        <button
          onClick={openCreate}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors"
        >
          <PlusIcon className="h-4 w-4" />
          创建模板
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-400">加载中...</div>
        </div>
      ) : templates.length === 0 ? (
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
              d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
            />
          </svg>
          <p className="text-gray-500 mt-2">暂无模板</p>
          <button
            onClick={openCreate}
            className="mt-4 text-sm text-primary hover:underline"
          >
            创建第一个模板
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((template) => (
            <div
              key={template.id}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-gray-900 truncate flex-1">
                  {template.name}
                </h3>
                <span className="ml-2 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium">
                  {languageLabels[template.language] || template.language}
                </span>
              </div>

              <div
                className="text-sm text-gray-600 line-clamp-4 mb-4 leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: highlightVariables(template.body),
                }}
              />

              {template.variables && template.variables.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {template.variables.map((v) => (
                    <span
                      key={v}
                      className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs font-mono"
                    >
                      {v}
                    </span>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <span className="text-xs text-gray-400">
                  {format(new Date(template.created_at), "yyyy-MM-dd")}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => openPreview(template)}
                    className="p-1.5 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
                    title="预览"
                  >
                    <EyeIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => openEdit(template)}
                    className="p-1.5 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
                    title="编辑"
                  >
                    <PencilSquareIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(template.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50 transition-colors"
                    title="删除"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingId ? "编辑模板" : "创建模板"}
        maxWidth="max-w-xl"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              模板名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="例如：东南亚客户初次联系"
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              语言
            </label>
            <select
              value={form.language}
              onChange={(e) => setForm({ ...form, language: e.target.value })}
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm"
            >
              {Object.entries(languageLabels).map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              模板内容 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
              rows={6}
              placeholder={"Hi {{name}},\n\nI noticed your company {{company}} might be interested in our {{product}}.\n\nWould you like to learn more?"}
              className="w-full px-4 py-2.5 rounded-lg border border-gray-300 focus:ring-2 focus:ring-primary focus:border-primary outline-none text-sm resize-none font-mono"
            />
            <p className="text-xs text-gray-400 mt-1">
              使用 {"{{变量名}}"} 语法插入动态内容，如 {"{{name}}"}, {"{{company}}"}
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {saving ? "保存中..." : editingId ? "更新模板" : "创建模板"}
            </button>
          </div>
        </form>
      </Modal>

      {/* Preview Modal */}
      <Modal
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
        title="模板预览"
        maxWidth="max-w-lg"
      >
        {previewTemplate && (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">原始模板</h3>
              <div
                className="bg-gray-50 rounded-lg p-4 text-sm leading-relaxed"
                dangerouslySetInnerHTML={{
                  __html: highlightVariables(previewTemplate.body),
                }}
              />
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">示例预览</h3>
              <div
                className="bg-green-50 rounded-lg p-4 text-sm leading-relaxed border border-green-100"
                dangerouslySetInnerHTML={{
                  __html: renderPreview(previewTemplate.body),
                }}
              />
              <p className="text-xs text-gray-400 mt-2">
                示例数据: name=John Smith, company=Acme Corp, product=LED Lights, price=$10.99
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
