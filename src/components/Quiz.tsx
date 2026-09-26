"use client";

import { useState } from "react";

interface Question {
  id: number;
  question: string;
  options: string[];
  correctIndex: number;
  topic: string;
}

interface QuizData {
  title: string;
  questions: Question[];
}

interface Props {
  quiz: QuizData;
  onReset: () => void;
}

export default function Quiz({ quiz, onReset }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [showResult, setShowResult] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const [score, setScore] = useState(0);
  const [finished, setFinished] = useState(false);
  const [answers, setAnswers] = useState<(number | null)[]>(
    new Array(quiz.questions.length).fill(null)
  );

  const question = quiz.questions[currentIndex];
  const isCorrect = selectedAnswer === question.correctIndex;
  const total = quiz.questions.length;

  async function handleSubmit() {
    if (selectedAnswer === null) return;
    setShowResult(true);
    const newAnswers = [...answers];
    newAnswers[currentIndex] = selectedAnswer;
    setAnswers(newAnswers);

    if (isCorrect) {
      setScore((s) => s + 1);
    } else {
      setLoadingExplanation(true);
      try {
        const res = await fetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: question.question,
            userAnswer: selectedAnswer,
            correctAnswer: question.correctIndex,
            options: question.options,
          }),
        });
        const data = await res.json();
        setExplanation(data.explanation);
      } catch {
        setExplanation("Could not load explanation. Check your connection.");
      }
      setLoadingExplanation(false);
    }
  }

  function handleNext() {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1);
      setSelectedAnswer(null);
      setShowResult(false);
      setExplanation(null);
    } else {
      setFinished(true);
    }
  }

  if (finished) {
    const percentage = Math.round((score / total) * 100);
    return (
      <div className="max-w-2xl mx-auto text-center space-y-8">
        <div className="w-16 h-16 mx-auto rounded-full bg-neutral-900 border border-neutral-800 flex items-center justify-center">
          <span className="text-2xl font-semibold text-neutral-100">
            {percentage}%
          </span>
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight text-neutral-50">
            Quiz Complete
          </h2>
          <div className="text-5xl font-semibold tracking-tight text-neutral-50">
            {score}/{total}
          </div>
        </div>
        <p className="text-neutral-500 max-w-sm mx-auto leading-relaxed">
          {percentage >= 80
            ? "Excellent — you really know this material."
            : percentage >= 50
            ? "Good effort. Review the topics you missed."
            : "Keep studying — you'll get there."}
        </p>
        <div className="flex gap-4 justify-center pt-2">
          <button
            onClick={onReset}
            className="px-6 py-3 bg-neutral-100 text-black hover:bg-white rounded-xl font-medium transition-colors"
          >
            Try Another PDF
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight text-neutral-100">
          {quiz.title}
        </h2>
        <span className="text-xs font-medium text-neutral-500 bg-neutral-900 border border-neutral-800 px-3 py-1 rounded-full">
          {currentIndex + 1} / {total}
        </span>
      </div>

      <div className="w-full bg-neutral-900 rounded-full h-1">
        <div
          className="bg-neutral-100 h-1 rounded-full transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / total) * 100}%` }}
        />
      </div>

      <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-6 space-y-4">
        <span className="text-[11px] uppercase tracking-wider text-neutral-500 bg-neutral-900 border border-neutral-800 px-2.5 py-1 rounded-full">
          {question.topic}
        </span>
        <p className="text-lg font-medium text-neutral-100">
          {question.question}
        </p>

        <div className="space-y-3 pt-2">
          {question.options.map((option, i) => {
            let style =
              "border-neutral-800 hover:border-neutral-600 bg-neutral-900/50 text-neutral-300";
            if (showResult) {
              if (i === question.correctIndex) {
                style = "border-neutral-100 bg-neutral-900 text-neutral-50";
              } else if (i === selectedAnswer && !isCorrect) {
                style = "border-neutral-700 bg-neutral-900/30 text-neutral-500 line-through decoration-neutral-600";
              } else {
                style = "border-neutral-900 bg-neutral-950 text-neutral-600 opacity-50";
              }
            } else if (selectedAnswer === i) {
              style = "border-neutral-100 bg-neutral-900 text-neutral-50";
            }

            return (
              <button
                key={i}
                onClick={() => !showResult && setSelectedAnswer(i)}
                disabled={showResult}
                className={`w-full text-left p-4 rounded-xl border transition-all flex items-center justify-between ${style}`}
              >
                <span>{option}</span>
                {showResult && i === question.correctIndex && (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                )}
                {showResult && i === selectedAnswer && !isCorrect && (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {showResult && !isCorrect && (
        <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-5 space-y-2">
          <p className="font-medium text-neutral-200 text-sm uppercase tracking-wider">
            Let me explain
          </p>
          {loadingExplanation ? (
            <p className="text-neutral-500 animate-pulse">
              Thinking through this...
            </p>
          ) : (
            <p className="text-neutral-400 leading-relaxed">{explanation}</p>
          )}
        </div>
      )}

      {showResult && isCorrect && (
        <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-5">
          <p className="font-medium text-neutral-200">Correct — nice work.</p>
        </div>
      )}

      <div className="flex justify-end">
        {!showResult ? (
          <button
            onClick={handleSubmit}
            disabled={selectedAnswer === null}
            className="px-6 py-3 bg-neutral-100 text-black hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed rounded-xl font-medium transition-colors"
          >
            Submit Answer
          </button>
        ) : (
          <button
            onClick={handleNext}
            className="px-6 py-3 bg-neutral-100 text-black hover:bg-white rounded-xl font-medium transition-colors"
          >
            {currentIndex < total - 1 ? "Next Question →" : "See Results"}
          </button>
        )}
      </div>
    </div>
  );
}
