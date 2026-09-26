import { GoogleGenerativeAI } from "@google/generative-ai";
import { NextRequest, NextResponse } from "next/server";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || "");

export async function POST(req: NextRequest) {
  try {
    const { question, userAnswer, correctAnswer, options } = await req.json();

    const model = genAI.getGenerativeModel({ model: "gemini-3.8-flash" });

    const result = await model.generateContent(
      `A student answered a quiz question incorrectly. Explain why their answer is wrong and why the correct answer is right. Be conversational, encouraging, and help them understand the concept — like a patient tutor.

Question: ${question}
Student's answer: ${options[userAnswer]}
Correct answer: ${options[correctAnswer]}

Give a clear, concise explanation (3-5 sentences). Start with acknowledging what they might have been thinking, then explain the correct concept.`
    );

    return NextResponse.json({ explanation: result.response.text() });
  } catch (error) {
    console.error("Explain error:", error);
    return NextResponse.json(
      { error: "Failed to generate explanation" },
      { status: 500 }
    );
  }
}
