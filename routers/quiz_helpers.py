"""Quiz generation and rendering helpers for the Dashboard Inspector."""

import re


def parse_quiz_questions(text: str) -> list[dict]:
    """
    Parse Gemini's quiz response into a list of question dicts.

    Expected format:
        ### Question 1
        Q: What is...?
        A) Option A
        B) Option B
        C) Option C
        D) Option D
        ANSWER: B
        EXPLANATION: Because...
    """
    questions = []
    # Split on question headers
    blocks = re.split(r"###\s*Question\s*\d+", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Extract question text
        q_match = re.search(r"Q[.:]?\s*(.+?)(?=\n[ABCD]\)|\n[ABCD]\.)", block, re.DOTALL)
        if not q_match:
            q_match = re.search(r"Q[.:]?\s*(.+?)(?=\n)", block)
        question_text = q_match.group(1).strip() if q_match else ""

        # Extract options
        options = []
        for letter in ["A", "B", "C", "D"]:
            # Look for "A) text" or "A. text"
            opt_match = re.search(
                rf"{re.escape(letter)}\)\s*(.+?)(?=\n[{chr(66)}-{chr(69)}]\)|\n[{chr(66)}-{chr(69)}]\.|\nANSWER:|$)",
                block, re.DOTALL
            )
            if not opt_match:
                opt_match = re.search(
                    rf"{re.escape(letter)}\.\s*(.+?)(?=\n[{chr(66)}-{chr(69)}]\)|\n[{chr(66)}-{chr(69)}]\.|\nANSWER:|$)",
                    block, re.DOTALL
                )
            if opt_match:
                options.append({"label": letter, "text": opt_match.group(1).strip()})

        # Extract correct answer
        ans_match = re.search(r"ANSWER[.:]?\s*([A-D])", block)
        correct = ans_match.group(1).strip() if ans_match else ""

        # Extract explanation
        expl_match = re.search(r"EXPLANATION[.:]?\s*(.+?)$", block, re.DOTALL)
        explanation = expl_match.group(1).strip() if expl_match else ""

        if question_text and options and correct:
            questions.append({
                "question": question_text,
                "options": options,
                "correct": correct,
                "explanation": explanation,
            })

    return questions


def render_interactive_quiz(questions: list[dict]) -> str:
    """Render questions as interactive multiple-choice with Alpine.js."""

    def esc(s: str) -> str:
        import html
        return html.escape(s)

    q_html = ""
    for qi, q in enumerate(questions):
        options_html = ""
        for opt in q["options"]:
            opt_id = f"q{qi}_opt{opt['label']}"
            options_html += f'''
                <label for="{opt_id}"
                       class="block w-full p-3 rounded-lg border cursor-pointer transition"
                       :class="{{ selected_q{qi} === '{opt['label']}' ?
                         (correct_q{qi} === '{opt['label']}' ?
                           'bg-green-100 border-green-500' :
                           'bg-red-100 border-red-500') :
                         'bg-white border-gray-200 hover:bg-gray-50' }}"
                       @click="selectAnswer({qi}, '{opt['label']}')">
                    <div class="flex items-center gap-2">
                        <div class="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0"
                             :class="{{ selected_q{qi} === '{opt['label']}' ?
                               (correct_q{qi} === '{opt['label']}' ?
                                 'border-green-500 bg-green-500' :
                                 'border-red-500 bg-red-500') :
                               'border-gray-300' }}">
                            <span x-show="selected_q{qi} === '{opt['label']}'"
                                  class="text-white text-xs font-bold">
                                {{ correct_q{qi} === '{opt['label']}' ? '\u2713' : '\u2717' }}
                            </span>
                        </div>
                        <span class="text-sm font-medium"
                              :class="{{ selected_q{qi} === '{opt['label']}' ?
                                (correct_q{qi} === '{opt['label']}' ?
                                  'text-green-800' :
                                  'text-red-800') :
                                'text-gray-700' }}">
                            {esc(opt['text'])}
                        </span>
                    </div>
                </label>
                <input type="radio" id="{opt_id}" name="q{qi}" value="{opt['label']}" class="hidden">
            '''

        expl_html = f'''
            <div x-show="selected_q{qi}"
                 x-transition
                 class="mt-3 p-3 rounded-lg text-sm"
                 :class="{{ correct_q{qi} === selected_q{qi} ?
                   'bg-green-50 border border-green-200 text-green-800' :
                   'bg-red-50 border border-red-200 text-red-800' }}">
                <p class="font-semibold mb-1">
                    <span x-text="correct_q{qi} === selected_q{qi} ? '\u2705 Correct!' : '\u274c Incorrect. The correct answer is {q['correct']}.'"></span>
                </p>
                <p>{esc(q['explanation'])}</p>
            </div>
        '''

        q_html += f'''
        <div class="quiz-question mb-4"
             x-data="{{
                selected_q{qi}: '',
                correct_q{qi}: '{q['correct']}',
                selectAnswer(qnum, ans) {{
                    if (this['selected_q' + qnum] === '') {{
                        this['selected_q' + qnum] = ans;
                    }}
                }}
             }}">
            <p class="font-semibold text-gray-900 mb-2">
                Question {qi + 1}: {esc(q['question'])}
            </p>
            <div class="space-y-2">
                {options_html}
            </div>
            {expl_html}
        </div>
        '''

    return f'''
    <div class="p-4 bg-green-50 border border-green-200 rounded-lg text-sm mt-3">
        <p class="font-semibold text-green-800 mb-2">\U0001f4dd Practice Quiz</p>
        <p class="text-xs text-green-600 mb-3">Click an answer to check it.</p>
        <div class="text-gray-700">
            {q_html}
        </div>
    </div>
    '''