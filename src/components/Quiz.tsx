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
      <div className="max-w-2xl mx-auto text-center space-y-6">
        <div className="text-6xl">
          {percentage >= 80 ? "🎉" : percentage >= 50 ? "📚" : "💪"}
        </div>
        <h2 className="text-3xl font-bold">Quiz Complete!</h2>
        <div className="text-6xl font-bold text-blue-400">
          {score}/{total}
        </div>
        <p className="text-xl text-gray-400">
          {percentage >= 80
            ? "Excellent! You really know this material."
            : percentage >= 50
            ? "Good effort! Review the topics you missed."
            : "Keep studying — you'll get there!"}
        </p>
        <div className="flex gap-4 justify-center pt-4">
          <button
            onClick={onReset}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-xl font-medium transition-colors"
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
        <h2 className="text-xl font-semibold text-gray-200">{quiz.title}</h2>
        <span className="text-sm text-gray-500 bg-gray-800 px-3 py-1 rounded-full">
          {currentIndex + 1} / {total}
        </span>
      </div>

      <div className="w-full bg-gray-800 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${((currentIndex + 1) / total) * 100}%` }}
        />
      </div>

      <div className="bg-gray-900/80 border border-gray-700 rounded-2xl p-6 space-y-4">
        <span className="text-xs text-blue-400 bg-blue-400/10 px-2 py-1 rounded-full">
          {question.topic}
        </span>
        <p className="text-lg font-medium">{question.question}</p>

        <div className="space-y-3 pt-2">
          {question.options.map((option, i) => {
            let style = "border-gray-700 hover:border-gray-500 bg-gray-800/50";
            if (showResult) {
              if (i === question.correctIndex) {
                style = "border-green-500 bg-green-500/10";
              } else if (i === selectedAnswer && !isCorrect) {
                style = "border-red-500 bg-red-500/10";
              } else {
                style = "border-gray-700 bg-gray-800/30 opacity-50";
              }
            } else if (selectedAnswer === i) {
              style = "border-blue-500 bg-blue-500/10";
            }

            return (
              <button
                key={i}
                onClick={() => !showResult && setSelectedAnswer(i)}
                disabled={showResult}
                className={`w-full text-left p-4 rounded-xl border-2 transition-all ${style}`}
              >
                {option}
              </button>
            );
          })}
        </div>
      </div>

      {showResult && !isCorrect && (
        <div className="bg-amber-900/20 border border-amber-700/50 rounded-2xl p-5 space-y-2">
          <p className="font-medium text-amber-400">💡 Let me explain...</p>
          {loadingExplanation ? (
            <p className="text-gray-400 animate-pulse">
              Thinking through this...
            </p>
          ) : (
            <p className="text-gray-300 leading-relaxed">{explanation}</p>
          )}
        </div>
      )}

      {showResult && isCorrect && (
        <div className="bg-green-900/20 border border-green-700/50 rounded-2xl p-5">
          <p className="font-medium text-green-400">✅ Correct! Nice work.</p>
        </div>
      )}

      <div className="flex justify-end">
        {!showResult ? (
          <button
            onClick={handleSubmit}
            disabled={selectedAnswer === null}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl font-medium transition-colors"
          >
            Submit Answer
          </button>
        ) : (
          <button
            onClick={handleNext}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-xl font-medium transition-colors"
          >
            {currentIndex < total - 1 ? "Next Question →" : "See Results"}
          </button>
        )}
      </div>
    </div>
  );
}
