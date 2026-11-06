from typing import Optional
from app.core import settings, logger, call_gemini_with_retry

# Global variables for optional local model
explain_tokenizer = None
explain_model = None

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch

    def load_local_model():
        global explain_tokenizer, explain_model
        if explain_tokenizer is None:
            try:
                explain_tokenizer = AutoTokenizer.from_pretrained("MBZUAI/LaMini-Flan-T5-783M")
                explain_model = AutoModelForSeq2SeqLM.from_pretrained("MBZUAI/LaMini-Flan-T5-783M")
            except Exception:
                explain_tokenizer = False
                explain_model = False
except ImportError:
    def load_local_model():
        return False

def build_explanation_prompt(
    topic: str,
    level: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    """
    Constructs an adaptive concept explanation prompt based on selected level and learning style.
    """
    instructions = [
        "You are EduGenie, an expert educational concept explainer.",
        "Your task is to break down the concept clearly, engagingly, and accurately for students.",
        "",
        "General Guidelines:",
        "- Be accurate and pedagogically clear.",
        "- Avoid unhelpful jargon unless clearly explained with intuition.",
        "- Format code in markdown code blocks if the topic is technical.",
        "- Structure with clean markdown headings.",
    ]

    # Level adaptation
    if level:
        lvl = level.lower().strip()
        if lvl == "beginner":
            instructions.append(
                "- Level: BEGINNER. Use plain everyday vocabulary, intuitive analogies, and simple sentence structures. "
                "Focus on the core 'what' and 'why', with zero unexplained technical jargon."
            )
        elif lvl == "intermediate":
            instructions.append(
                "- Level: INTERMEDIATE. Balance conceptual clarity with technical accuracy. "
                "Explain underlying mechanisms, key relationships between components, and practical usage."
            )
        elif lvl == "advanced":
            instructions.append(
                "- Level: ADVANCED. Provide deep technical rigor, theoretical foundations, edge cases, "
                "formal definitions, and performance or architectural considerations."
            )
    else:
        instructions.append("- Level: Standard beginner-friendly explanation suitable for all students.")

    # Style adaptation
    if style:
        sty = style.lower().strip()
        if "simple" in sty:
            instructions.append(
                "- Learning Style: SIMPLE EXPLANATION. Keep it concise, high-level, and easy to read in 2 minutes."
            )
        elif "step" in sty:
            instructions.append(
                "- Learning Style: STEP-BY-STEP EXPLANATION. Structure the core explanation as progressive, "
                "numbered sequential steps (Step 1, Step 2, ...) from first principles to full concept."
            )
        elif "real-world" in sty or "example" in sty:
            instructions.append(
                "- Learning Style: REAL-WORLD EXAMPLE. Anchor the explanation around concrete, "
                "tangible applications in everyday life, industry, or nature."
            )
        elif "analogy" in sty:
            instructions.append(
                "- Learning Style: ANALOGY-BASED EXPLANATION. Use vivid, memorable analogies "
                "comparing this concept to familiar daily experiences to build lasting intuition."
            )
        elif "exam" in sty:
            instructions.append(
                "- Learning Style: EXAM-ORIENTED EXPLANATION. Structure for revision: formal definition, "
                "key points to write in an exam, common mistakes/pitfalls to avoid, and essential formulas/rules."
            )
    else:
        instructions.append("- Learning Style: Standard explanation with clear intuition and examples.")

    instructions.extend([
        "",
        "Response Structure (use standard Markdown headings):",
        "### 💡 Conceptual Overview",
        "[Clear definition and core intuition]",
        "",
        "### 🔍 Detailed Breakdown",
        "[In-depth explanation tailored to the requested level and style]",
        "",
        "### 🌟 Practical Example / Analogy",
        "[Relatable real-world scenario, code example, or analogy]",
        "",
        "### 📌 Key Takeaways",
        "[Essential bullet points for quick revision]",
        "",
        f"Topic to Explain: '{topic}'"
    ])

    return "\n".join(instructions)

def _get_curated_explanation_fallback(
    topic: str,
    level: Optional[str] = None,
    style: Optional[str] = None
) -> Optional[str]:
    """Provides curated offline explanations for core educational concepts."""
    t_lower = topic.lower()

    if "quantum" in t_lower:
        return """### 💡 Conceptual Overview
Quantum computing is a revolutionary computing paradigm that harnesses the fundamental laws of quantum mechanics to solve problems too complex for classical supercomputers.

### 🔍 Detailed Breakdown
1. **Classical Bits vs. Qubits:** While traditional computers use classical bits that are strictly 0 or 1, quantum computers use **qubits** that can exist in multiple states at the same time thanks to a principle called **superposition**.
2. **Entanglement:** Qubits can become entangled, meaning the state of one instantly influences another, allowing quantum systems to process vast combinations of possibilities simultaneously.
3. **Interference:** Quantum algorithms use interference to amplify correct answers and cancel out incorrect ones during computation.

### 🌟 Practical Example / Analogy
Imagine searching for a treasure in a giant maze:
- A classical computer sends an explorer down one path at a time. If it hits a dead end, it backtracks and tries the next path.
- A quantum computer acts like a wave of water filling the entire maze at once, exploring all paths simultaneously to locate the exit in a fraction of the time!

### 📌 Key Takeaways
- Qubits enable exponential computational parallelism via superposition and entanglement.
- Ideal for cryptography, molecular drug discovery, and complex optimization problems."""

    elif "binary search" in t_lower:
        return """### 💡 Conceptual Overview
The binary search algorithm is an efficient way to find the position of a target value within a **sorted list** of elements.

### 🔍 Detailed Breakdown
- **Prerequisite:** The input list must already be in sorted order.
- **How it works:**
  1. Find the middle element of the current range.
  2. If the target equals the middle element, the search succeeds.
  3. If the target is smaller, repeat the search exclusively on the left half.
  4. If the target is larger, repeat the search exclusively on the right half.
  5. Repeat until found or until the range has length zero.

### 🌟 Practical Example / Analogy
Think of searching for a word in a printed physical dictionary:
You open to the exact middle. If your word starts with "P" and the page is "M", you know "P" comes after "M", so you discard the entire first half of the book and repeat on the remaining half. You never check word-by-word from page 1!

```python
def binary_search(sorted_arr, target):
    low = 0
    high = len(sorted_arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if sorted_arr[mid] == target:
            return mid
        elif sorted_arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
```

### 📌 Key Takeaways
- Time Complexity: $O(\\log n)$ — searches 1,000,000 items in ~20 comparisons!
- Always requires sorted input data."""

    elif "photosynthesis" in t_lower:
        return """### 💡 Conceptual Overview
Photosynthesis is the biochemical process by which green plants, algae, and certain bacteria convert light energy into chemical energy stored in glucose.

### 🔍 Detailed Breakdown
- **Inputs:** Sunlight (energy source), Water ($H_2O$ absorbed by roots), and Carbon Dioxide ($CO_2$ absorbed through stomata).
- **Process:** Chlorophyll molecules inside chloroplasts absorb photons and trigger two stages:
  1. *Light-Dependent Reactions:* Thylakoids capture solar energy and split water, releasing oxygen gas.
  2. *Calvin Cycle (Light-Independent):* Energy carries carbon dioxide into organic sugar molecules (glucose).
- **Outputs:** Glucose ($C_6H_{12}O_6$) and Oxygen ($O_2$).

### 🌟 Practical Example / Analogy
Think of a plant leaf as a solar-powered bakery:
- Sunlight is the solar electricity powering the ovens.
- Water and carbon dioxide are the flour and yeast.
- Glucose is the delicious bread that nourishes the plant.
- Fresh oxygen is the wholesome air vented outside for animals to breathe!

### 📌 Key Takeaways
- Equation: $6\\text{CO}_2 + 6\\text{H}_2\\text{O} + \\text{Light} \\rightarrow \\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2$.
- Photosynthesis is the primary engine fueling Earth's oxygen atmosphere and food webs."""

    return None

def explain_topic(
    topic: str,
    level: Optional[str] = None,
    style: Optional[str] = None,
) -> str:
    """
    Explains educational concepts with adaptive levels and learning styles.
    Uses local model if available, otherwise Google Gemini API with timeout and bounded retries.
    """
    if not topic or not isinstance(topic, str) or not topic.strip():
        return "Please provide a topic to explain."

    clean_topic = topic.strip()
    if len(clean_topic) > 1000:
        clean_topic = clean_topic[:1000]

    # 1. Try local LaMini-Flan-T5 model if available
    if explain_tokenizer and explain_model and explain_tokenizer is not False:
        try:
            input_text = f"Explain the concept of '{clean_topic}' in a simple and clear way for a school student."
            inputs = explain_tokenizer(input_text, return_tensors="pt")
            outputs = explain_model.generate(
                **inputs,
                max_new_tokens=150,
                temperature=0.7,
                top_k=50,
                top_p=0.95,
                do_sample=True
            )
            explanation = explain_tokenizer.decode(outputs[0], skip_special_tokens=True)
            if explanation and len(explanation) > 10:
                return explanation
        except Exception as exc:
            logger.warning("Local explanation model failed: %s", type(exc).__name__)

    # 2. Build structured prompt with level and style parameters
    prompt = build_explanation_prompt(clean_topic, level=level, style=style)

    # 3. Call Gemini API with bounded timeouts and retries
    ai_response = call_gemini_with_retry(prompt)
    if ai_response and len(ai_response.strip()) > 20:
        return ai_response.strip()

    # 4. Check curated educational reference bank
    curated = _get_curated_explanation_fallback(clean_topic, level=level, style=style)
    if curated:
        return curated

    # 5. Clean, relevant fallback when offline
    return f"""### ⚠️ Live AI Explanation Unavailable

EduGenie could not generate a live AI explanation for: **"{clean_topic}"** at this moment.

### 💡 Why Did This Occur?
The AI tutoring service is temporarily unreachable, timed out, or operating in offline mode.

### 🔍 Next Steps:
1. **Retry Your Request:** Click "Explain" in a few moments to send the request again.
2. **Select Level & Style:** Try picking a specific level (Beginner, Intermediate, Advanced) or style (Step-by-step, Analogy) for tailored explanations.
3. **Verify Settings:** If running locally, check that `GEMINI_API_KEY` is provided in your `.env` file with active quota.

### 📌 Summary
EduGenie connects to Google Gemini AI to provide dynamic explanations for any topic, and includes offline reference guides for core curriculum concepts."""
