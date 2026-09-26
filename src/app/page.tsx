"use client";

import { useState } from "react";
import PdfUploader from "@/components/PdfUploader";
import Quiz from "@/components/Quiz";

interface QuizData {
  title: string;
  questions: {
    id: number;
    question: string;
    options: string[];
    correctIndex: number;
    topic: string;
  }[];
}

export default function Home() {
  const [quiz, setQuiz] = useState<QuizData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [numQuestions, setNumQuestions] = useState(5);

  async function handleUpload(file: File) {
    setLoading(true);
    setError(null);
    setFileName(file.name);

    const formData = new FormData();
    formData.append("pdf", file);
    formData.append("numQuestions", numQuestions.toString());

    try {
      const res = await fetch("/api/quiz", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to generate quiz");
      }

      const data = await res.json();
      setQuiz(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong"
      );
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setQuiz(null);
    setError(null);
    setFileName(null);
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-neutral-100">
      <header className="border-b border-neutral-800/80">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-neutral-100 flex items-center justify-center">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="black"
                strokeWidth="2"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6" />
              </svg>
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight text-neutral-50">
                Study Buddy
              </h1>
              <p className="text-[11px] uppercase tracking-wider text-neutral-500">
                Powered by Gemini
              </p>
            </div>
          </div>
          {quiz && (
            <button
              onClick={handleReset}
              className="text-sm text-neutral-500 hover:text-neutral-100 transition-colors"
            >
              ← New PDF
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-16">
        {!quiz ? (
          <div className="space-y-10">
            <div className="text-center space-y-3">
              <h2 className="text-4xl font-semibold tracking-tight text-neutral-50">
                Drop a PDF, get a quiz
              </h2>
              <p className="text-neutral-500 text-base max-w-md mx-auto leading-relaxed">
                Upload your lecture slides or textbook chapter. AI generates
                practice questions and explains every wrong answer.
              </p>
            </div>

            <div className="flex justify-center items-center gap-1 p-1 bg-neutral-900 border border-neutral-800 rounded-lg w-fit mx-auto">
              {[5, 10, 15].map((n) => (
                <button
                  key={n}
                  onClick={() => setNumQuestions(n)}
                  className={`px-5 py-1.5 rounded-md text-sm font-medium transition-all ${
                    numQuestions === n
                      ? "bg-neutral-100 text-black"
                      : "text-neutral-500 hover:text-neutral-200"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>

            <PdfUploader onUpload={handleUpload} isLoading={loading} />

            {loading && fileName && (
              <p className="text-center text-sm text-neutral-600">
                Processing <span className="text-neutral-400">{fileName}</span>...
              </p>
            )}

            {error && (
              <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 text-center">
                <p className="text-neutral-300">{error}</p>
              </div>
            )}
          </div>
        ) : (
          <Quiz quiz={quiz} onReset={handleReset} />
        )}
      </main>
    </div>
  );
}
