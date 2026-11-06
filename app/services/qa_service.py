from typing import Optional, List, Dict, Any, Generator
import re
from app.core import settings, logger, call_gemini_with_retry, call_gemini_stream
from app.services.retrieval_service import retrieval_service

def build_qa_prompt(
    question: str,
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    grade_level: Optional[str] = None,
    language: Optional[str] = None,
    explanation_style: Optional[str] = None,
    response_length: Optional[str] = "short",
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Constructs an intelligent, natural conversational educational prompt for EduGenie AI tutor.
    Supports universal subjects, multi-turn follow-ups, language adaptation (English, Tamil, Tanglish),
    grade-level tailoring, and intelligent answer-length control (short by default, normal, detailed).
    """
    q_lower = question.lower()
    detail_keywords = [
        "explain in detail",
        "in detail",
        "step by step",
        "step-by-step",
        "full explanation",
        "detailed explanation",
        "in-depth",
        "elaborate",
        "deep dive",
        "thorough explanation",
    ]
    student_asked_detail = any(kw in q_lower for kw in detail_keywords)

    req_len = (response_length or "short").lower().strip()
    if req_len not in ("short", "normal", "detailed"):
        req_len = "short"

    if student_asked_detail or (explanation_style and "detailed" in explanation_style.lower()):
        effective_length = "detailed"
    else:
        effective_length = req_len

    instructions = [
        "You are EduGenie, an intelligent, student-friendly AI learning companion and conversational tutor.",
        "Your mission is to provide accurate, structured, adaptive, and easy-to-understand educational explanations,",
        "inspired by the natural, helpful question-answering experience of ChatGPT.",
        "",
        "Core Pedagogical Guidelines:",
        "- Answer clearly, directly, and concisely without fluff or unnecessary filler introductions.",
        "- Explain difficult concepts in beginner-friendly language with intuitive reasoning.",
        "- Break complex topics into logical, progressive steps.",
        "- Use relatable, concrete examples relevant to students (daily life scenarios, intuitive analogies, or well-commented code).",
        "- For programming questions, always format code in standard markdown code blocks with the language identifier (e.g. ```python, ```html, ```javascript) and explain the logic.",
        "- For mathematics, format formulas clearly and explain each calculation step.",
        "- Support science, technology, engineering, mathematics, languages, social studies, humanities, homework, and general academic subjects.",
        "- Accuracy and Uncertainty: Distinguish verified facts from assumptions. If uncertain, if the question is ambiguous, or if verified facts are unavailable, clearly admit uncertainty instead of inventing facts or hallucinating.",
        "- Never fabricate citations, URLs, search results, or live web data. If current information is unavailable, acknowledge the limitation honestly.",
        "- Student Safety & Privacy: Do not request or store passwords, precise personal addresses, or sensitive personal data. Maintain respectful, safe, and supportive educational boundaries.",
        "- Avoid generic, repetitive, or irrelevant responses.",
    ]

    # Universal Brevity & Quality Guidelines
    instructions.extend([
        "",
        "Intelligent Conciseness & Anti-Fluff Directives:",
        "- NO FILLER / NO REPETITION: Do NOT repeat the question. Never start with conversational filler (e.g. 'Sure!', 'I would be happy to explain', 'Great question!'). Never end with boilerplate sign-offs (e.g. 'I hope this helps! Let me know if you have any questions'). Jump directly into the answer.",
        "- SCHOOL STUDENTS: Use clear, simple, age-appropriate language suitable for school students.",
        "- ACCURACY & SAFETY FIRST: Never compromise correctness, essential mathematical precision, scientific truth, or safety information just to make answers shorter. Brevity must never sacrifice accuracy.",
        "- DEFINITIONS: Provide a clear, simple 1-2 sentence definition and at most ONE short example if needed.",
        "- MATHS & SCIENCE: Give the answer with only the essential calculation steps. Show more steps only when requested.",
        "- CODING QUESTIONS: Provide a short explanation (1-2 sentences) and the necessary code block only. Avoid unnecessary theory, history, or setup fluff.",
        "- FOLLOW-UP QUESTIONS: When answering a follow-up question within an ongoing conversation, answer only the specific follow-up instead of repeating the entire previous explanation.",
    ])

    # Dynamic Length Mode Control
    if effective_length == "short":
        instructions.extend([
            "",
            "Answer Length Preference: SHORT (DEFAULT):",
            "- Default response: Give a direct, concise answer in 2 to 5 sentences total.",
            "- Simple questions: Answer in 1 to 3 sentences.",
            "- Deliver the core answer immediately without unnecessary preamble, padding, or multi-heading essay format.",
            "- Keep math and science answers strictly to essential working and the final result.",
        ])
    elif effective_length == "normal":
        instructions.extend([
            "",
            "Answer Length Preference: NORMAL (BALANCED):",
            "- Provide a balanced response in 1-2 focused paragraphs (5 to 10 sentences).",
            "- Include direct answer, brief explanation, and a relatable example.",
        ])
    else:  # detailed
        instructions.extend([
            "",
            "Answer Length Preference: DETAILED (FULL EXPLANATION):",
            "- The student explicitly requested a detailed or step-by-step explanation.",
            "- Provide a comprehensive, in-depth breakdown covering mechanisms, detailed steps, and key insights.",
        ])

    # Grade level adaptation
    if grade_level:
        gl = grade_level.lower()
        if "higher" in gl or "college" in gl or any(f"grade {i}" in gl for i in range(11, 13)) or "class 11" in gl or "class 12" in gl:
            instructions.append("- Grade Level: HIGHER SECONDARY / COLLEGE (Grades 11-12+). Provide theoretical rigor, mechanism depth, analytical precision, and advanced problem-solving techniques.")
        elif "primary" in gl or "elementary" in gl or any(f"grade {i}" in gl for i in range(1, 6)) or "class 1" in gl or "class 5" in gl:
            instructions.append("- Grade Level: PRIMARY (Grades 1-5). Use simple everyday vocabulary, warm friendly tone, fun analogies, and short clear sentences.")
        elif "middle" in gl or any(f"grade {i}" in gl for i in range(6, 9)) or "class 6" in gl or "class 8" in gl:
            instructions.append("- Grade Level: MIDDLE SCHOOL (Grades 6-8). Balance foundational concept clarity with structured explanations and relatable examples.")
        elif "high" in gl or any(f"grade {i}" in gl for i in range(9, 11)) or "class 9" in gl or "class 10" in gl:
            instructions.append("- Grade Level: HIGH SCHOOL (Grades 9-10). Use standard curriculum depth, formal terminology, formula breakdowns, and exam-relevant clarity.")
        else:
            instructions.append(f"- Student Grade Level: Tailor explanation depth and tone appropriately to {grade_level.upper()}.")

    # Difficulty level adaptation
    if difficulty:
        instructions.append(f"- Student Level: Tailor your vocabulary, depth, and pacing to a {difficulty.upper()} student level.")

    # Subject focus
    if subject:
        instructions.append(f"- Academic Subject: Focus explanations and examples within the field of {subject}.")

    # Language adaptation (Tamil, Tanglish, English)
    is_tamil_requested = (language and "tamil" in language.lower() and "tanglish" not in language.lower()) or "in tamil" in q_lower or "தமிழில்" in question
    is_tanglish_requested = (language and "tanglish" in language.lower()) or "in tanglish" in q_lower or "tanglish" in q_lower

    if is_tamil_requested:
        instructions.append("- Preferred Language: TAMIL (தமிழ்). Respond in clean, polite, and educational Tamil script, explaining concepts accurately using standard Tamil educational terminology.")
    elif is_tanglish_requested:
        instructions.append("- Preferred Language: TANGLISH. Respond in natural, conversational Tanglish (spoken Tamil written phonetically in the English/Latin alphabet, e.g. 'Photosynthesis na thavarangal sunlight use panni food prepare panra process...').")
    elif language and language.lower() == "english":
        instructions.append("- Preferred Language: ENGLISH. Respond in fluent, natural English.")

    # Response Style adaptation
    if explanation_style:
        es = explanation_style.lower()
        if "simple" in es:
            instructions.append("- Response Style: SIMPLE. Focus on the core intuition in plain everyday words without overwhelming technical jargon.")
        elif "step" in es:
            instructions.append("- Response Style: STEP-BY-STEP. Present numbered sequential steps and logical progression.")
        elif "detailed" in es:
            instructions.append("- Response Style: DETAILED. Provide comprehensive theoretical and practical exploration with depth.")
        elif "analogy" in es:
            instructions.append("- Response Style: ANALOGY-BASED. Center the explanation around an intuitive, memorable real-life analogy.")
        elif "exam" in es:
            instructions.append("- Response Style: EXAM-ORIENTED. Highlight high-yield definitions, key formulas, common student pitfalls, and revision points.")

    # Structural Guidelines
    instructions.extend([
        "",
        "Conversational Response Structure Guidelines:",
        "For comprehensive concept explanations or new topics, structure your response clearly using standard Markdown headings:",
        "### 🎯 Direct Answer",
        "[1-2 concise sentences directly answering the question]",
        "",
        "### 💡 Simple Explanation",
        "[Clear, step-by-step conceptual explanation in beginner-friendly language]",
        "",
        "### 🔍 Relatable Example",
        "[A practical, student-friendly example, real-world application, or code snippet]",
        "",
        "### 📌 Key Takeaway",
        "[1-2 bullet points summarizing the most critical concept to remember]",
        "",
        "### ❓ Follow-Up Question",
        "[An engaging question to check the student's understanding or spark further curiosity]",
        "",
        "Structural Nuance: For SHORT mode (default), deliver the Direct Answer directly and concisely in 2-5 sentences (or 1-3 sentences for simple questions/definitions) without padding. The full 5-section breakdown (Direct Answer, Simple Explanation, Relatable Example, Key Takeaway, Follow-Up Question) should be used when the student requests DETAILED mode or asks 'explain in detail' / 'step by step'.",
    ])

    prompt_parts = ["\n".join(instructions), ""]

    # History formatting for multi-turn dialogue
    if history and isinstance(history, list) and len(history) > 0:
        prompt_parts.append("Previous Conversation History:")
        for turn in history[-8:]:
            role_label = "Student" if turn.get("role") in ("user", "student") else "EduGenie Tutor"
            content = turn.get("content", "").strip()
            if content:
                if len(content) > 1500:
                    content = content[:1500] + "..."
                prompt_parts.append(f"{role_label}: {content}")
        prompt_parts.append("")
        prompt_parts.append(f"Student Follow-Up Question: {question}")
        prompt_parts.append("Answer this follow-up question in context of the previous conversation while adhering to the response structure and guidelines.")
    else:
        prompt_parts.append(f"Question to Answer: {question}")

    return "\n".join(prompt_parts)

def _get_curated_qa_fallback(question: str, response_length: str = "short") -> Optional[str]:
    """Returns curated educational responses adapted for short default or detailed requests."""
    q_lower = question.lower()
    detail_keywords = [
        "explain in detail", "in detail", "step by step", "step-by-step",
        "full explanation", "detailed explanation", "in-depth", "elaborate"
    ]
    is_detailed = (response_length == "detailed") or any(kw in q_lower for kw in detail_keywords)

    if "largest ocean" in q_lower:
        if not is_detailed:
            return (
                "The Pacific Ocean is the largest and deepest ocean on Earth, covering more than 63 million "
                "square miles (over 165 million square kilometers). It accounts for more than 30% of the Earth's "
                "total surface area, making it larger than all the continents combined. It also contains the deepest point "
                "on our planet, the Mariana Trench."
            )
        return """### 🎯 Direct Answer
The Pacific Ocean is the largest and deepest ocean on Earth, covering more than 63 million square miles (over 165 million square kilometers).

### 💡 Simple Explanation
The Pacific Ocean accounts for more than 30% of the Earth's total surface area—which means it is larger than all of the Earth's land masses combined! It stretches from the Arctic in the north to Antarctica in the south, between Asia and Australia to the west and the Americas to the east.

### 🔍 Relatable Example
Imagine fitting all seven continents—Asia, Africa, North America, South America, Antarctica, Europe, and Australia—together like puzzle pieces. They would all easily fit inside the Pacific Ocean basin with room to spare!

### 📌 Key Takeaway
- The Pacific Ocean is the planet's largest body of water and contains the deepest known point on Earth, the Mariana Trench (Challenger Deep at ~11,000 meters).

### ❓ Follow-Up Question
Would you like to know how tectonic plates create the famous "Ring of Fire" around the Pacific Ocean?"""

    elif "pythagoras" in q_lower:
        if not is_detailed:
            return (
                "The Pythagoras Theorem states that in any right-angled triangle, the square of the hypotenuse ($c$) "
                "is equal to the sum of the squares of the other two sides ($a$ and $b$): $a^2 + b^2 = c^2$. "
                "For essential calculation: if side $a = 3$ and side $b = 4$, then $c^2 = 3^2 + 4^2 = 25$, giving hypotenuse $c = 5$."
            )
        return """### 🎯 Direct Answer
The Pythagoras Theorem states that in any right-angled triangle, the square of the hypotenuse is equal to the sum of the squares of the other two sides ($a^2 + b^2 = c^2$).

### 💡 Simple Explanation
In a right-angled triangle (a triangle with one 90-degree angle):
1. The **hypotenuse** ($c$) is the longest side, directly opposite the right angle.
2. The other two perpendicular sides are called $a$ and $b$.
3. If you create squares on each of the three sides, the area of the largest square on the hypotenuse equals the combined area of the squares on the other two sides.

### 🔍 Relatable Example
If a ladder is leaned against a wall reaching 4 meters high ($a = 4$), and the bottom of the ladder is placed 3 meters away from the wall ($b = 3$):
$$c^2 = 3^2 + 4^2 = 9 + 16 = 25 \\implies c = 5\\text{ meters}$$
So, the ladder must be 5 meters long!

### 📌 Key Takeaway
- Formula: $a^2 + b^2 = c^2$ (only applies to right-angled triangles where $c$ is the hypotenuse).

### ❓ Follow-Up Question
Would you like to try solving a quick practice triangle problem together?"""

    elif "photosynthesis" in q_lower:
        if not is_detailed:
            return (
                "Photosynthesis is the process by which green plants convert sunlight, water, and carbon dioxide into "
                "glucose (energy) and oxygen ($6\\text{CO}_2 + 6\\text{H}_2\\text{O} + \\text{Light} \\rightarrow \\text{C}_6\\text{H}_{12}\\text{O}_6 + \\text{O}_2$). "
                "Chlorophyll in leaves captures sunlight while roots absorb water from the soil to produce plant nutrients. "
                "For example, a plant leaf acts like a solar-powered kitchen that feeds the plant and produces clean oxygen for us to breathe."
            )
        return """### 🎯 Direct Answer
Photosynthesis is the biological process by which green plants, algae, and some bacteria convert sunlight, water, and carbon dioxide into glucose (energy) and oxygen.

### 💡 Simple Explanation
Plants are nature's solar-powered food factories:
1. **Absorb Sunlight:** Chlorophyll in plant leaves traps light energy from the sun.
2. **Take in Water & CO₂:** Roots pull water from soil, while tiny leaf pores (stomata) absorb carbon dioxide from air.
3. **Produce Food & Oxygen:** Chemical reactions convert these inputs into glucose (sugar for plant growth) and release oxygen gas into the atmosphere.

### 🔍 Relatable Example
Think of a plant leaf as a kitchen: sunlight is the oven heat, water and carbon dioxide are the raw ingredients, glucose is the baked bread, and clean oxygen is the refreshing aroma released into the room!

### 📌 Key Takeaway
- Chemical Equation: $6\\text{CO}_2 + 6\\text{H}_2\\text{O} + \\text{Light} \\rightarrow \\text{C}_6\\text{H}_{12}\\text{O}_6 + \\text{O}_2$.
- Plants provide both the oxygen we breathe and the base of almost all Earth food chains.

### ❓ Follow-Up Question
What role do you think chloroplasts and chlorophyll play in giving leaves their green color?"""

    elif "binary search" in q_lower:
        if not is_detailed:
            return (
                "Binary search is an algorithm that finds a target in a sorted list by repeatedly dividing the search space in half. "
                "For example, like opening a dictionary to the middle, it checks the center element and discards the half where the target cannot be. "
                "Its time complexity is $O(\\log n)$, making it much faster than linear search."
            )
        return """### 🎯 Direct Answer
Binary search is an efficient search algorithm that finds the position of a target value within a sorted list by repeatedly dividing the search interval in half.

### 💡 Simple Explanation
1. Check the middle element of the sorted list.
2. If the middle element matches your target, you are done!
3. If your target is smaller, eliminate the upper half and search only the lower half.
4. If your target is larger, eliminate the lower half and search only the upper half.
5. Repeat until found or until the interval is empty.

### 🔍 Relatable Example
When looking up a word in a physical dictionary, you don't read page 1, 2, 3... You open to the middle, see if your word comes before or after that letter, and flip halfway into the correct side. That is binary search in action!

### 📌 Key Takeaway
- Requires the data to be **sorted**.
- Time Complexity: $O(\\log n)$, making it exponentially faster than linear search ($O(n)$).

### ❓ Follow-Up Question
Why doesn't binary search work on an unsorted array?"""

    return None

def answer_question_with_gemini(
    question: str,
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    grade_level: Optional[str] = None,
    language: Optional[str] = None,
    explanation_style: Optional[str] = None,
    response_length: Optional[str] = "short",
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Answers educational questions with natural, adaptive pedagogical explanations,
    supporting universal subjects, grade levels, languages (English/Tamil/Tanglish),
    answer-length control (short, normal, detailed), and follow-up turns.
    """
    if not question or not isinstance(question, str) or not question.strip():
        return "Please ask a valid question."

    clean_question = question.strip()
    if len(clean_question) > 5000:
        clean_question = clean_question[:5000]

    # 1. Build structured conversational prompt with intelligent length control
    prompt = build_qa_prompt(
        clean_question,
        subject=subject,
        difficulty=difficulty,
        grade_level=grade_level,
        language=language,
        explanation_style=explanation_style,
        response_length=response_length,
        history=history,
    )

    # 2. Call Gemini API with strict timeouts and bounded retries
    ai_response = call_gemini_with_retry(prompt)
    if ai_response and len(ai_response.strip()) > 15:
        return ai_response.strip()

    # 3. Check curated educational reference bank with response length preference
    curated = _get_curated_qa_fallback(clean_question, response_length=response_length or "short")
    if curated:
        return curated

    # 4. Context-aware, informative fallback when AI is unavailable
    return f"""### ⚠️ AI Tutor Temporarily Unavailable

We could not generate a live AI answer for your question: **"{clean_question}"** at this moment.

### 💡 What Happened?
The AI tutor service is currently unreachable, timed out, or operating offline.

### 🔍 What You Can Do Next:
1. **Try Again:** Click "Get Answer" in a few moments to retry your request.
2. **Refine Your Question:** Add specific context (such as subject: *Mathematics* or *Computer Science*) to help focus the response.
3. **Verify Settings:** If running in development, ensure your `GEMINI_API_KEY` is configured in your `.env` file with active quota.

### 📌 Key Takeaway
EduGenie provides verified live tutoring when connected to Google Gemini AI, and curated answers for core curriculum concepts when offline."""

def answer_question_stream(
    question: str,
    subject: Optional[str] = None,
    difficulty: Optional[str] = None,
    grade_level: Optional[str] = None,
    language: Optional[str] = None,
    explanation_style: Optional[str] = None,
    response_length: Optional[str] = "short",
    history: Optional[List[Dict[str, str]]] = None,
) -> Generator[str, None, None]:
    """
    Streams educational answers chunk-by-chunk in real-time.
    Supports answer-length control and falls back gracefully if streaming is unavailable.
    """
    if not question or not isinstance(question, str) or not question.strip():
        yield "Please ask a valid question."
        return

    clean_question = question.strip()
    if len(clean_question) > 5000:
        clean_question = clean_question[:5000]

    prompt = build_qa_prompt(
        clean_question,
        subject=subject,
        difficulty=difficulty,
        grade_level=grade_level,
        language=language,
        explanation_style=explanation_style,
        response_length=response_length,
        history=history,
    )

    yielded_any = False
    try:
        for chunk in call_gemini_stream(prompt):
            if chunk:
                yielded_any = True
                yield chunk
    except Exception as exc:
        logger.warning("Stream generation encountered notice: %s", type(exc).__name__)

    if not yielded_any:
        # Fall back to synchronous response or curated answer
        full_answer = answer_question_with_gemini(
            clean_question,
            subject=subject,
            difficulty=difficulty,
            grade_level=grade_level,
            language=language,
            explanation_style=explanation_style,
            response_length=response_length,
            history=history,
        )
        yield full_answer

def generate_suggested_followups(question: str, answer: str) -> List[str]:
    """Generates 2-3 intuitive follow-up suggestions based on the topic."""
    q_lower = question.lower()
    if "photo" in q_lower or "cell" in q_lower or "dna" in q_lower or "plant" in q_lower:
        return [
            "Explain the chemical equation in simple steps",
            "Give a real-world everyday analogy",
            "What happens if sunlight or water is missing?",
        ]
    elif any(term in q_lower for term in ("code", "python", "loop", "function", "array", "binary", "algorithm")):
        return [
            "Show a working code example with comments",
            "What is the time complexity and performance?",
            "What are common bugs to avoid?",
        ]
    elif any(term in q_lower for term in ("pythagoras", "math", "triangle", "equation", "solve", "fraction", "formula")):
        return [
            "Show step-by-step arithmetic working",
            "Let's solve another practice problem together",
            "How is this used in architecture and real life?",
        ]
    elif any(term in q_lower for term in ("tamil", "tanglish", "தமிழ்")):
        return [
            "Innum simple-ah explain panunga",
            "Oru real-life example kudunga",
            "English-la key terms enna?",
        ]
    else:
        return [
            "Can you explain this more simply?",
            "Give another real-world example",
            "How do I revise this for exams?",
        ]
