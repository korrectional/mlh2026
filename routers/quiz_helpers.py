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
    """Render questions as interactive multiple-choice using plain JavaScript."""

    def esc(s: str) -> str:
        import html
        return html.escape(s)

    import json as _json

    # Serialize the questions data as JSON for the JS to use
    quiz_data_json = _json.dumps(questions, ensure_ascii=False)

    q_html = ""
    for qi, q in enumerate(questions):
        options_html = ""
        for opt in q["options"]:
            label = esc(opt["text"])
            opt_id = f"quiz_q{qi}_{opt['label']}"
            options_html += f'''
            <div id="{opt_id}_wrapper"
                 class="quiz-option block w-full p-3 rounded-lg border cursor-pointer transition bg-white border-gray-200 hover:bg-gray-50"
                 onclick="selectQuizAnswer({qi}, '{opt['label']}', {qi} === {qi})">
                <div class="flex items-center gap-2">
                    <div id="{opt_id}_circle"
                         class="w-5 h-5 rounded-full border-2 border-gray-300 flex items-center justify-center shrink-0">
                        <span id="{opt_id}_mark" class="text-white text-xs font-bold hidden"></span>
                    </div>
                    <span id="{opt_id}_text" class="text-sm font-medium text-gray-700">{label}</span>
                </div>
            </div>
            '''

        expl_id = f"quiz_expl_{qi}"
        expl_html = f'''
        <div id="{expl_id}" class="mt-3 p-3 rounded-lg text-sm hidden"></div>
        '''

        q_html += f'''
        <div class="quiz-question mb-4" id="quiz_q_div_{qi}">
            <p class="font-semibold text-gray-900 mb-2">
                Question {qi + 1}: {esc(q['question'])}
            </p>
            <div class="space-y-2" id="quiz_q_options_{qi}">
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
    <script>
    (function() {{
        const quizData = {quiz_data_json};
        const answered = {{}};

        window.selectQuizAnswer = function(qIdx, selectedLabel) {{
            if (answered[qIdx]) return;
            answered[qIdx] = selectedLabel;

            const correct = quizData[qIdx].correct;
            const isCorrect = selectedLabel === correct;
            const explanation = quizData[qIdx].explanation;

            // Get all option wrappers for this question
            const optionsDiv = document.getElementById('quiz_q_options_' + qIdx);
            const wrappers = optionsDiv.querySelectorAll('[class*="quiz-option"]');

            wrappers.forEach(function(wrapper) {{
                // Extract the label from the onclick attribute
                const onclick = wrapper.getAttribute('onclick');
                const match = onclick.match(/'([A-D])'/);
                if (!match) return;
                const label = match[1];

                const circle = wrapper.querySelector('[id$="_circle"]');
                const mark = wrapper.querySelector('[id$="_mark"]');
                const textSpan = wrapper.querySelector('[id$="_text"]');

                if (label === correct) {{
                    wrapper.className = wrapper.className.replace(/bg-white|border-gray-200|hover:bg-gray-50/g, '');
                    wrapper.className += ' bg-green-100 border-green-500';
                    if (circle) {{
                        circle.className = circle.className.replace(/border-gray-300/g, 'border-green-500 bg-green-500');
                    }}
                    if (mark) {{
                        mark.className = mark.className.replace(/hidden/g, '');
                        mark.textContent = '\\u2713';
                    }}
                    if (textSpan) {{
                        textSpan.className = textSpan.className.replace(/text-gray-700/g, 'text-green-800');
                    }}
                }} else if (label === selectedLabel) {{
                    // This is the wrong answer the user picked
                    wrapper.className = wrapper.className.replace(/bg-white|border-gray-200|hover:bg-gray-50/g, '');
                    wrapper.className += ' bg-red-100 border-red-500';
                    if (circle) {{
                        circle.className = circle.className.replace(/border-gray-300/g, 'border-red-500 bg-red-500');
                    }}
                    if (mark) {{
                        mark.className = mark.className.replace(/hidden/g, '');
                        mark.textContent = '\\u2717';
                    }}
                    if (textSpan) {{
                        textSpan.className = textSpan.className.replace(/text-gray-700/g, 'text-red-800');
                    }}
                }} else {{
                    // Dim unselected options
                    wrapper.style.opacity = '0.5';
                }}
            }});

            // Show explanation
            const explDiv = document.getElementById('quiz_expl_' + qIdx);
            if (explDiv) {{
                explDiv.className = 'mt-3 p-3 rounded-lg text-sm ' +
                    (isCorrect ? 'bg-green-50 border border-green-200 text-green-800' :
                                 'bg-red-50 border border-red-200 text-red-800');
                explDiv.innerHTML = '<p class="font-semibold mb-1">' +
                    (isCorrect ? '\\u2705 Correct!' : '\\u274c Incorrect. The correct answer is ' + correct + '.') +
                    '</p><p>' + escHtml(explanation) + '</p>';
                explDiv.classList.remove('hidden');
            }}
        }};

        function escHtml(s) {{
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }}
    }})();
    </script>
    '''