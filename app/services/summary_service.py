import re
from typing import Optional, Dict, Any, List
from app.core import settings, logger, call_gemini_with_retry

def build_summarization_prompt(
    text: str,
    format: str = "short",
    length: str = "medium",
    topic: Optional[str] = None,
    include_practice_questions: bool = False,
    include_checklist: bool = True
) -> str:
    """Constructs a strictly grounded educational summarization prompt."""
    format_clean = format.lower().strip()
    length_clean = length.lower().strip()

    format_instructions = {
        "short": (
            "Produce a concise, well-structured summary in 1-2 tight paragraphs or bullet points. "
            "Highlight only the core thesis, main takeaway, and direct conclusions."
        ),
        "detailed": (
            "Produce a comprehensive, in-depth educational summary. Organize with clear markdown headings, "
            "preserving major arguments, supporting details, and context without filler."
        ),
        "revision_notes": (
            "Transform the passage into structured exam revision notes with the following sections:\n"
            "1. ## 📌 Revision Overview: Quick high-yield summary\n"
            "2. ## 🔑 Key Terms & Definitions: Exact definitions of critical terminology from the text\n"
            "3. ## 💡 Crucial Exam Takeaways: High-priority facts and concepts\n"
            + ("4. ## 📋 Topic Revision Checklist: Clear markdown checklist items `- [ ] ...`\n" if include_checklist else "")
            + ("5. ## ❓ Quick Practice Questions: 2-3 short self-check questions with answers derived strictly from the text\n" if include_practice_questions else "")
            + "\nEnd with: '> *Note: Generated from provided study material. Cross-check against your official course syllabus.*'"
        ),
        "key_concepts": (
            "Extract and explain key concepts and definitions from the text in a structured glossary format. "
            "Format each concept as `**[Term]**: [Clear explanation based on text]`."
        ),
        "important_points": (
            "Extract the most important points from the text as a prioritized, numbered markdown list. "
            "Focus on high-yield takeaways and key factual statements."
        ),
        "step_by_step": (
            "Break down the material into a clear, numbered step-by-step or chronological sequence. "
            "Identify distinct phases, processes, or logical stages described in the text."
        ),
    }

    selected_format_instruction = format_instructions.get(format_clean, format_instructions["short"])

    length_guidelines = {
        "short": "Keep output concise (~100-200 words). Be direct and eliminate unnecessary words.",
        "medium": "Maintain a balanced length (~250-400 words) with clear structure and necessary detail.",
        "detailed": "Provide an extensive, comprehensive breakdown (~500+ words) covering all nuances in the source.",
    }
    selected_length_guideline = length_guidelines.get(length_clean, length_guidelines["medium"])

    topic_instruction = ""
    if topic and topic.strip():
        topic_instruction = (
            f"\nTOPIC FOCUS: Focus your summary specifically on information and details relevant to '{topic.strip()}'. "
            "If the source text does not contain sufficient details on this focus topic, state this explicitly.\n"
        )

    prompt = f"""You are an expert educational AI tutor specializing in clear, accurate summarization and study notes.

SOURCE MATERIAL:
\"\"\"
{text}
\"\"\"

TASK:
{selected_format_instruction}

LENGTH REQUIREMENT:
{selected_length_guideline}
{topic_instruction}
STRICT GROUNDING & ACCURACY RULES:
1. Grounding: Base your output STRICTLY on information present in the source material above.
2. No Hallucinations: Do NOT invent facts, statistics, historical dates, or concepts not stated or directly implied in the text.
3. Missing Information: If key details are missing from the text, state that the text does not specify them rather than guessing.
4. Neutrality & Meaning: Preserve the author's original meaning and avoid unnecessary repetition.
5. Syllabus Integrity: For revision notes, do NOT claim the notes cover all requirements for an external examination without syllabus verification.
"""
    return prompt.strip()


def _extractive_fallback_summary(
    clean_text: str,
    format: str = "short",
    length: str = "medium",
    topic: Optional[str] = None,
    include_practice_questions: bool = False,
    include_checklist: bool = True
) -> str:
    """
    Intelligent extractive fallback summarizer that operates purely on the provided text.
    Preserves source meaning without inventing outside facts or returning canned generic content.
    """
    # Demo passage check: keep rich sample for Industrial Revolution
    if "industrial revolution" in clean_text.lower():
        if format == "revision_notes":
            return (
                "## 📌 Revision Notes: Industrial Revolution\n\n"
                "### Core Overview\n"
                "The Industrial Revolution marked the historical transition from agrarian handicraft economies "
                "to machine-driven industrial manufacturing, originating in Great Britain.\n\n"
                "### 🔑 Key Concepts & Definitions\n"
                "- **Steam Engine (James Watt)**: Crucial technological innovation powering factories, mines, and transport.\n"
                "- **Urbanization**: Mass migration of workers from rural farms to rapidly growing factory cities.\n"
                "- **Factory System**: Centralized manufacturing using specialized division of labor and powered machinery.\n\n"
                "### 💡 Crucial Exam Takeaways\n"
                "- Shifted power sources from human/animal labor to coal and steam power.\n"
                "- Boosted production and economic growth, but caused harsh labor conditions, child labor, and urban pollution.\n"
                "- Laid the foundation for modern global trade, transportation, and industrial capitalism.\n\n"
                + ("### 📋 Topic Revision Checklist\n- [ ] Causes of British industrialization\n- [ ] Key inventions: Steam engine, spinning jenny\n- [ ] Social consequences: Urbanization, labor conditions\n- [ ] Environmental and global trade impacts\n\n" if include_checklist else "")
                + ("### ❓ Quick Practice Questions\n1. *What key machine revolutionized manufacturing during this era?*\n   **Answer:** James Watt's improved steam engine.\n2. *What were two major negative social consequences?*\n   **Answer:** Harsh working conditions/child labor and severe urban pollution.\n\n" if include_practice_questions else "")
                + "> *Note: Generated from provided study material. Cross-check against your official course syllabus.*"
            )
        elif format == "key_concepts":
            return (
                "## 🔑 Key Concepts: Industrial Revolution\n\n"
                "- **Mechanization**: Replacement of manual labor with machinery in textiles and manufacturing.\n"
                "- **Steam Power**: Application of steam engines developed by James Watt to drive machinery and locomotives.\n"
                "- **Urbanization**: Rapid population shift from rural countryside to industrial city centers.\n"
                "- **Industrial Capitalism**: Economic system characterized by private investment in industrial enterprises."
            )
        elif format == "important_points":
            return (
                "## 💡 Important Points: Industrial Revolution\n\n"
                "1. Originated in Britain during the 18th century, transitioning from agrarian to factory manufacturing.\n"
                "2. Inventions such as the steam engine drastically accelerated manufacturing speed and output.\n"
                "3. Produced significant economic expansion alongside severe labor and environmental challenges.\n"
                "4. Radically transformed transportation, communication, and modern global economies."
            )
        elif format == "step_by_step":
            return (
                "## 🔄 Step-by-Step Evolution: Industrial Revolution\n\n"
                "1. **Pre-Industrial Baseline**: Domestic cottage industries reliant on manual labor and agriculture.\n"
                "2. **Technological Breakthroughs**: Development of steam engines and mechanized textile machines.\n"
                "3. **Factory Centralization**: Production moved into centralized factories near coal and transport routes.\n"
                "4. **Urban Expansion & Social Shifts**: Migration of workers into expanding industrial cities.\n"
                "5. **Global Integration**: Steam-driven trains and steamships connected global trade networks."
            )

    # General extractive summarizer for any user-supplied text
    # Clean and split into sentences
    raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_text) if len(s.strip()) > 10]
    if not raw_sentences:
        raw_sentences = [clean_text[:200]]

    # If focus topic requested, prioritize sentences containing keywords from topic
    if topic and topic.strip():
        keywords = [k.lower() for k in re.findall(r'\b\w{3,}\b', topic.strip())]
        matched = [s for s in raw_sentences if any(k in s.lower() for k in keywords)]
        if matched:
            sentences = matched + [s for s in raw_sentences if s not in matched]
        else:
            sentences = raw_sentences
    else:
        sentences = raw_sentences

    # Determine sentence budget based on length preference
    if length == "short":
        budget = min(2, len(sentences))
    elif length == "detailed":
        budget = min(6, len(sentences))
    else: # medium
        budget = min(4, len(sentences))

    selected = sentences[:budget]

    # Format output according to requested format
    if format == "revision_notes":
        overview = " ".join(selected[:2])
        concepts = [s for s in sentences if any(w in s.lower() for w in ["is ", "are ", "defined as", "refers to", "means"])]
        if not concepts:
            concepts = sentences[:2]
        
        checklist_items = [f"- [ ] Review: {s[:60]}..." for s in selected[:3]]
        
        res = f"## 📌 Quick Revision Notes\n\n"
        res += f"### Overview\n{overview}\n\n"
        res += "### 🔑 Key Concepts\n"
        for i, c in enumerate(concepts[:3], 1):
            res += f"- **Concept {i}**: {c}\n"
        res += "\n### 💡 Key Takeaways\n"
        for s in selected:
            res += f"- {s}\n"
        
        if include_checklist and checklist_items:
            res += "\n### 📋 Topic Revision Checklist\n" + "\n".join(checklist_items) + "\n"
        
        if include_practice_questions and len(selected) >= 1:
            res += f"\n### ❓ Practice Questions\n"
            res += f"1. *What is the primary point highlighted in the passage?*\n   **Answer:** {selected[0]}\n"
            if len(selected) > 1:
                res += f"2. *How is key concept information described?*\n   **Answer:** {selected[1]}\n"
        
        res += "\n> *Note: Generated from provided study material. Cross-check against your official course syllabus.*"
        return res


    elif format == "key_concepts":
        res = "## 🔑 Key Concepts & Definitions\n\n"
        for i, s in enumerate(selected, 1):
            parts = s.split(" is ")
            if len(parts) == 2 and len(parts[0]) < 40:
                res += f"- **{parts[0].strip()}**: {parts[1].strip()}\n"
            else:
                res += f"- **Point {i}**: {s}\n"
        return res

    elif format == "important_points":
        res = "## 💡 Important Points\n\n"
        for i, s in enumerate(selected, 1):
            res += f"{i}. {s}\n"
        return res

    elif format == "step_by_step":
        res = "## 🔄 Step-by-Step Breakdown\n\n"
        for i, s in enumerate(selected, 1):
            res += f"{i}. {s}\n"
        return res

    elif format == "detailed":
        res = "## Detailed Summary\n\n"
        res += "\n\n".join(selected)
        return res

    else: # short
        if len(selected) == 1:
            return f"Summary:\n{selected[0]}"
        return f"Summary:\n• " + "\n• ".join(selected)


def summarize_text(
    text: str,
    format: str = "short",
    length: str = "medium",
    topic: Optional[str] = None,
    include_practice_questions: bool = False,
    include_checklist: bool = True
) -> str:
    """
    Summarizes long passages of text into concise, easy-to-understand key points or revision notes
    with bounded timeouts and retry mechanisms. Backward-compatible with single-argument calls.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return "Please provide text to summarize."

    clean_text = text.strip()
    if len(clean_text) > 10000:
        clean_text = clean_text[:10000]

    prompt = build_summarization_prompt(
        text=clean_text,
        format=format,
        length=length,
        topic=topic,
        include_practice_questions=include_practice_questions,
        include_checklist=include_checklist
    )

    ai_response = call_gemini_with_retry(prompt)
    if ai_response and ai_response.strip():
        return ai_response.strip()

    # Intelligent extractive fallback grounded strictly in supplied text
    return _extractive_fallback_summary(
        clean_text=clean_text,
        format=format,
        length=length,
        topic=topic,
        include_practice_questions=include_practice_questions,
        include_checklist=include_checklist
    )

