const CHAT_API_BASE =
  process.env.REACT_APP_CHAT_API_URL ||
  process.env.REACT_APP_API_URL ||
  '/semantic-registry';

function extractEventText(payload) {
  if (!payload || typeof payload !== 'object') return '';
  return (
    payload.answer ||
    payload.message ||
    payload.text ||
    payload.content ||
    payload.delta ||
    payload.token ||
    ''
  );
}

function parseSseBlock(block) {
  const lines = block.split('\n');
  let eventType = 'message';
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventType = line.slice(6).trim() || 'message';
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }

  const rawData = dataLines.join('\n');
  if (!rawData) {
    return { type: eventType, payload: {} };
  }

  try {
    return { type: eventType, payload: JSON.parse(rawData) };
  } catch {
    return { type: eventType, payload: { message: rawData } };
  }
}

export async function streamChat({ message, sessionId, signal, onEvent, onComplete }) {
  const response = await fetch(`${CHAT_API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId || null }),
    signal
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Chat stream failed with status ${response.status}`);
  }

  if (!response.body) {
    throw new Error('No response stream received from chat endpoint.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let latestSessionId = sessionId || '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';

    for (const block of blocks) {
      if (!block.trim()) continue;
      const event = parseSseBlock(block);
      const sid = event.payload?.session_id;
      if (sid) latestSessionId = sid;
      onEvent?.({
        type: event.type,
        payload: event.payload || {},
        text: extractEventText(event.payload || {})
      });
    }
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    const sid = event.payload?.session_id;
    if (sid) latestSessionId = sid;
    onEvent?.({
      type: event.type,
      payload: event.payload || {},
      text: extractEventText(event.payload || {})
    });
  }

  onComplete?.({ sessionId: latestSessionId });
  return { sessionId: latestSessionId };
}

export async function createChatSession(signal) {
  const response = await fetch(`${CHAT_API_BASE}/api/chat/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Session creation failed with status ${response.status}`);
  }

  const data = await response.json();
  return {
    sessionId: data.session_id || '',
    welcomeMessage: data.welcome_message || '',
    suggestedPrompts: Array.isArray(data.suggested_prompts) ? data.suggested_prompts : []
  };
}

