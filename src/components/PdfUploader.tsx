"use client";

import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

interface Props {
  onUpload: (file: File) => void;
  isLoading: boolean;
}

export default function PdfUploader({ onUpload, isLoading }: Props) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onUpload(acceptedFiles[0]);
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: isLoading,
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200 ${
        isDragActive
          ? "border-blue-500 bg-blue-500/10"
          : "border-gray-600 hover:border-gray-400 bg-gray-900/50"
      } ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-4">
        <div className="text-5xl">📄</div>
        {isLoading ? (
          <>
            <div className="animate-spin text-3xl">⚙️</div>
            <p className="text-lg text-gray-300">
              Gemini is generating your quiz...
            </p>
          </>
        ) : isDragActive ? (
          <p className="text-lg text-blue-400">Drop your PDF here</p>
        ) : (
          <>
            <p className="text-lg text-gray-200">
              Drop lecture slides or a textbook PDF
            </p>
            <p className="text-sm text-gray-500">
              or click to browse
            </p>
          </>
        )}
      </div>
    </div>
  );
}
