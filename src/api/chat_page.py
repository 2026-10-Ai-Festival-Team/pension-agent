"""Dependency-free browser UI for the local pension-agent API."""

from __future__ import annotations


CHAT_PAGE = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>연금 Agent</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f5f7fb; color: #172033; }
    main { max-width: 860px; margin: 0 auto; padding: 42px 20px 64px; }
    h1 { margin: 0; font-size: 30px; }
    .hint { color: #5b6475; margin: 10px 0 24px; line-height: 1.55; }
    .card { background: #fff; border: 1px solid #e2e7f0; border-radius: 14px; padding: 20px; box-shadow: 0 4px 18px #15213a0b; }
    textarea { box-sizing: border-box; width: 100%; min-height: 104px; resize: vertical; padding: 14px; border: 1px solid #bcc6d8; border-radius: 10px; font: inherit; line-height: 1.5; }
    textarea:focus { outline: 3px solid #c8d8ff; border-color: #3974db; }
    .actions { display: flex; gap: 10px; align-items: center; margin-top: 12px; }
    button { background: #1f63ca; color: white; border: 0; border-radius: 9px; padding: 10px 16px; font: inherit; font-weight: 650; cursor: pointer; }
    button:hover { background: #1852aa; }
    button:disabled { background: #96a4b9; cursor: wait; }
    #status { color: #5b6475; font-size: 14px; }
    #result { margin-top: 20px; }
    #answer { white-space: pre-wrap; line-height: 1.65; }
    #answer.error { color: #a21c25; }
    details { margin-top: 16px; border-top: 1px solid #e6eaf1; padding-top: 14px; }
    summary { cursor: pointer; color: #2d405d; font-weight: 650; }
    .evidence { margin: 12px 0; border-left: 3px solid #7ba5eb; padding: 8px 12px; background: #f7faff; }
    .evidence-meta { color: #54647c; font-size: 13px; margin-bottom: 6px; overflow-wrap: anywhere; }
    .evidence-text { white-space: pre-wrap; line-height: 1.5; font-size: 14px; }
  </style>
</head>
<body>
  <main>
    <h1>연금 Agent</h1>
    <p class="hint">사측 제공 문서를 검색한 뒤, 충분한 근거가 있을 때만 답변을 생성합니다. 상품은 특정 매수·매도를 권유하지 않고 원본 문서의 위험등급·투자대상·보수를 비교합니다. 답변 아래에서 사용한 근거 문서와 위치를 확인할 수 있습니다.</p>
    <section class="card">
      <label for="question">질문</label>
      <textarea id="question" placeholder="예: DB형과 DC형의 적립금 운용 주체는 어떻게 다른가요?"></textarea>
      <div class="actions">
        <button id="submit" type="button">질문하기</button>
        <span id="status" aria-live="polite"></span>
      </div>
    </section>
    <section id="result" class="card" hidden>
      <h2>답변</h2>
      <div id="answer"></div>
      <details id="evidence-details">
        <summary id="evidence-summary">답변에 사용한 근거</summary>
        <div id="evidence"></div>
      </details>
    </section>
  </main>
  <script>
    const question = document.getElementById('question');
    const submit = document.getElementById('submit');
    const status = document.getElementById('status');
    const result = document.getElementById('result');
    const answer = document.getElementById('answer');
    const evidence = document.getElementById('evidence');
    const evidenceSummary = document.getElementById('evidence-summary');

    function appendEvidence(item) {
      const block = document.createElement('article');
      block.className = 'evidence';
      const page = item.locator.page_start ?? item.locator.slide_start ?? item.locator.sheet ?? '위치 정보 없음';
      const meta = document.createElement('div');
      meta.className = 'evidence-meta';
      meta.textContent = `${item.source_path} · ${page} · ${item.chunk_id}`;
      const text = document.createElement('div');
      text.className = 'evidence-text';
      text.textContent = item.text;
      block.append(meta, text);
      evidence.append(block);
    }

    async function ask() {
      const value = question.value.trim();
      if (!value) { question.focus(); return; }
      submit.disabled = true;
      status.textContent = '문서 근거를 확인하고 있습니다…';
      result.hidden = true;
      answer.classList.remove('error');
      evidence.replaceChildren();
      try {
        const response = await fetch('/answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: value, top_k: 5 }),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || '답변 요청을 처리하지 못했습니다.');
        answer.textContent = body.answer;
        const contexts = body.retrieved_context || [];
        evidenceSummary.textContent = `답변에 사용한 근거 ${contexts.length}개`;
        contexts.forEach(appendEvidence);
        result.hidden = false;
        status.textContent = '';
      } catch (error) {
        answer.textContent = error.message || '답변 요청 중 오류가 발생했습니다.';
        answer.classList.add('error');
        evidenceSummary.textContent = '답변에 사용한 근거 0개';
        result.hidden = false;
        status.textContent = '';
      } finally {
        submit.disabled = false;
      }
    }
    submit.addEventListener('click', ask);
    question.addEventListener('keydown', (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') ask();
    });
  </script>
</body>
</html>"""
