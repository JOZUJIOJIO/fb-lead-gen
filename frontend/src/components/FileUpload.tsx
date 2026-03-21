"use client";

import React, { useCallback, useState, useRef } from "react";
import { ArrowUpTrayIcon, DocumentIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  label?: string;
}

export default function FileUpload({
  onFileSelect,
  accept = ".csv,.xlsx,.xls",
  label = "拖拽文件到此处，或点击上传",
}: FileUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        setSelectedFile(file);
        onFileSelect(file);
      }
    },
    [onFileSelect]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setSelectedFile(file);
        onFileSelect(file);
      }
    },
    [onFileSelect]
  );

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={clsx(
        "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors",
        dragOver
          ? "border-primary bg-blue-50"
          : "border-gray-300 hover:border-primary hover:bg-gray-50"
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={handleChange}
        className="hidden"
      />
      {selectedFile ? (
        <div className="flex flex-col items-center gap-2">
          <DocumentIcon className="h-10 w-10 text-primary" />
          <p className="text-sm font-medium text-gray-900">{selectedFile.name}</p>
          <p className="text-xs text-gray-500">
            {(selectedFile.size / 1024).toFixed(1)} KB
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <ArrowUpTrayIcon className="h-10 w-10 text-gray-400" />
          <p className="text-sm text-gray-600">{label}</p>
          <p className="text-xs text-gray-400">支持 CSV、Excel 格式</p>
        </div>
      )}
    </div>
  );
}
