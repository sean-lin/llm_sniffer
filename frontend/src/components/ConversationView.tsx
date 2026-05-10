import type { RequestSummary } from '../types';

interface Props {
  requests: RequestSummary[];
  sessionId: string;
  onSelectRequest: (id: number) => void;
}

export default function ConversationView({ requests, sessionId, onSelectRequest }: Props) {
  if (requests.length === 0) {
    return <div className="empty-state"><p>No requests in this session</p></div>;
  }

  return (
    <div className="conversation-view">
      <div className="session-meta-bar">
        <span className="meta-item" title="Session ID">Session: <code>{sessionId}</code></span>
      </div>
      <h2>Conversation ({requests.length} turns)</h2>
      <div className="turns-list">
        {requests.map(req => (
          <div key={req.id} className="turn-card" onClick={() => onSelectRequest(req.id)}>
            <div className="turn-header">
              <span className={`badge badge-${req.client_type}`}>{req.client_type}</span>
              <span className="model-name">{req.model}</span>
              <span className={`status-badge ${req.status_code === 200 ? 'success' : 'error'}`}>
                {req.status_code}
              </span>
              {req.stream && <span className="badge badge-stream">stream</span>}
              <span className="duration">{req.duration_ms}ms</span>
              <span className="timestamp">{formatTime(req.timestamp)}</span>
            </div>
            <div className="turn-meta">
              {req.user_agent && (
                <span className="meta-item" title="User-Agent">UA: {truncate(req.user_agent, 40)}</span>
              )}
              <TokenUsageDisplay response={req.response_body} />
            </div>
            <div className="turn-preview">
              <div className="turn-user-msg">{extractUserPreview(req)}</div>
              <div className="turn-assistant-msg">{extractAssistantPreview(req)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TokenUsageDisplay({ response }: { response: RequestSummary['response_body'] }) {
  if (!response) return null;

  const usage = (response as Record<string, unknown>).usage as Record<string, number> | undefined;
  if (!usage) return null;

  let prompt = 0;
  let completion = 0;

  // OpenAI format
  if (usage.prompt_tokens !== undefined) {
    prompt = usage.prompt_tokens;
    completion = usage.completion_tokens ?? 0;
  }
  // Anthropic format
  else if (usage.input_tokens !== undefined) {
    prompt = usage.input_tokens;
    completion = usage.output_tokens ?? 0;
  }

  if (prompt === 0 && completion === 0) return null;

  return (
    <span className="meta-item token-usage">
      Tokens: {prompt} + {completion} = {prompt + completion}
    </span>
  );
}

function extractUserPreview(req: RequestSummary): string {
  const messages = req.request_body?.messages;
  if (!messages) return '';
  const userMsgs = messages.filter(m => m.role === 'user');
  const last = userMsgs[userMsgs.length - 1];
  if (!last) return '';
  if (typeof last.content === 'string') return truncate(last.content);
  if (Array.isArray(last.content)) {
    const textBlock = last.content.find(b => b.type === 'text');
    return truncate(textBlock?.text || '[media]');
  }
  return '';
}

function extractAssistantPreview(req: RequestSummary): string {
  const resp = req.response_body;
  if (!resp) return '';
  // OpenAI format
  if (resp.choices && resp.choices[0]?.message) {
    const msg = resp.choices[0].message;
    if (msg.tool_calls && msg.tool_calls.length > 0) {
      return `[Tool: ${msg.tool_calls.map(tc => tc.function.name).join(', ')}]`;
    }
    if (msg.reasoning_content) {
      return '[Thinking] ' + truncate(msg.reasoning_content);
    }
    if (typeof msg.content === 'string') return truncate(msg.content);
  }
  // Anthropic format
  if (resp.content && Array.isArray(resp.content)) {
    const thinkingBlock = resp.content.find(b => b.type === 'thinking');
    if (thinkingBlock && 'thinking' in thinkingBlock) {
      return '[Thinking] ' + truncate(thinkingBlock.thinking as string);
    }
    const textBlock = resp.content.find(b => b.type === 'text');
    if (textBlock && 'text' in textBlock) return truncate(textBlock.text as string);
  }
  return '';
}

function truncate(s: string, len = 120): string {
  return s.length > len ? s.slice(0, len) + '...' : s;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}
