"use client";

import React from "react";
import type { Message } from "@/lib/types";
import StatusBadge from "./StatusBadge";
import { format } from "date-fns";
import {
  CheckIcon,
  PaperAirplaneIcon,
  LinkIcon,
} from "@heroicons/react/24/outline";

interface MessageCardProps {
  message: Message;
  onApprove?: (id: number) => void;
  onSend?: (id: number) => void;
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (id: number) => void;
}

export default function MessageCard({
  message,
  onApprove,
  onSend,
  selectable,
  selected,
  onSelect,
}: MessageCardProps) {
  const whatsappLink = message.whatsapp_link ||
    (message.lead_phone
      ? `https://wa.me/${message.lead_phone.replace(/[^0-9]/g, "")}?text=${encodeURIComponent(message.content)}`
      : null);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-3">
        {selectable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onSelect?.(message.id)}
            className="mt-1 rounded border-gray-300 text-primary focus:ring-primary"
          />
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">
                {message.lead_name || `线索 #${message.lead_id}`}
              </span>
              <StatusBadge status={message.status} />
            </div>
            <span className="text-xs text-gray-400">
              {format(new Date(message.created_at), "MM-dd HH:mm")}
            </span>
          </div>

          <p className="text-sm text-gray-600 line-clamp-3 mb-3">
            {message.content}
          </p>

          <div className="flex items-center gap-2">
            {message.status === "pending_approval" && onApprove && (
              <button
                onClick={() => onApprove(message.id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
              >
                <CheckIcon className="h-3.5 w-3.5" />
                审核通过
              </button>
            )}
            {message.status === "approved" && onSend && (
              <button
                onClick={() => onSend(message.id)}
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
              >
                <PaperAirplaneIcon className="h-3.5 w-3.5" />
                发送
              </button>
            )}
            {whatsappLink && (
              <a
                href={whatsappLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
              >
                <LinkIcon className="h-3.5 w-3.5" />
                WhatsApp
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
