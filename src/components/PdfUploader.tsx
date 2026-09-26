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
      className={`border border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all duration-200 ${
        isDragActive
          ? "border-neutral-300 bg-neutral-900"
          : "border-neutral-800 hover:border-neutral-600 bg-neutral-950"
      } ${isLoading ? "opacity-50 cursor-not-allowed" : ""}`}
    >
      <input {...getInputProps()} />
      <div className="flex flex-col items-center gap-5">
        {isLoading ? (
          <>
            <div className="w-8 h-8 border-2 border-neutral-700 border-t-neutral-100 rounded-full animate-spin" />
            <p className="text-base text-neutral-400">
              Gemini is generating your quiz...
            </p>
          </>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl bg-neutral-900 border border-neutral-800 flex items-center justify-center">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-neutral-400"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
                <path d="M12 18v-6" />
                <path d="m9 15 3-3 3 3" />
              </svg>
            </div>
            {isDragActive ? (
              <p className="text-base text-neutral-200">Drop your PDF here</p>
            ) : (
              <>
                <p className="text-base text-neutral-200">
                  Drop lecture slides or a textbook PDF
                </p>
                <p className="text-sm text-neutral-600">or click to browse</p>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
