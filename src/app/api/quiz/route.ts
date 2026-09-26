import { GoogleGenerativeAI } from "@google/generative-ai";
import { NextRequest, NextResponse } from "next/server";

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY || "");

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("pdf") as File | null;
    const numQuestions = parseInt(formData.get("numQuestions") as string) || 5;

    if (!file) {
      return NextResponse.json({ error: "No PDF uploaded" }, { status: 400 });
    }

    const bytes = await file.arrayBuffer();
    const base64 = Buffer.from(bytes).toString("base64");

    const model = genAI.getGenerativeModel({ model: "gemini-3.8-flash" });

    const result = await model.generateContent([
      {
        inlineData: {
          mimeType: "application/pdf",
          data: base64,
        },
      },
      {
        text: `You are a study buddy AI. Analyze this PDF document and generate exactly ${numQuestions} multiple-choice quiz questions to test understanding of the key concepts.

Return ONLY valid JSON in this exact format, no markdown fences:
{
  "title": "Quiz title based on the document topic",
  "questions": [
    {
      "id": 1,
      "question": "The question text",
      "options": ["A) option", "B) option", "C) option", "D) option"],
      "correctIndex": 0,
      "topic": "Brief topic label"
    }
  ]
}

Make questions that test real understanding, not just memorization. Include a mix of conceptual, application, and analysis questions. Each question must have exactly 4 options.`,
      },
    ]);

    const text = result.response.text();
    const cleaned = text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
    const quiz = JSON.parse(cleaned);

    return NextResponse.json(quiz);
  } catch (error) {
    console.error("Quiz generation error:", error);
    return NextResponse.json(
      { error: "Failed to generate quiz. Check your API key and try again." },
      { status: 500 }
    );
  }
}
