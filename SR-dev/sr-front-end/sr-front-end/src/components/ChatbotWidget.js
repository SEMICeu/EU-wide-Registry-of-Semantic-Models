import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createChatSession, streamChat } from '../services/chatService';

const STREAMING_TYPES = new Set(['message', 'token', 'chunk', 'delta']);
const FINAL_TYPE = 'final';
const ERROR_TYPE = 'error';
const STATUS_TYPE = 'status';
const ROUTING_TYPE = 'routing';
const DEBUG_TYPE = 'debug';
const DEFAULT_WELCOME =
  `🚀 Welcome to the SEMIC Semantic Registry Assistant PoC.

Ask me about the assets and their metadata currently residing in the SEMIC Semantic Registry.

How I retrieve information:

🧠 Graph traversal: schema-based answers
🔎 Vector search: semantic matching over titles and descriptions
⚡ Hybrid: combines both when needed
💡 Tip: include class and relationship names from the UML for more precise answers.

UML diagram: https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/html/overview.jpg`;

function stageToLabel(stage) {
  if (!stage) return 'Processing';
  if (stage === 'received') return '';
  return stage
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function isMarkdownTableLine(line) {
  return line.trim().startsWith('|') && line.trim().endsWith('|');
}

function isTableDivider(line) {
  const cleaned = line.replace(/\|/g, '').replace(/:/g, '').replace(/-/g, '').trim();
  return cleaned.length === 0 && line.includes('-');
}

function parseTableRow(line) {
  return line
    .trim()
    .slice(1, -1)
    .split('|')
    .map((cell) => cell.trim());
}

function renderInlineMarkdown(text) {
  if (!text) return '';
  const parts = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|https?:\/\/[^\s)]+(?:\([^\s)]*\))?)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith('**') && token.endsWith('**')) {
      parts.push(<strong key={`md-b-${key++}`}>{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('`') && token.endsWith('`')) {
      parts.push(<code key={`md-c-${key++}`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith('[')) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        parts.push(
          <a
            key={`md-a-${key++}`}
            className="chatbot-inline-link"
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        parts.push(token);
      }
    } else if (token.startsWith('http://') || token.startsWith('https://')) {
      let safeUrl = token;
      let trailing = '';
      while (/[.,!?;:]$/.test(safeUrl)) {
        trailing = safeUrl.slice(-1) + trailing;
        safeUrl = safeUrl.slice(0, -1);
      }
      parts.push(
        <a
          key={`md-u-${key++}`}
          className="chatbot-inline-link"
          href={safeUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          {safeUrl}
        </a>
      );
      if (trailing) parts.push(trailing);
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

function MarkdownLike({ text }) {
  if (!text) return null;
  const lines = text.split('\n');
  const blocks = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const rawLine = lines[i];
    const line = rawLine.trim();

    if (!line) {
      i += 1;
      continue;
    }

    if (line.startsWith('## ')) {
      blocks.push(<h4 key={`h2-${key++}`} className="chatbot-md-h">{renderInlineMarkdown(line.slice(3))}</h4>);
      i += 1;
      continue;
    }

    if (line.startsWith('### ')) {
      blocks.push(<h5 key={`h3-${key++}`} className="chatbot-md-sh">{renderInlineMarkdown(line.slice(4))}</h5>);
      i += 1;
      continue;
    }

    if (line.startsWith('> ')) {
      blocks.push(<blockquote key={`q-${key++}`} className="chatbot-md-quote">{renderInlineMarkdown(line.slice(2))}</blockquote>);
      i += 1;
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ''));
        i += 1;
      }
      blocks.push(
        <ul key={`ul-${key++}`} className="chatbot-md-list">
          {items.map((item, idx) => <li key={`li-${idx}`}>{renderInlineMarkdown(item)}</li>)}
        </ul>
      );
      continue;
    }

    if (isMarkdownTableLine(line) && i + 1 < lines.length && isTableDivider(lines[i + 1].trim())) {
      const headers = parseTableRow(lines[i]);
      i += 2;
      const rows = [];
      while (i < lines.length && isMarkdownTableLine(lines[i].trim())) {
        rows.push(parseTableRow(lines[i]));
        i += 1;
      }
      blocks.push(
        <div key={`tbl-wrap-${key++}`} className="chatbot-md-table-wrap">
          <table className="chatbot-md-table">
            <thead>
              <tr>
                {headers.map((h, idx) => <th key={`th-${idx}`}>{renderInlineMarkdown(h)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ridx) => (
                <tr key={`tr-${ridx}`}>
                  {row.map((cell, cidx) => <td key={`td-${ridx}-${cidx}`}>{renderInlineMarkdown(cell)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    const paragraph = [line];
    i += 1;
    while (i < lines.length && lines[i].trim() && !lines[i].trim().startsWith('## ') && !lines[i].trim().startsWith('### ')) {
      if (/^[-*]\s+/.test(lines[i].trim())) break;
      if (isMarkdownTableLine(lines[i].trim())) break;
      if (lines[i].trim().startsWith('> ')) break;
      paragraph.push(lines[i].trim());
      i += 1;
    }
    blocks.push(<p key={`p-${key++}`} className="chatbot-md-p">{renderInlineMarkdown(paragraph.join(' '))}</p>);
  }

  return <div className="chatbot-md">{blocks}</div>;
}

function AssistantMessage({ msg, isLoading, suggestedPrompts, onSelectPrompt }) {
  const statuses = (msg.statuses || []).filter((stage) => stage !== 'received');
  const debugItems = msg.debugEvents || [];
  const routing = msg.routing || null;
  const isWelcomeMessage = String(msg.id || '').startsWith('welcome');

  return (
    <div className={`chatbot-msg chatbot-msg--${msg.kind} chatbot-msg--assistant`}>
      {statuses.length > 0 && (
        <div className="chatbot-status-track">
          {statuses.map((stage, idx) => (
            <div key={`${stage}-${idx}`} className="chatbot-status-item">
              <span className="chatbot-status-dot" />
              <span>
                {stageToLabel(stage)}
                {isLoading && idx === statuses.length - 1 ? ' ...' : ''}
              </span>
            </div>
          ))}
          {isLoading && <div className="chatbot-status-spinner" aria-label="Processing" />}
        </div>
      )}

      {routing && (
        <details className="chatbot-routing-card">
          <summary>Routing metadata</summary>
          <div><b>Intent:</b> {routing.intent || 'N/A'}</div>
          <div><b>Route:</b> {routing.route || 'N/A'}</div>
          <div><b>Reason:</b> {routing.plan?.reason || 'N/A'}</div>
          <div><b>Question:</b> {routing.resolved_question || 'N/A'}</div>
        </details>
      )}

      {debugItems.length > 0 && (
        <details className="chatbot-debug-card">
          <summary>Context</summary>
          {debugItems.map((item, idx) => (
            <div className="chatbot-debug-item" key={`debug-${idx}`}>
              {item.cypher && (
                <>
                  <div className="chatbot-debug-label">Cypher</div>
                  <pre className="chatbot-code-block">{item.cypher}</pre>
                </>
              )}
              {item.context_preview && (
                <>
                  <div className="chatbot-debug-label">Context preview</div>
                  <pre className="chatbot-code-block">{JSON.stringify(item.context_preview, null, 2)}</pre>
                </>
              )}
            </div>
          ))}
        </details>
      )}

      <MarkdownLike text={msg.text || (msg.kind === 'stream' ? '...' : '')} />

      {isWelcomeMessage && suggestedPrompts.length > 0 && (
        <details className="chatbot-suggestions chatbot-suggestions--in-message">
          <summary className="chatbot-suggestions-label">Example questions</summary>
          <div className="chatbot-suggestion-list">
            {suggestedPrompts.map((prompt, idx) => (
              <button
                key={`prompt-${idx}`}
                className="chatbot-suggestion-btn"
                onClick={() => onSelectPrompt(prompt)}
                title={prompt}
                type="button"
              >
                {prompt}
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

export default function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      kind: 'final',
      text: DEFAULT_WELCOME
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [suggestedPrompts, setSuggestedPrompts] = useState([]);
  const [selectedPrompt, setSelectedPrompt] = useState('');
  const [toastError, setToastError] = useState('');
  const pendingAssistantId = useRef(null);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);

  const canSend = useMemo(
    () => input.trim().length > 0 && !isLoading && !isSessionLoading,
    [input, isLoading, isSessionLoading]
  );

  useEffect(() => {
    const list = scrollRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, isLoading, isOpen]);

  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
    };
  }, []);

  useEffect(() => {
    if (!toastError) return undefined;
    const timer = setTimeout(() => setToastError(''), 4500);
    return () => clearTimeout(timer);
  }, [toastError]);

  const bootstrapSession = async () => {
    if (isSessionLoading) return;
    setIsSessionLoading(true);
    try {
      const data = await createChatSession();
      setSessionId(data.sessionId);
      setSuggestedPrompts(data.suggestedPrompts);
      setSelectedPrompt('');
      setMessages([
        {
          id: `welcome-${Date.now()}`,
          role: 'assistant',
          kind: 'final',
          text: data.welcomeMessage || DEFAULT_WELCOME
        }
      ]);
    } catch (err) {
      setToastError(err.message || 'Could not create chat session.');
    } finally {
      setIsSessionLoading(false);
    }
  };

  const startNewChat = async () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    pendingAssistantId.current = null;
    setIsLoading(false);
    setInput('');
    setSessionId('');
    setSuggestedPrompts([]);
    setSelectedPrompt('');
    await bootstrapSession();
  };

  useEffect(() => {
    if (!isOpen || sessionId) return;
    bootstrapSession();
  }, [isOpen, sessionId]);

  const appendMessage = (message) => {
    setMessages((prev) => [...prev, message]);
  };

  const updatePendingAssistant = (updater) => {
    const targetId = pendingAssistantId.current;
    if (!targetId) return;
    setMessages((prev) =>
      prev.map((msg) => (msg.id === targetId ? { ...msg, ...updater(msg) } : msg))
    );
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    pendingAssistantId.current = assistantId;
    setInput('');
    setIsLoading(true);

    appendMessage({ id: userId, role: 'user', kind: 'user', text });
    appendMessage({
      id: assistantId,
      role: 'assistant',
      kind: 'stream',
      text: '',
      done: false,
      statuses: [],
      routing: null,
      debugEvents: []
    });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat({
        message: text,
        sessionId,
        signal: controller.signal,
        onEvent: ({ type, payload, text: eventText }) => {
          const sid = payload?.session_id;
          if (sid) setSessionId(sid);

          if (type === ERROR_TYPE) {
            const errorMessage = payload?.message || 'Chat request failed.';
            updatePendingAssistant(() => ({
              kind: 'error',
              text: errorMessage,
              done: true
            }));
            setToastError(errorMessage);
            return;
          }

          if (type === FINAL_TYPE) {
            updatePendingAssistant((msg) => ({
              kind: 'final',
              text: payload?.answer || msg.text || '',
              done: true
            }));
            return;
          }

          if (STREAMING_TYPES.has(type)) {
            if (!eventText) return;
            updatePendingAssistant((msg) => ({
              kind: 'stream',
              text: `${msg.text || ''}${eventText}`,
              done: false
            }));
            return;
          }

          if (type === STATUS_TYPE) {
            const stage = payload?.stage;
            if (!stage) return;
            updatePendingAssistant((msg) => ({
              statuses: msg.statuses?.includes(stage) ? msg.statuses : [...(msg.statuses || []), stage]
            }));
            return;
          }

          if (type === ROUTING_TYPE) {
            updatePendingAssistant(() => ({ routing: payload || null }));
            return;
          }

          if (type === DEBUG_TYPE) {
            updatePendingAssistant((msg) => ({
              debugEvents: [...(msg.debugEvents || []), payload || {}]
            }));
          }
        },
        onComplete: ({ sessionId: sid }) => {
          if (sid) setSessionId(sid);
        }
      });

      updatePendingAssistant((msg) => ({
        kind: msg.kind === 'stream' ? 'final' : msg.kind,
        done: true
      }));
    } catch (err) {
      if (err.name !== 'AbortError') {
        const errorMessage = err.message || 'Could not contact chat endpoint.';
        updatePendingAssistant(() => ({
          kind: 'error',
          text: errorMessage,
          done: true
        }));
        setToastError(errorMessage);
      }
    } finally {
      setIsLoading(false);
      pendingAssistantId.current = null;
      abortRef.current = null;
    }
  };

  const handleInputKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className={`chatbot-widget${isExpanded ? ' chatbot-widget--fullscreen' : ''}`}>
      {isOpen && (
        <section
          className={`chatbot-panel${isExpanded ? ' chatbot-panel--fullscreen' : ''}`}
          aria-label="Chat assistant"
        >
          <header className="chatbot-header">
            <div>
              <div className="chatbot-title">Semantic Registry Assistant</div>
              <div className="chatbot-subtitle">graph traversal and/or content similarity search</div>
            </div>
            <div className="chatbot-header-actions">
              <button
                className="chatbot-new-btn"
                onClick={startNewChat}
                aria-label="Start new chat"
                title="New chat"
                disabled={isSessionLoading}
              >
                New
              </button>
              <button
                className="chatbot-expand-btn"
                onClick={() => setIsExpanded((prev) => !prev)}
                aria-label={isExpanded ? 'Exit fullscreen' : 'Fullscreen'}
                title={isExpanded ? 'Exit fullscreen' : 'Fullscreen'}
              >
                {isExpanded ? '⤡' : '⤢'}
              </button>
              <button
                className="chatbot-close-btn"
                onClick={() => {
                  setIsOpen(false);
                  setIsExpanded(false);
                }}
                aria-label="Close chatbot"
              >
                ×
              </button>
            </div>
          </header>

          <div className="chatbot-messages" ref={scrollRef}>
            {isSessionLoading && (
              <div className="chatbot-msg chatbot-msg--assistant chatbot-msg--typing">
                Starting session...
              </div>
            )}
            {messages.map((msg) => (msg.role === 'assistant' ? (
              <AssistantMessage
                key={msg.id}
                msg={msg}
                isLoading={isLoading && pendingAssistantId.current === msg.id}
                suggestedPrompts={!isSessionLoading && !isLoading ? suggestedPrompts : []}
                onSelectPrompt={(prompt) => {
                  setSelectedPrompt(prompt);
                  setInput(prompt);
                }}
              />
            ) : (
              <div key={msg.id} className={`chatbot-msg chatbot-msg--${msg.kind} chatbot-msg--${msg.role}`}>
                {msg.text}
              </div>
            )))}
            {isLoading && (
              <div className="chatbot-msg chatbot-msg--assistant chatbot-msg--typing">
                Thinking...
              </div>
            )}
          </div>

          <div className="chatbot-input-wrap">
            <textarea
              className="chatbot-input"
              rows={2}
              placeholder="Ask a question..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
            />
            <button
              className="chatbot-send-btn"
              onClick={sendMessage}
              disabled={!canSend}
            >
              Send
            </button>
          </div>
        </section>
      )}

      {!isOpen && (
        <button
          className="chatbot-fab"
          onClick={() => setIsOpen(true)}
          aria-expanded={false}
          aria-label="Open chatbot"
        >
          Chat
        </button>
      )}

      {toastError && <div className="chatbot-error-toast">{toastError}</div>}
    </div>
  );
}

