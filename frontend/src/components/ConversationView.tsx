import type { RequestSummary } from '../types';

interface Props {
  requests: RequestSummary[];
  onSelectRequest: (id: number) => void;
}

export default function ConversationView({ requests, onSelectRequest }: Props) {
  if (requests.length === 0) {
    return <div className="empty-state"><p>No requests in this session</p></div>;
  }

  return (
    <div className="conversation-view">
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
    if (typeof msg.content === 'string') return truncate(msg.content);
  }
  // Anthropic format
  if (resp.content && Array.isArray(resp.content)) {
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
