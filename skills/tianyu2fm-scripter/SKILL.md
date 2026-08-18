---
name: tianyu2fm-scripter
description: Research a podcast guest's books, essays, interviews, talks, and other first-party material, then combine those sources with an existing TIANYU2FM outline, transcript, topic brief, or question list to generate, extend, source, select, or reorganize Chinese interview questions. Use when preparing guest-specific podcast research, turning an author's core ideas into askable questions, writing continuation questions from things the guest has said, avoiding overlap with an existing script, or arranging supporting questions under a small number of compelling section-level questions.
---

# TIANYU2FM Scripter

Create guest-specific Chinese podcast questions that sound like a real conversation, not a book report. Ground the questions in the guest's work, preserve the program's existing thinking, and make every new question earn its place.

## Core rules

- Read all user-provided material before researching. Treat the existing outline as the editorial baseline, not as disposable notes.
- Keep source documents read-only unless the user explicitly asks for a write. When asked to create a revised version, preserve the original and create a separate document or child page.
- Never silently rewrite an existing question stem when the user asks only for arrangement. Move it verbatim.
- Prefer the guest's books, official previews, publisher material, first-party essays, and direct interviews. Use reviews mainly to discover leads, not as authority for the guest's position.
- Never claim to have read a complete work when only a table of contents, preview, excerpt, or secondary account was available. State the research basis and cite at the most precise level supported by the evidence.
- Treat cross-domain analogies as prompts, not proofs. In particular, do not turn physics, mathematics, neuroscience, or AI concepts into claims about society or life without marking the move as a heuristic.
- Default to a few strong section-level questions. Do not invent subtopics beneath every section unless the user asks for them.

## Workflow

### 1. Build the editorial brief

Extract from the user's material:

- the episode's central tension;
- the desired emotional and intellectual destination;
- the guest's relevant experiences and claims;
- all existing questions and their implied answers;
- the host's question style, vocabulary, and level of directness;
- constraints such as “do not edit,” “preserve wording,” “add sources,” or “create a child document.”

Write an internal coverage map with four buckets: already covered, partially covered, missing, and deliberately out of scope. Use it to prevent duplicate questions.

### 2. Research the guest's work

Research each named work separately. Follow this source order:

1. user-provided full text or legally accessible full text;
2. official ebook preview, table of contents, or excerpt;
3. publisher page, author essay, or authorized extract;
4. direct interview, lecture, podcast, or speech by the guest;
5. reputable review for discovery or cross-checking.

For every usable idea, record:

- work and chapter, section, page, timestamp, or excerpt location;
- the idea in neutral paraphrase;
- whether it is an explicit claim, an inference, or a possible analogy;
- the primary link or local source;
- confidence: high, medium, or exploratory.

Use internet research tools when the user asks to research or when the source is not locally available. When the source is a Feishu, Notion, Drive, PDF, or other connected document, invoke the relevant document skill and follow its read/write rules.

### 3. Mine question opportunities

Generate candidates in two modes.

**Continuation questions** follow something the guest has already said. Push on one of these dimensions:

- causal chain: “为什么会这样，中间机制是什么？”
- boundary: “这个判断在什么情况下不成立？”
- counterexample: “看起来相反的案例怎么解释？”
- trade-off: “获得它的代价是什么？”
- historical update: “过去成立的逻辑今天还成立吗？”
- personal consequence: “这个逻辑落到一个人身上会发生什么？”
- action: “知道以后，个人还能做什么？”

**Core transformations** turn a book idea into an interview question. Preserve the idea's real tension rather than asking the guest to repeat a definition. Connect it to the episode thesis, an observable contradiction, or a personal decision.

Read [question-patterns.md](references/question-patterns.md) when generating or diagnosing question candidates.

### 4. Write questions for speech

- Make each question askable aloud in one breath or in a short setup plus one clear landing question.
- Let the setup establish the guest's idea; let the final sentence introduce uncertainty, conflict, or stakes.
- Avoid questions whose setup already dictates the answer.
- Avoid generic prompts such as “能不能介绍一下这本书” unless foundational explanation is genuinely necessary.
- Use the host's existing address form and wording consistently. Do not normalize “你/您” when verbatim preservation is required.
- Add a concise source line to each new question: `出处：《书名》｜章节/主题`.
- If the evidence is indirect, label it `灵感来源` rather than `出处`.

### 5. Select and deduplicate

Compare every candidate against the coverage map. Remove questions that:

- repeat an existing question with different nouns;
- can be answered by another question's setup;
- rely on a premise the source does not support;
- ask for an abstract definition without advancing the episode;
- are interesting in isolation but do not serve the episode's central tension.

Keep productive overlap only when the later question clearly deepens, reverses, personalizes, or tests the earlier one.

### 6. Arrange the episode

When the user asks only for question inspiration, group by the two generation modes and show the source beneath each question.

When the user asks for an episode outline:

- default to three large section-level questions unless the user specifies another number;
- make each section title an intriguing, slightly open-ended question;
- place supporting questions directly under the relevant large question;
- do not add subordinate thematic headings by default;
- build an arc from shared observation, to explanatory framework, to personal or open-ended reflection;
- reserve the final section for questions that benefit from rapport, ambiguity, or personal disclosure.

Read [output-formats.md](references/output-formats.md) when packaging the result or writing it into a document.

### 7. Handle document writes safely

Only write when explicitly authorized.

- Preserve the original document.
- Create a child page or separate revision when requested.
- Before moving questions, capture their exact wording.
- After writing, fetch the result again and verify that every original question appears once, section headings match the requested structure, and the new page is attached to the intended parent.
- Report the created document link and confirm whether the original remained unchanged.

## Final quality gate

Before delivery, verify:

- Every new question has a defensible source or is clearly labeled exploratory.
- The output extends the user's thinking rather than replacing it.
- Questions contain tension, boundaries, consequences, or choices.
- No unverified quotation is presented as verbatim.
- No false claim of full-book access appears.
- The structure contains only the number of levels the user requested.
- Any document mutation matches the user's authorization exactly.
