document.addEventListener('DOMContentLoaded', () => {
    // 1. Tab Switching Logic
    const tabBtns = document.querySelectorAll('.tab-btn');
    const featureCards = document.querySelectorAll('.feature-card');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            
            tabBtns.forEach(b => {
                b.classList.remove('active');
                b.setAttribute('aria-selected', 'false');
            });
            featureCards.forEach(card => card.classList.remove('active-card'));

            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            const targetCard = document.getElementById(targetId);
            if (targetCard) {
                targetCard.classList.add('active-card');
            }
            if (targetId === 'section-dashboard') {
                loadDashboardData();
            }
        });
    });

    // Helper: Show Loading Spinner in output box
    function showLoading(outputEl, message = 'EduGenie is thinking...') {
        outputEl.classList.remove('hidden');
        outputEl.innerHTML = `
            <div class="loading-state">
                <div class="spinner"></div>
                <span>${escapeHtml(message)}</span>
            </div>
        `;
    }

    function toggleFormState(form, isLoading) {
        if (!form) return;
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = isLoading;
            if (isLoading) {
                submitBtn.classList.add('btn-loading');
            } else {
                submitBtn.classList.remove('btn-loading');
            }
        }
    }

    function escapeHtml(str) {
        return (str || '').toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Helper: Render markdown securely sanitized with DOMPurify to eliminate XSS
    function renderMarkdown(text) {
        if (!text) return '';
        let rawHtml = '';
        if (window.marked && typeof window.marked.parse === 'function') {
            rawHtml = window.marked.parse(text);
        } else {
            rawHtml = escapeHtml(text).replace(/\n/g, '<br>');
        }
        
        // Sanitize with DOMPurify if loaded
        if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
            return window.DOMPurify.sanitize(rawHtml);
        }
        // Secure fallback: If DOMPurify is unavailable, do not inject unescaped HTML!
        return escapeHtml(text).replace(/\n/g, '<br>');
    }

    // 2. Conversational AI Tutor State & Event Management
    const qaForm = document.getElementById('qaForm');
    const questionInput = document.getElementById('question');
    const qaSubmitBtn = document.getElementById('qaSubmitBtn');
    const qaResult = document.getElementById('qaResult'); // legacy hidden anchor
    const chatMessageStream = document.getElementById('chatMessageStream');
    const chatMessagesList = document.getElementById('chatMessagesList');
    const chatWelcomeCard = document.getElementById('chatWelcomeCard');
    const chatThinkingIndicator = document.getElementById('chatThinkingIndicator');
    const chatNewSessionBtn = document.getElementById('chatNewSessionBtn');
    const charCounter = document.getElementById('charCounter');
    const qaGradeLevel = document.getElementById('qaGradeLevel');
    const qaSubject = document.getElementById('qaSubject');
    const qaLanguage = document.getElementById('qaLanguage');
    const qaDifficulty = document.getElementById('qaDifficulty');
    const qaResponseLength = document.getElementById('qaResponseLength');

    let currentConversationId = null;
    let conversationTurns = []; // [{role: 'user'|'assistant', content: string}]
    let isGenerating = false;
    let userHasScrolledUp = false;
    let lastFailedQuestion = null;

    // Track user scroll position in chat stream to avoid jarring jumps when reviewing history
    if (chatMessageStream) {
        chatMessageStream.addEventListener('scroll', () => {
            const distanceFromBottom = chatMessageStream.scrollHeight - chatMessageStream.scrollTop - chatMessageStream.clientHeight;
            userHasScrolledUp = distanceFromBottom > 60;
        });
    }

    function scrollToBottom(force = false) {
        if (!chatMessageStream) return;
        if (force || !userHasScrolledUp) {
            chatMessageStream.scrollTo({
                top: chatMessageStream.scrollHeight,
                behavior: 'smooth'
            });
        }
    }

    // Auto-resize input textarea up to max-height
    if (questionInput) {
        questionInput.addEventListener('input', () => {
            questionInput.style.height = 'auto';
            questionInput.style.height = Math.min(questionInput.scrollHeight, 140) + 'px';
            if (charCounter) {
                const len = questionInput.value.length;
                charCounter.textContent = `${len} / 5000`;
                charCounter.style.color = len > 4800 ? '#f87171' : 'var(--text-muted)';
            }
        });

        // Submit on Enter (Shift+Enter for newline)
        questionInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!isGenerating && questionInput.value.trim()) {
                    sendMessage(questionInput.value.trim());
                }
            }
        });
    }

    // Wire suggestion chips on welcome card
    const chipBtns = document.querySelectorAll('.chip-btn');
    chipBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const query = btn.getAttribute('data-query');
            if (query && !isGenerating) {
                if (questionInput) questionInput.value = query;
                sendMessage(query);
            }
        });
    });

    // Start New Chat
    if (chatNewSessionBtn) {
        chatNewSessionBtn.addEventListener('click', async () => {
            if (isGenerating) return;
            try {
                const res = await fetch('/qa/new-chat', { method: 'POST' });
                const data = await res.json();
                currentConversationId = data.conversation_id;
            } catch (err) {
                currentConversationId = 'conv_' + Math.random().toString(36).substr(2, 9);
            }
            conversationTurns = [];
            lastFailedQuestion = null;
            if (chatMessagesList) chatMessagesList.innerHTML = '';
            if (chatWelcomeCard) chatWelcomeCard.style.display = 'block';
            if (questionInput) {
                questionInput.value = '';
                questionInput.style.height = 'auto';
                questionInput.focus();
            }
            if (charCounter) charCounter.textContent = '0 / 5000';
            if (qaResponseLength) qaResponseLength.value = 'short';
            scrollToBottom(true);
        });
    }

    function appendUserMessage(text) {
        if (chatWelcomeCard) chatWelcomeCard.style.display = 'none';
        const msgEl = document.createElement('div');
        msgEl.className = 'chat-msg student';
        msgEl.innerHTML = `
            <div class="chat-avatar student-avatar" title="You">
                <i class="fa-solid fa-user-graduate"></i>
            </div>
            <div class="msg-body">
                <div class="msg-bubble">${escapeHtml(text)}</div>
            </div>
        `;
        if (chatMessagesList) chatMessagesList.appendChild(msgEl);
        scrollToBottom(true);
        return msgEl;
    }

    function createTutorMessageElement() {
        if (chatWelcomeCard) chatWelcomeCard.style.display = 'none';
        const msgEl = document.createElement('div');
        msgEl.className = 'chat-msg tutor';
        msgEl.innerHTML = `
            <div class="chat-avatar tutor-avatar" title="EduGenie">
                <i class="fa-solid fa-wand-magic-sparkles"></i>
            </div>
            <div class="msg-body">
                <div class="msg-bubble"><div class="bubble-content"></div></div>
                <div class="msg-action-toolbar" style="display: none;"></div>
                <div class="followup-chips" style="display: none;"></div>
            </div>
        `;
        if (chatMessagesList) chatMessagesList.appendChild(msgEl);
        return msgEl;
    }

    function renderTutorActions(msgEl, fullText, followups = []) {
        const toolbar = msgEl.querySelector('.msg-action-toolbar');
        const chipsContainer = msgEl.querySelector('.followup-chips');

        if (toolbar) {
            toolbar.style.display = 'flex';
            toolbar.innerHTML = `
                <button type="button" class="msg-action-btn action-copy" title="Copy answer to clipboard">
                    <i class="fa-regular fa-copy"></i> Copy
                </button>
                <button type="button" class="msg-action-btn action-simpler" title="Ask for a simpler explanation">
                    <i class="fa-solid fa-feather"></i> Simpler
                </button>
                <button type="button" class="msg-action-btn action-examples" title="Ask for real-world examples">
                    <i class="fa-solid fa-lightbulb"></i> Examples
                </button>
                <button type="button" class="msg-action-btn action-quiz" title="Practice with a quiz on this topic">
                    <i class="fa-solid fa-circle-question"></i> Quiz Me
                </button>
                <button type="button" class="msg-action-btn action-plan" title="Generate a study plan for this topic">
                    <i class="fa-solid fa-route"></i> Study Plan
                </button>
            `;

            // Copy button logic
            const copyBtn = toolbar.querySelector('.action-copy');
            if (copyBtn) {
                copyBtn.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(fullText);
                        copyBtn.classList.add('active-action');
                        copyBtn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
                        setTimeout(() => {
                            copyBtn.classList.remove('active-action');
                            copyBtn.innerHTML = '<i class="fa-regular fa-copy"></i> Copy';
                        }, 2000);
                    } catch (e) {
                        alert('Answer copied to clipboard!');
                    }
                });
            }

            // Simpler button logic
            const simplerBtn = toolbar.querySelector('.action-simpler');
            if (simplerBtn) {
                simplerBtn.addEventListener('click', () => {
                    if (!isGenerating) sendMessage("Can you explain that more simply with an easy everyday analogy?");
                });
            }

            // Examples button logic
            const exBtn = toolbar.querySelector('.action-examples');
            if (exBtn) {
                exBtn.addEventListener('click', () => {
                    if (!isGenerating) sendMessage("Can you give me 2 relatable, real-world examples of this concept?");
                });
            }

            // Quiz Me button logic: switches to quiz tab with topic pre-filled
            const quizBtn = toolbar.querySelector('.action-quiz');
            if (quizBtn) {
                quizBtn.addEventListener('click', () => {
                    const tabQuiz = document.getElementById('tabQuiz');
                    const quizTopic = document.getElementById('quizTopic');
                    const firstLine = fullText.split('\n')[0].replace(/^[#*\s🎯💡]+/, '').trim();
                    if (quizTopic) quizTopic.value = firstLine.slice(0, 80);
                    if (tabQuiz) tabQuiz.click();
                });
            }

            // Study Plan button logic: switches to learning tab with topic prefilled
            const planBtn = toolbar.querySelector('.action-plan');
            if (planBtn) {
                planBtn.addEventListener('click', () => {
                    const tabLearn = document.getElementById('tabLearn');
                    const studyGoal = document.getElementById('studyGoal');
                    const firstLine = fullText.split('\n')[0].replace(/^[#*\s🎯💡]+/, '').trim();
                    if (studyGoal) studyGoal.value = "Master " + firstLine.slice(0, 60);
                    if (tabLearn) tabLearn.click();
                });
            }
        }

        // Render suggested follow-up chips
        if (chipsContainer && Array.isArray(followups) && followups.length > 0) {
            chipsContainer.style.display = 'flex';
            chipsContainer.innerHTML = '';
            followups.forEach(promptText => {
                const chip = document.createElement('button');
                chip.type = 'button';
                chip.className = 'followup-chip';
                chip.innerHTML = `<i class="fa-solid fa-reply"></i> ${escapeHtml(promptText)}`;
                chip.addEventListener('click', () => {
                    if (!isGenerating) sendMessage(promptText);
                });
                chipsContainer.appendChild(chip);
            });
        }
        scrollToBottom();
    }

    function appendErrorMessage(errorText, retryQuery) {
        lastFailedQuestion = retryQuery;
        const msgEl = document.createElement('div');
        msgEl.className = 'chat-msg tutor error-msg';
        msgEl.innerHTML = `
            <div class="chat-avatar tutor-avatar" style="background: #ef4444;">
                <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
            <div class="msg-body">
                <div class="msg-bubble">
                    <strong>⚠️ Service Notice:</strong>
                    <p style="margin: 0.35rem 0;">${escapeHtml(errorText)}</p>
                    <button type="button" class="chat-retry-btn" id="retryMsgBtn">
                        <i class="fa-solid fa-rotate-right"></i> Retry Question
                    </button>
                </div>
            </div>
        `;
        if (chatMessagesList) chatMessagesList.appendChild(msgEl);
        const retryBtn = msgEl.querySelector('#retryMsgBtn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                msgEl.remove();
                if (lastFailedQuestion && !isGenerating) {
                    sendMessage(lastFailedQuestion);
                }
            });
        }
        scrollToBottom(true);
    }

    async function sendMessage(questionText) {
        if (!questionText || isGenerating) return;
        const cleanText = questionText.trim();
        if (!cleanText) return;

        isGenerating = true;
        if (qaSubmitBtn) qaSubmitBtn.disabled = true;
        if (questionInput) {
            questionInput.value = '';
            questionInput.style.height = 'auto';
        }
        if (charCounter) charCounter.textContent = '0 / 5000';

        appendUserMessage(cleanText);
        conversationTurns.push({ role: 'user', content: cleanText });

        if (chatThinkingIndicator) chatThinkingIndicator.classList.remove('hidden');
        scrollToBottom(true);

        const payload = {
            question: cleanText,
            conversation_id: currentConversationId,
            subject: qaSubject && qaSubject.value ? qaSubject.value : null,
            difficulty: qaDifficulty && qaDifficulty.value ? qaDifficulty.value : null,
            grade_level: qaGradeLevel && qaGradeLevel.value ? qaGradeLevel.value : null,
            language: qaLanguage && qaLanguage.value ? qaLanguage.value : null,
            response_length: qaResponseLength && qaResponseLength.value ? qaResponseLength.value : 'short',
            history: conversationTurns.slice(-8)
        };

        let tutorMsgEl = null;
        let accumulatedText = "";

        // Progressive streaming with graceful JSON fallback
        try {
            const streamResponse = await fetch('/qa/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (streamResponse.ok && streamResponse.body) {
                if (chatThinkingIndicator) chatThinkingIndicator.classList.add('hidden');
                tutorMsgEl = createTutorMessageElement();
                const bubbleContent = tutorMsgEl.querySelector('.bubble-content');
                const reader = streamResponse.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                let followups = [];

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // keep partial line in buffer

                    for (const line of lines) {
                        const trimmed = line.trim();
                        if (trimmed.startsWith('data:')) {
                            const jsonStr = trimmed.slice(5).trim();
                            if (!jsonStr) continue;
                            try {
                                const parsed = JSON.parse(jsonStr);
                                if (parsed.chunk) {
                                    accumulatedText += parsed.chunk;
                                    bubbleContent.innerHTML = renderMarkdown(accumulatedText);
                                    scrollToBottom();
                                }
                                if (parsed.done) {
                                    if (parsed.conversation_id) currentConversationId = parsed.conversation_id;
                                    if (parsed.suggested_followups) followups = parsed.suggested_followups;
                                }
                                if (parsed.error) {
                                    throw new Error(parsed.error);
                                }
                            } catch (e) {
                                // non-fatal stream parse notice
                            }
                        }
                    }
                }

                if (accumulatedText.trim()) {
                    conversationTurns.push({ role: 'assistant', content: accumulatedText });
                    renderTutorActions(tutorMsgEl, accumulatedText, followups);
                } else {
                    throw new Error("Empty streaming response received.");
                }
            } else {
                // Fallback to standard JSON endpoint
                throw new Error("Streaming endpoint unavailable, using standard request.");
            }
        } catch (streamErr) {
            // Standard JSON POST Fallback
            try {
                const response = await fetch('/qa', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (chatThinkingIndicator) chatThinkingIndicator.classList.add('hidden');

                if (response.ok && data.answer) {
                    if (data.conversation_id) currentConversationId = data.conversation_id;
                    conversationTurns.push({ role: 'assistant', content: data.answer });
                    if (!tutorMsgEl) tutorMsgEl = createTutorMessageElement();
                    const bubbleContent = tutorMsgEl.querySelector('.bubble-content');
                    bubbleContent.innerHTML = renderMarkdown(data.answer);
                    renderTutorActions(tutorMsgEl, data.answer, data.suggested_followups || []);
                } else {
                    const errMsg = data.error || 'The AI Tutor could not complete this request.';
                    appendErrorMessage(errMsg, cleanText);
                }
            } catch (err) {
                if (chatThinkingIndicator) chatThinkingIndicator.classList.add('hidden');
                appendErrorMessage('Network connection lost or request timed out. Please check your connection and retry.', cleanText);
            }
        } finally {
            isGenerating = false;
            if (qaSubmitBtn) qaSubmitBtn.disabled = false;
            if (chatThinkingIndicator) chatThinkingIndicator.classList.add('hidden');
            if (questionInput) questionInput.focus();
        }
    }

    if (qaForm) {
        qaForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (questionInput && !isGenerating) {
                const q = questionInput.value.trim();
                if (q) sendMessage(q);
            }
        });
    }


    // 3. Explanation Form Handler with Level and Learning Style
    const explainForm = document.getElementById('explainForm');
    const explainResult = document.getElementById('explainResult');

    explainForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topicInput = document.getElementById('topic');
        const topic = topicInput.value.trim();
        if (!topic) return;

        const levelEl = document.getElementById('explainLevel');
        const styleEl = document.getElementById('explainStyle');
        const level = levelEl && levelEl.value ? levelEl.value : null;
        const style = styleEl && styleEl.value ? styleEl.value : null;

        toggleFormState(explainForm, true);
        showLoading(explainResult, 'Generating concept explanation...');

        const payload = {
            topic: topic,
            level: level,
            style: style
        };

        try {
            const response = await fetch('/explain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (response.ok && data.explanation) {
                let metaBadgesHtml = '';
                if (data.adapted) {
                    metaBadgesHtml += '<div class="meta-badge-row">';
                    if (data.level) {
                        metaBadgesHtml += `<span class="meta-badge badge-level"><i class="fa-solid fa-layer-group"></i> Level: ${escapeHtml(data.level)}</span>`;
                    }
                    if (data.style) {
                        metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-palette"></i> Style: ${escapeHtml(data.style)}</span>`;
                    }
                    metaBadgesHtml += '</div>';
                }

                explainResult.innerHTML = `
                    <div class="output-title"><i class="fa-solid fa-book-open"></i> Explanation for "${escapeHtml(data.topic || topic)}":</div>
                    ${metaBadgesHtml}
                    <div class="output-content">${renderMarkdown(data.explanation)}</div>
                `;
                recordActivity('topic_explanation', `Explained: ${data.topic || topic}`, data.topic || topic, null, {
                    level: data.level || level,
                    style: data.style || style
                });
            } else {
                const errMsg = data.error || 'Unable to fetch explanation.';
                explainResult.innerHTML = `<div class="output-content" style="color: #f87171;">❌ ${escapeHtml(errMsg)}</div>`;
            }
        } catch (err) {
            explainResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Network Error: Unable to fetch explanation.</div>`;
        } finally {
            toggleFormState(explainForm, false);
        }
    });

    // Helper: Copy Output Content to Clipboard
    window.copyOutputText = function(buttonEl) {
        const container = buttonEl.closest('.output') || buttonEl.closest('.feature-card');
        if (!container) return;
        const contentEl = container.querySelector('.output-content');
        if (!contentEl) return;
        const textToCopy = contentEl.innerText || contentEl.textContent;
        navigator.clipboard.writeText(textToCopy).then(() => {
            const originalHtml = buttonEl.innerHTML;
            buttonEl.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
            buttonEl.classList.add('btn-copied');
            setTimeout(() => {
                buttonEl.innerHTML = originalHtml;
                buttonEl.classList.remove('btn-copied');
            }, 2000);
        }).catch(() => {
            alert('Failed to copy to clipboard.');
        });
    };

    // 4. Summarize Form Handler with Format, Length, Focus Topic, and Revision Options
    const summaryForm = document.getElementById('summaryForm');
    const summaryResult = document.getElementById('summaryResult');
    const summaryFormatSelect = document.getElementById('summaryFormat');
    const revisionOptionsRow = document.getElementById('revisionOptionsRow');

    if (summaryFormatSelect && revisionOptionsRow) {
        summaryFormatSelect.addEventListener('change', () => {
            if (summaryFormatSelect.value === 'revision_notes') {
                revisionOptionsRow.style.opacity = '1';
                revisionOptionsRow.style.pointerEvents = 'auto';
            } else {
                revisionOptionsRow.style.opacity = '0.7';
            }
        });
    }

    summaryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const textInput = document.getElementById('summaryText');
        const text = textInput ? textInput.value.trim() : '';
        if (!text) return;

        const formatEl = document.getElementById('summaryFormat');
        const lengthEl = document.getElementById('summaryLength');
        const topicEl = document.getElementById('summaryTopic');
        const checklistEl = document.getElementById('includeChecklist');
        const questionsEl = document.getElementById('includePracticeQuestions');

        const formatVal = formatEl ? formatEl.value : 'short';
        const lengthVal = lengthEl ? lengthEl.value : 'medium';
        const topicVal = topicEl && topicEl.value.trim() ? topicEl.value.trim() : null;
        const includeChecklist = checklistEl ? checklistEl.checked : true;
        const includePracticeQuestions = questionsEl ? questionsEl.checked : false;

        toggleFormState(summaryForm, true);
        showLoading(summaryResult, formatVal === 'revision_notes' ? 'Drafting comprehensive revision notes...' : 'Summarizing passage with strict source accuracy...');

        const payload = {
            text: text,
            format: formatVal,
            length: lengthVal,
            topic: topicVal,
            include_checklist: includeChecklist,
            include_practice_questions: includePracticeQuestions
        };

        try {
            const response = await fetch('/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (response.ok && data.summary) {
                const formatLabels = {
                    short: 'Short Summary',
                    detailed: 'Detailed Summary',
                    revision_notes: 'Exam Revision Notes',
                    key_concepts: 'Key Concepts & Definitions',
                    important_points: 'Important Points',
                    step_by_step: 'Step-by-Step Breakdown'
                };
                const formatLabel = formatLabels[data.format || formatVal] || 'Summary';

                let metaBadgesHtml = '<div class="meta-badge-row">';
                metaBadgesHtml += `<span class="meta-badge badge-level"><i class="fa-solid fa-layer-group"></i> Format: ${escapeHtml(formatLabel)}</span>`;
                metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-sliders"></i> Length: ${escapeHtml(data.length || lengthVal)}</span>`;
                if (data.topic) {
                    metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-crosshairs"></i> Focus: ${escapeHtml(data.topic)}</span>`;
                }
                metaBadgesHtml += '</div>';

                summaryResult.innerHTML = `
                    <div class="output-header-flex">
                        <div class="output-title"><i class="fa-solid fa-file-lines"></i> ${escapeHtml(formatLabel)}:</div>
                        <button type="button" class="copy-btn" onclick="copyOutputText(this)" title="Copy to clipboard">
                            <i class="fa-solid fa-copy"></i> Copy
                        </button>
                    </div>
                    ${metaBadgesHtml}
                    <div class="output-content">${renderMarkdown(data.summary)}</div>
                `;
                const actType = (data.format || formatVal) === 'revision_notes' ? 'revision_notes' : 'text_summary';
                const actTitle = actType === 'revision_notes' ? `Revision Notes: ${data.topic || topicVal || 'Key Topics'}` : `Summary: ${data.topic || topicVal || 'Passage'}`;
                recordActivity(actType, actTitle, data.topic || topicVal || 'Passage', null, {
                    format: data.format || formatVal,
                    length: data.length || lengthVal
                });
            } else {
                const errMsg = data.error || 'Unable to fetch summary.';
                summaryResult.innerHTML = `<div class="output-content" style="color: #f87171;">❌ ${escapeHtml(errMsg)}</div>`;
            }
        } catch (err) {
            summaryResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Network Error: Unable to fetch summary.</div>`;
        } finally {
            toggleFormState(summaryForm, false);
        }
    });

    // 5. In-Memory Session State for Quizzes & Adaptive Learning Integration
    let latestQuizSession = {
        topic: '',
        questions: [] // [{question, options, correct_answer, selected_answer, is_correct, answered}]
    };

    function updateQuizBanner() {
        const banner = document.getElementById('quizSessionBanner');
        const bannerText = document.getElementById('quizSessionText');
        if (!banner || !bannerText) return;

        const answeredCount = latestQuizSession.questions.filter(q => q.answered).length;
        const totalCount = latestQuizSession.questions.length;
        if (totalCount > 0 && answeredCount > 0) {
            const correctCount = latestQuizSession.questions.filter(q => q.is_correct).length;
            banner.classList.remove('hidden');
            bannerText.innerHTML = `Quiz on "<strong>${escapeHtml(latestQuizSession.topic || 'Current Topic')}</strong>": ${correctCount}/${answeredCount} answered correctly`;
        } else {
            banner.classList.add('hidden');
        }
    }

    // Quiz Form Handler & Interactive Renderer
    const quizForm = document.getElementById('quizForm');
    const quizResult = document.getElementById('quizResult');

    quizForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const textInput = document.getElementById('quizText');
        const text = textInput ? textInput.value.trim() : '';
        if (!text) return;

        toggleFormState(quizForm, true);
        showLoading(quizResult, 'Crafting multiple-choice quiz questions...');

        try {
            const response = await fetch('/quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            });
            const data = await response.json();

            if (response.ok && data.quiz && Array.isArray(data.quiz)) {
                // Initialize session state
                latestQuizSession = {
                    topic: text,
                    questions: data.quiz.map(q => ({
                        question: q.question,
                        options: q.options || [],
                        correct_answer: q.answer,
                        selected_answer: null,
                        is_correct: false,
                        answered: false
                    }))
                };
                renderQuiz(data.quiz, text);
                updateQuizBanner();
            } else {
                const errMsg = data.error || 'Unable to generate quiz.';
                quizResult.innerHTML = `<div class="output-content" style="color: #f87171;">❌ ${escapeHtml(errMsg)}</div>`;
            }
        } catch (err) {
            quizResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Network Error: Unable to generate quiz.</div>`;
        } finally {
            toggleFormState(quizForm, false);
        }
    });

    function renderQuiz(quizItems, sourceTopic) {
        if (!quizItems || !Array.isArray(quizItems) || quizItems.length === 0) {
            quizResult.classList.remove('hidden');
            quizResult.innerHTML = `<div class="output-content">No quiz questions were generated. Please try again.</div>`;
            return;
        }

        const validQuestions = quizItems.filter(q => q && typeof q === 'object' && q.question && Array.isArray(q.options) && q.options.length > 0);
        if (validQuestions.length === 0) {
            quizResult.classList.remove('hidden');
            quizResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Unable to format quiz questions. Please try again.</div>`;
            return;
        }

        let html = `
            <div class="quiz-container">
                <div class="output-title"><i class="fa-solid fa-list-check"></i> Generated Quiz (${validQuestions.length} Questions):</div>
        `;

        validQuestions.forEach((q, index) => {
            const qNum = index + 1;
            const optionsHtml = (q.options || []).map((opt, optIndex) => `
                <label class="quiz-option-label" for="q${qNum}_opt${optIndex}">
                    <input type="radio" id="q${qNum}_opt${optIndex}" name="question_${qNum}" value="${escapeHtml(opt)}">
                    <span>${escapeHtml(opt)}</span>
                </label>
            `).join('');

            html += `
                <div class="quiz-card" data-question-index="${index}">
                    <div class="quiz-question">Q${qNum}: ${escapeHtml(q.question)}</div>
                    <div class="quiz-options">
                        ${optionsHtml}
                    </div>
                    <button type="button" class="check-answer-btn" onclick="checkQuizAnswer(this)">Check Answer</button>
                    <div class="quiz-feedback-container"></div>
                </div>
            `;
        });

        // Add Adaptive Recommendation Trigger Card
        html += `
            <div class="quiz-adaptive-card" id="quizAdaptiveCard">
                <div class="adaptive-card-header">
                    <i class="fa-solid fa-wand-magic-sparkles"></i>
                    <div>
                        <h4>Level Up with Adaptive Recommendations</h4>
                        <p>Turn your quiz performance into targeted revision notes and a personalized study sequence.</p>
                    </div>
                </div>
                <button type="button" id="btnQuizToAdaptive" class="quiz-to-adaptive-btn">
                    <span>Get Adaptive Recommendations from this Quiz</span> <i class="fa-solid fa-arrow-right"></i>
                </button>
            </div>
        `;

        html += `</div>`;
        quizResult.classList.remove('hidden');
        quizResult.innerHTML = html;

        // Wire up adaptive recommendation jump button
        const btnAdaptive = document.getElementById('btnQuizToAdaptive');
        if (btnAdaptive) {
            btnAdaptive.addEventListener('click', () => {
                triggerQuizToAdaptiveLearning(sourceTopic);
            });
        }
    }

    // Global helper to check individual question answer
    window.checkQuizAnswer = function(buttonEl) {
        const card = buttonEl.closest('.quiz-card');
        const qIndex = parseInt(card.getAttribute('data-question-index'), 10);
        const questionObj = latestQuizSession.questions[qIndex];
        const correctAnswer = questionObj ? questionObj.correct_answer : '';
        const selectedRadio = card.querySelector('input[type="radio"]:checked');
        const feedbackContainer = card.querySelector('.quiz-feedback-container');

        if (!selectedRadio) {
            feedbackContainer.innerHTML = `<div class="quiz-feedback incorrect">⚠️ Please select an option first!</div>`;
            return;
        }

        // Lock radio inputs and button to prevent re-answering or tamper attempts
        buttonEl.disabled = true;
        card.querySelectorAll('input[type="radio"]').forEach(radio => radio.disabled = true);

        const selectedValue = selectedRadio.value;
        const isCorrect = (selectedValue === correctAnswer);

        if (latestQuizSession.questions[qIndex]) {
            latestQuizSession.questions[qIndex].selected_answer = selectedValue;
            latestQuizSession.questions[qIndex].is_correct = isCorrect;
            latestQuizSession.questions[qIndex].answered = true;
        }

        if (isCorrect) {
            feedbackContainer.innerHTML = `<div class="quiz-feedback correct"><i class="fa-solid fa-circle-check"></i> Correct! Great job.</div>`;
        } else {
            feedbackContainer.innerHTML = `<div class="quiz-feedback incorrect"><i class="fa-solid fa-circle-xmark"></i> Incorrect. Correct answer: <strong>${escapeHtml(correctAnswer)}</strong></div>`;
        }

        updateQuizBanner();

        // Check if all questions have been completed
        const answeredCount = latestQuizSession.questions.filter(q => q.answered).length;
        const totalCount = latestQuizSession.questions.length;
        if (totalCount > 0 && answeredCount === totalCount && !latestQuizSession.hasBeenRecorded) {
            latestQuizSession.hasBeenRecorded = true;
            const correctCount = latestQuizSession.questions.filter(q => q.is_correct).length;
            recordQuizCompletion(latestQuizSession.topic, correctCount, totalCount);
        }
    };

    // Helper: Transition from Quiz to Adaptive Recommendations seamlessly
    function triggerQuizToAdaptiveLearning(topic) {
        // Switch to section-learn tab
        const learnTabBtn = document.querySelector('.tab-btn[data-target="section-learn"]');
        if (learnTabBtn) {
            learnTabBtn.click();
        }

        // Switch to roadmap sub-tab
        const roadmapSubBtn = document.getElementById('tabModeRoadmap');
        if (roadmapSubBtn) {
            roadmapSubBtn.click();
        }

        // Pre-fill topic and ensure checkbox is checked
        const learnTopicInput = document.getElementById('learnTopic');
        if (learnTopicInput) {
            learnTopicInput.value = topic;
        }
        const useQuizCheck = document.getElementById('useQuizSessionCheck');
        if (useQuizCheck) {
            useQuizCheck.checked = true;
        }

        // Automatically trigger recommendations
        const learnFormEl = document.getElementById('learnForm');
        if (learnFormEl) {
            learnFormEl.dispatchEvent(new Event('submit'));
        }
    }

    // 6. Sub-Mode Tabs for Section-Learn (Roadmap vs Study Plan)
    const tabModeRoadmap = document.getElementById('tabModeRoadmap');
    const tabModePlan = document.getElementById('tabModePlan');
    const subContainerRoadmap = document.getElementById('subContainerRoadmap');
    const subContainerPlan = document.getElementById('subContainerPlan');

    if (tabModeRoadmap && tabModePlan && subContainerRoadmap && subContainerPlan) {
        tabModeRoadmap.addEventListener('click', () => {
            tabModeRoadmap.classList.add('active');
            tabModePlan.classList.remove('active');
            subContainerRoadmap.classList.add('active-sub-mode');
            subContainerPlan.classList.remove('active-sub-mode');
        });

        tabModePlan.addEventListener('click', () => {
            tabModePlan.classList.add('active');
            tabModeRoadmap.classList.remove('active');
            subContainerPlan.classList.add('active-sub-mode');
            subContainerRoadmap.classList.remove('active-sub-mode');
        });
    }

    // 7. Adaptive Learning Path Form Handler
    const learnForm = document.getElementById('learnForm');
    const learnResult = document.getElementById('learnResult');

    learnForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topicInput = document.getElementById('learnTopic');
        const topic = topicInput ? topicInput.value.trim() : '';
        if (!topic) return;

        const subjectEl = document.getElementById('learnSubject');
        const diffEl = document.getElementById('learnDifficulty');
        const goalsEl = document.getElementById('learnGoals');
        const useQuizCheck = document.getElementById('useQuizSessionCheck');

        const subjectVal = subjectEl && subjectEl.value ? subjectEl.value : null;
        const diffVal = diffEl && diffEl.value ? diffEl.value : null;
        const goalsVal = goalsEl && goalsEl.value.trim() ? goalsEl.value.trim() : null;

        const shouldIncludeQuiz = useQuizCheck && useQuizCheck.checked && latestQuizSession.questions.some(q => q.answered);
        const quizResultsPayload = shouldIncludeQuiz
            ? latestQuizSession.questions.filter(q => q.answered)
            : null;

        toggleFormState(learnForm, true);
        showLoading(learnResult, shouldIncludeQuiz ? 'Analyzing quiz results and tailoring recommendations...' : 'Designing adaptive learning roadmap...');

        const payload = {
            topic: topic,
            subject: subjectVal,
            difficulty: diffVal,
            goals: goalsVal,
            quiz_results: quizResultsPayload
        };

        try {
            const response = await fetch('/learn/recommendations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();

            if (response.ok && data.recommendation) {
                let metaBadgesHtml = '<div class="meta-badge-row">';
                if (data.subject) {
                    metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-book-open"></i> Subject: ${escapeHtml(data.subject)}</span>`;
                }
                if (data.difficulty) {
                    metaBadgesHtml += `<span class="meta-badge badge-level"><i class="fa-solid fa-sliders"></i> Level: ${escapeHtml(data.difficulty)}</span>`;
                }
                if (data.based_on_quiz) {
                    metaBadgesHtml += `<span class="meta-badge badge-quiz-adapted"><i class="fa-solid fa-circle-check"></i> Tailored to Quiz Results</span>`;
                }
                metaBadgesHtml += '</div>';

                learnResult.innerHTML = `
                    <div class="output-header-flex">
                        <div class="output-title"><i class="fa-solid fa-route"></i> Learning Path for "${escapeHtml(data.topic || topic)}":</div>
                        <button type="button" class="copy-btn" onclick="copyOutputText(this)" title="Copy to clipboard">
                            <i class="fa-solid fa-copy"></i> Copy
                        </button>
                    </div>
                    ${metaBadgesHtml}
                    <div class="output-content">${renderMarkdown(data.recommendation)}</div>
                `;
            } else {
                const errMsg = data.error || 'Unable to fetch learning path.';
                learnResult.innerHTML = `<div class="output-content" style="color: #f87171;">❌ ${escapeHtml(errMsg)}</div>`;
            }
        } catch (err) {
            learnResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Network Error: Unable to fetch learning path.</div>`;
        } finally {
            toggleFormState(learnForm, false);
        }
    });

    // 8. Personalized Study Plan Form Handler
    const studyPlanForm = document.getElementById('studyPlanForm');
    const studyPlanResult = document.getElementById('studyPlanResult');

    if (studyPlanForm && studyPlanResult) {
        studyPlanForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const goalInput = document.getElementById('planGoal');
            const goal = goalInput ? goalInput.value.trim() : '';
            if (!goal) return;

            const subjectEl = document.getElementById('planSubject');
            const levelEl = document.getElementById('planLevel');
            const timeEl = document.getElementById('planTime');
            const targetDateEl = document.getElementById('planTargetDate');

            const payload = {
                goal: goal,
                subject: subjectEl && subjectEl.value ? subjectEl.value : null,
                level: levelEl && levelEl.value ? levelEl.value : 'beginner',
                available_time: timeEl ? timeEl.value : '1 hour / day',
                target_date: targetDateEl && targetDateEl.value.trim() ? targetDateEl.value.trim() : null
            };

            toggleFormState(studyPlanForm, true);
            showLoading(studyPlanResult, 'Building realistic, proportional study plan...');

            try {
                const response = await fetch('/learn/study-plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();

                if (response.ok && data.plan) {
                    let metaBadgesHtml = '<div class="meta-badge-row">';
                    if (data.subject) {
                        metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-book-open"></i> Subject: ${escapeHtml(data.subject)}</span>`;
                    }
                    metaBadgesHtml += `<span class="meta-badge badge-level"><i class="fa-solid fa-layer-group"></i> Level: ${escapeHtml(data.level)}</span>`;
                    metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-clock"></i> Time: ${escapeHtml(data.available_time)}</span>`;
                    if (data.target_date) {
                        metaBadgesHtml += `<span class="meta-badge badge-subject"><i class="fa-solid fa-calendar-days"></i> Timeline: ${escapeHtml(data.target_date)}</span>`;
                    }
                    metaBadgesHtml += '</div>';

                    studyPlanResult.innerHTML = `
                        <div class="output-header-flex">
                            <div class="output-title"><i class="fa-solid fa-calendar-check"></i> Study Plan for "${escapeHtml(data.goal || goal)}":</div>
                            <button type="button" class="copy-btn" onclick="copyOutputText(this)" title="Copy to clipboard">
                                <i class="fa-solid fa-copy"></i> Copy Plan
                            </button>
                        </div>
                        ${metaBadgesHtml}
                        <div class="output-content">${renderMarkdown(data.plan)}</div>
                        <div class="session-notice">
                            <i class="fa-solid fa-circle-info"></i> ${escapeHtml(data.disclaimer || 'Generated study plan. Track milestone progress directly in your Student Dashboard!')}
                        </div>
                    `;
                    saveStudyPlanRecord(data.goal || goal, data.subject || (subjectEl ? subjectEl.value : null), data.target_date || (targetDateEl ? targetDateEl.value : null), data.level || (levelEl ? levelEl.value : 'beginner'));
                } else {
                    const errMsg = data.error || 'Unable to generate study plan.';
                    studyPlanResult.innerHTML = `<div class="output-content" style="color: #f87171;">❌ ${escapeHtml(errMsg)}</div>`;
                }
            } catch (err) {
                studyPlanResult.innerHTML = `<div class="output-content" style="color: #f87171;">⚠️ Network Error: Unable to generate study plan.</div>`;
            } finally {
                toggleFormState(studyPlanForm, false);
            }
        });
    }

    // =========================================================================
    // 9. Student Progress & Learning Dashboard Subsystem
    // =========================================================================

    // Record verified learning activity event
    async function recordActivity(activityType, title, topic, subject = null, details = null) {
        try {
            await fetch('/progress/activities', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    activity_type: activityType,
                    title: title,
                    topic: topic,
                    subject: subject,
                    details: details
                })
            });
        } catch (err) {
            console.warn('Unable to record learning activity:', err);
        }
    }

    // Record verified quiz completion
    async function recordQuizCompletion(topic, correct, total) {
        try {
            const payload = {
                topic: topic || 'General Quiz',
                total_questions: total,
                correct_answers: correct,
                difficulty: 'standard'
            };
            const res = await fetch('/progress/quizzes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                // Insert a completion banner into the quiz output with link to dashboard
                const adaptiveCard = document.getElementById('quizAdaptiveCard');
                if (adaptiveCard && adaptiveCard.parentNode) {
                    const percentage = Math.round((correct / total) * 100);
                    const completionNotice = document.createElement('div');
                    completionNotice.className = 'quiz-session-banner';
                    completionNotice.style.marginTop = '1rem';
                    completionNotice.innerHTML = `
                        <div class="banner-info">
                            <i class="fa-solid fa-circle-check banner-icon"></i>
                            <span>Quiz Recorded! Final Score: <strong>${correct}/${total} (${percentage}%)</strong> — Saved in your Student Dashboard.</span>
                        </div>
                        <button type="button" class="dashboard-action-btn" onclick="document.getElementById('tabDashboard').click()">
                            <i class="fa-solid fa-chart-line"></i> View Dashboard
                        </button>
                    `;
                    adaptiveCard.parentNode.insertBefore(completionNotice, adaptiveCard);
                }
            }
        } catch (err) {
            console.warn('Unable to record quiz completion:', err);
        }
    }

    // Save generated study plan to progress persistence
    async function saveStudyPlanRecord(goal, subject, targetDate, level) {
        try {
            const res = await fetch('/progress/study-plans', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    goal: goal,
                    subject: subject || null,
                    target_date: targetDate || null,
                    total_sessions: 7,
                    notes: `Level: ${level || 'beginner'}`
                })
            });
            if (res.ok) {
                await recordActivity(
                    'study_plan',
                    `Created Study Plan: ${goal}`,
                    goal,
                    subject || null,
                    { target_date: targetDate, level: level }
                );
            }
        } catch (err) {
            console.warn('Unable to save study plan record:', err);
        }
    }

    // Relative timestamp formatter
    function formatRelativeTime(isoString) {
        if (!isoString) return '';
        try {
            const date = new Date(isoString);
            if (isNaN(date.getTime())) return isoString;
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        } catch (e) {
            return isoString;
        }
    }

    // Fetch and render dashboard summary data
    async function loadDashboardData() {
        const totalQuizzesEl = document.getElementById('metricTotalQuizzes');
        const avgScoreEl = document.getElementById('metricAvgScore');
        const bestScoreEl = document.getElementById('metricBestScore');
        const topicsCountEl = document.getElementById('metricTopicsCount');

        const quizListEl = document.getElementById('dashboardQuizList');
        const studyPlanListEl = document.getElementById('dashboardStudyPlanList');
        const recsListEl = document.getElementById('dashboardRecommendationsList');
        const activityListEl = document.getElementById('dashboardActivityList');

        if (!totalQuizzesEl || !quizListEl) return;

        try {
            const response = await fetch('/progress/dashboard');
            if (!response.ok) {
                throw new Error('Failed to load dashboard data');
            }
            const data = await response.json();

            // 1. Update Metrics
            totalQuizzesEl.textContent = data.total_quiz_attempts || 0;
            avgScoreEl.textContent = `${data.avg_score_percentage || 0}%`;
            bestScoreEl.textContent = `${data.best_score_percentage || 0}%`;
            topicsCountEl.textContent = data.completed_topics_count || 0;

            // 2. Render Recent Quizzes
            renderDashboardQuizzes(data.recent_quiz_attempts || [], quizListEl);

            // 3. Render Active Study Plans
            renderDashboardStudyPlans(data.active_study_plans || [], studyPlanListEl);

            // 4. Render Targeted Recommendations
            renderDashboardRecommendations(data.recommendations || [], recsListEl);

            // 5. Render Recent Activities
            renderDashboardActivities(data.recent_activities || [], activityListEl);

        } catch (err) {
            console.error('Error fetching dashboard summary:', err);
            quizListEl.innerHTML = `
                <div class="empty-panel-state">
                    <i class="fa-solid fa-triangle-exclamation empty-panel-icon"></i>
                    <div class="empty-panel-text">Unable to load dashboard data. Please try again.</div>
                </div>
            `;
        }
    }

    // Render Recent Quiz History
    function renderDashboardQuizzes(quizzes, container) {
        if (!quizzes || quizzes.length === 0) {
            container.innerHTML = `
                <div class="empty-panel-state">
                    <i class="fa-solid fa-clipboard-question empty-panel-icon"></i>
                    <div class="empty-panel-text">No quiz attempts recorded yet. Test your knowledge to track performance over time!</div>
                    <button type="button" class="empty-panel-action" onclick="document.querySelector('[data-target=\\'section-quiz\\']').click()">
                        <i class="fa-solid fa-play"></i> Generate a Quiz
                    </button>
                </div>
            `;
            return;
        }

        let html = '';
        quizzes.forEach(quiz => {
            const percentage = quiz.score_percentage || 0;
            const scoreClass = percentage >= 80 ? 'score-excellent' : (percentage >= 50 ? 'score-moderate' : 'score-needs-work');
            html += `
                <div class="quiz-item-card">
                    <div class="quiz-item-main">
                        <div class="quiz-item-topic" title="${escapeHtml(quiz.topic)}">${escapeHtml(quiz.topic)}</div>
                        <div class="quiz-item-meta">
                            <span><i class="fa-solid fa-check"></i> ${quiz.correct_answers}/${quiz.total_questions} correct</span>
                            ${quiz.difficulty ? `<span>&bull; ${escapeHtml(quiz.difficulty)}</span>` : ''}
                            <span>&bull; <i class="fa-solid fa-clock"></i> ${formatRelativeTime(quiz.created_at)}</span>
                        </div>
                    </div>
                    <div class="score-pill ${scoreClass}">
                        ${percentage}%
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // Render Active Study Plans
    function renderDashboardStudyPlans(plans, container) {
        if (!plans || plans.length === 0) {
            container.innerHTML = `
                <div class="empty-panel-state">
                    <i class="fa-solid fa-calendar-check empty-panel-icon"></i>
                    <div class="empty-panel-text">No active study plans. Set a learning goal to generate a structured timeline.</div>
                    <button type="button" class="empty-panel-action" onclick="document.querySelector('[data-target=\\'section-learn\\']').click(); document.getElementById('tabModePlan').click();">
                        <i class="fa-solid fa-plus"></i> Create Study Plan
                    </button>
                </div>
            `;
            return;
        }

        let html = '';
        plans.forEach(plan => {
            const total = plan.total_sessions || 1;
            const completed = plan.completed_sessions || 0;
            const progressPercent = Math.min(100, Math.round((completed / total) * 100));
            const isFinished = completed >= total;

            html += `
                <div class="study-plan-card">
                    <div class="plan-card-header">
                        <div class="plan-card-goal">${escapeHtml(plan.goal)}</div>
                        ${plan.subject ? `<span class="badge-tag">${escapeHtml(plan.subject)}</span>` : ''}
                    </div>
                    <div class="plan-progress-wrapper">
                        <div class="plan-progress-labels">
                            <span>Sessions: ${completed} of ${total} completed</span>
                            <span><strong>${progressPercent}%</strong></span>
                        </div>
                        <div class="plan-progress-bar">
                            <div class="plan-progress-fill" style="width: ${progressPercent}%;"></div>
                        </div>
                    </div>
                    <div class="plan-actions-row">
                        <span class="activity-meta">${plan.target_date ? `<i class="fa-solid fa-calendar-day"></i> Target: ${escapeHtml(plan.target_date)}` : 'In Progress'}</span>
                        <button type="button" class="btn-advance-session" onclick="window.advanceStudyPlanSession(${plan.id}, ${completed}, ${total}, this)" ${isFinished ? 'disabled' : ''}>
                            <i class="fa-solid fa-circle-check"></i> ${isFinished ? 'Plan Completed' : 'Mark Next Session Done'}
                        </button>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // Render Targeted Recommendations
    function renderDashboardRecommendations(recs, container) {
        if (!recs || recs.length === 0) {
            container.innerHTML = `
                <div class="empty-panel-state">
                    <i class="fa-solid fa-bullseye empty-panel-icon"></i>
                    <div class="empty-panel-text">Complete quizzes and study topics to unlock tailored practice recommendations.</div>
                </div>
            `;
            return;
        }

        let html = '';
        recs.forEach(rec => {
            const badgeClass = rec.reason === 'Needs Revision' ? 'rec-reason-revision' : (rec.reason === 'Next Step' ? 'rec-reason-next-step' : 'rec-reason-default');
            const priorityClass = rec.priority === 'high' ? 'rec-priority-high' : (rec.priority === 'medium' ? 'rec-priority-medium' : 'rec-priority-low');

            html += `
                <div class="rec-card ${priorityClass}">
                    <div class="rec-header-row">
                        <div class="rec-topic-title">${escapeHtml(rec.topic)}</div>
                        <span class="rec-reason-badge ${badgeClass}">${escapeHtml(rec.reason)}</span>
                    </div>
                    <div class="rec-description">${escapeHtml(rec.description)}</div>
                    <button type="button" class="rec-action-btn" onclick="window.studyTopic('${escapeHtml(rec.topic)}')">
                        <i class="fa-solid fa-wand-magic-sparkles"></i> Study Concept &rarr;
                    </button>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // Render Learning Activity Log
    function renderDashboardActivities(activities, container) {
        if (!activities || activities.length === 0) {
            container.innerHTML = `
                <div class="empty-panel-state">
                    <i class="fa-solid fa-list-check empty-panel-icon"></i>
                    <div class="empty-panel-text">No verified activity recorded yet. Explaining topics, generating summaries, or completing quizzes will log events here.</div>
                </div>
            `;
            return;
        }

        let html = '';
        activities.forEach(act => {
            let actClass = 'act-type-explain';
            let iconHtml = '<i class="fa-solid fa-lightbulb"></i>';

            if (act.activity_type === 'quiz_attempt') {
                actClass = 'act-type-quiz';
                iconHtml = '<i class="fa-solid fa-clipboard-question"></i>';
            } else if (act.activity_type === 'revision_notes' || act.activity_type === 'text_summary') {
                actClass = 'act-type-summary';
                iconHtml = '<i class="fa-solid fa-compress-alt"></i>';
            } else if (act.activity_type === 'study_plan') {
                actClass = 'act-type-plan';
                iconHtml = '<i class="fa-solid fa-calendar-check"></i>';
            }

            html += `
                <div class="activity-card">
                    <div class="activity-icon-bubble ${actClass}">
                        ${iconHtml}
                    </div>
                    <div class="activity-details">
                        <div class="activity-title" title="${escapeHtml(act.title)}">${escapeHtml(act.title)}</div>
                        <div class="activity-meta">
                            ${act.subject ? `<span>${escapeHtml(act.subject)} &bull; </span>` : ''}
                            <span><i class="fa-solid fa-clock"></i> ${formatRelativeTime(act.created_at)}</span>
                        </div>
                    </div>
                </div>
            `;
        });
        container.innerHTML = html;
    }

    // Global action: Advance study plan session with in-flight guard
    window.advanceStudyPlanSession = async function(planId, currentCount, totalCount, btnEl = null) {
        if (currentCount >= totalCount) return;
        if (btnEl) {
            btnEl.disabled = true;
            btnEl.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Updating...`;
        }
        try {
            const nextCount = currentCount + 1;
            const res = await fetch(`/progress/study-plans/${planId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ completed_sessions: nextCount })
            });
            if (res.ok) {
                await loadDashboardData();
            } else {
                alert('Unable to update study plan progress.');
                if (btnEl) btnEl.disabled = false;
            }
        } catch (err) {
            alert('Network error updating study plan progress.');
            if (btnEl) btnEl.disabled = false;
        }
    };

    // Global action: Study recommended topic
    window.studyTopic = function(topic) {
        const explainTab = document.querySelector('[data-target="section-explain"]');
        if (explainTab) {
            explainTab.click();
        }
        const topicInput = document.getElementById('topic');
        if (topicInput) {
            topicInput.value = topic;
            topicInput.focus();
        }
        const explainFormEl = document.getElementById('explainForm');
        if (explainFormEl) {
            explainFormEl.dispatchEvent(new Event('submit'));
        }
    };

    // Dashboard Refresh Button with debounce guard
    const btnRefreshDashboard = document.getElementById('btnRefreshDashboard');
    if (btnRefreshDashboard) {
        btnRefreshDashboard.addEventListener('click', async () => {
            btnRefreshDashboard.disabled = true;
            btnRefreshDashboard.classList.add('btn-loading');
            try {
                await loadDashboardData();
            } finally {
                btnRefreshDashboard.disabled = false;
                btnRefreshDashboard.classList.remove('btn-loading');
            }
        });
    }

    // Dashboard Reset Button
    const btnResetDashboard = document.getElementById('btnResetDashboard');
    if (btnResetDashboard) {
        btnResetDashboard.addEventListener('click', async () => {
            const confirmed = confirm(
                'Are you sure you want to reset your local student workspace progress?\\n\\n' +
                'This will clear all recorded quiz attempts, activities, and study plans from local storage.'
            );
            if (!confirmed) return;

            try {
                const res = await fetch('/progress/reset', { method: 'POST' });
                if (res.ok) {
                    await loadDashboardData();
                } else {
                    alert('Unable to reset workspace progress.');
                }
            } catch (err) {
                alert('Network error resetting workspace progress.');
            }
        });
    }

    // Pre-load dashboard summary on startup
    loadDashboardData();
});


