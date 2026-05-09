import type { RequestDetail, Message } from '../types';
import MessageBubble from './MessageBubble';
import ToolUseDisplay from './ToolUseDisplay';
import MediaDisplay from './MediaDisplay';

interface Props {
  detail: RequestDetail;
  onBack: () => void;
}

export default function TurnDetail({ detail, onBack }: Props) {
  const reqMessages = detail.request_body?.messages || [];
  const respMessage = getResponseMessage(detail);

  return (
    <div className="turn-detail">
      <div className="turn-detail-header">
        <button className="back-btn" onClick={onBack}>&larr; Back</button>
        <span className={`badge badge-${detail.client_type}`}>{detail.client_type}</span>
        <span className="model-name">{detail.model}</span>
        <span className="duration">{detail.duration_ms}ms</span>
        <span className={`status-badge ${detail.status_code === 200 ? 'success' : 'error'}`}>
          {detail.status_code}
        </span>
        <span className="timestamp">{new Date(detail.timestamp).toLocaleString()}</span>
      </div>

      {detail.error && (
        <div className="error-banner">Error: {detail.error}</div>
      )}

      <div className="messages-section">
        <h3>Request Messages</h3>
        {reqMessages.map((msg, i) => (
          <div key={i} className={`message-wrapper role-${msg.role}`}>
            <div className="message-role">{msg.role}</div>
            <MessageBubble message={msg} />
            {msg.tool_calls && <ToolUseDisplay toolCalls={msg.tool_calls} />}
            <MediaDisplay media={detail.media.filter(m => m.role === 'request' && m.message_index === i)} />
          </div>
        ))}

        {respMessage && (
          <>
            <h3>Response</h3>
            <div className={`message-wrapper role-assistant`}>
              <div className="message-role">assistant</div>
              <MessageBubble message={respMessage} />
              {respMessage.tool_calls && <ToolUseDisplay toolCalls={respMessage.tool_calls} />}
              <MediaDisplay media={detail.media.filter(m => m.role === 'response')} />
            </div>
          </>
        )}
      </div>

      <details className="raw-json">
        <summary>Raw Request JSON</summary>
        <pre>{JSON.stringify(detail.request_body, null, 2)}</pre>
      </details>
      <details className="raw-json">
        <summary>Raw Response JSON</summary>
        <pre>{JSON.stringify(detail.response_body, null, 2)}</pre>
      </details>
    </div>
  );
}

function getResponseMessage(detail: RequestDetail): Message | null {
  const resp = detail.response_body;
  if (!resp) return null;
  if (resp.choices && resp.choices[0]?.message) {
    return resp.choices[0].message;
  }
  if (resp.content) {
    return { role: 'assistant', content: resp.content };
  }
  return null;
}
