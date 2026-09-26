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
    <div className="min-h-screen bg-black text-white">
      <header className="border-b border-gray-800">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📄</span>
            <div>
              <h1 className="text-xl font-bold">Study Buddy</h1>
              <p className="text-xs text-gray-500">
                Powered by Gemini
              </p>
            </div>
          </div>
          {quiz && (
            <button
              onClick={handleReset}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              ← New PDF
            </button>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        {!quiz ? (
          <div className="space-y-8">
            <div className="text-center space-y-3">
              <h2 className="text-4xl font-bold">
                Drop a PDF, get a quiz
              </h2>
              <p className="text-gray-400 text-lg max-w-md mx-auto">
                Upload your lecture slides or textbook chapter. AI generates
                practice questions and explains every wrong answer.
              </p>
            </div>

            <div className="flex justify-center gap-3 items-center">
              <label className="text-sm text-gray-400">Questions:</label>
              {[5, 10, 15].map((n) => (
                <button
                  key={n}
                  onClick={() => setNumQuestions(n)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    numQuestions === n
                      ? "bg-blue-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>

            <PdfUploader onUpload={handleUpload} isLoading={loading} />

            {loading && fileName && (
              <p className="text-center text-sm text-gray-500">
                Processing <span className="text-gray-300">{fileName}</span>...
              </p>
            )}

            {error && (
              <div className="bg-red-900/20 border border-red-700/50 rounded-xl p-4 text-center">
                <p className="text-red-400">{error}</p>
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
