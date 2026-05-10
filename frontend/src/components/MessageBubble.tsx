import { useState } from 'react';
import type { Message } from '../types';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const [expandedContent, setExpandedContent] = useState<{ title: string; content: string } | null>(null);
  const content = message.content;

  // Special handling for tool role messages (tool results)
  if (message.role === 'tool') {
    const resultStr = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
    return (
      <div className="message-content">
        {message.tool_call_id && (
          <div className="tool-result-header">
            <span className="tool-call-id-label">tool_call_id: {message.tool_call_id}</span>
          </div>
        )}
        <pre
          className="tool-content-truncated"
          onClick={() => setExpandedContent({ title: `Tool Result (${message.tool_call_id || ''})`, content: resultStr })}
        >
          {resultStr}
        </pre>
        {expandedContent && <ExpandPopover data={expandedContent} onClose={() => setExpandedContent(null)} />}
      </div>
    );
  }

  if (typeof content === 'string') {
    return (
      <div className="message-content">
        {message.reasoning_content && (
          <details className="thinking-block">
            <summary>Thinking</summary>
            <pre className="thinking-text">{message.reasoning_content}</pre>
          </details>
        )}
        <pre className="message-text">{content}</pre>
      </div>
    );
  }

  if (Array.isArray(content)) {
    return (
      <div className="message-content">
        {content.map((block, i) => {
          if (block.type === 'thinking' && (block as Record<string, unknown>).thinking) {
            return (
              <details key={i} className="thinking-block">
                <summary>Thinking</summary>
                <pre className="thinking-text">{(block as Record<string, unknown>).thinking as string}</pre>
              </details>
            );
          }
          if (block.type === 'text' && block.text) {
            return <pre key={i} className="message-text">{block.text}</pre>;
          }
          if (block.type === 'image_url' && block.image_url) {
            return <img key={i} className="inline-image" src={block.image_url.url} alt="content" />;
          }
          if (block.type === 'tool_use') {
            const inputStr = JSON.stringify((block as Record<string, unknown>).input, null, 2);
            return (
              <ToolBlock
                key={i}
                label={`Tool: ${(block as Record<string, unknown>).name as string}`}
                content={inputStr}
                title={`${(block as Record<string, unknown>).name as string} - Input`}
              />
            );
          }
          if (block.type === 'tool_result') {
            const resultContent = (block as Record<string, unknown>).content;
            const resultStr = typeof resultContent === 'string' ? resultContent : JSON.stringify(block, null, 2);
            return (
              <ToolBlock
                key={i}
                label="Tool Result"
                content={resultStr}
                title={`Tool Result (${(block as Record<string, unknown>).tool_use_id || ''})`}
              />
            );
          }
          return <pre key={i} className="unknown-block">{JSON.stringify(block, null, 2)}</pre>;
        })}
      </div>
    );
  }

  return <div className="message-content"><pre>{JSON.stringify(content, null, 2)}</pre></div>;
}

function ToolBlock({ label, content, title }: { label: string; content: string; title: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <div className="tool-use-inline">
        <span className="tool-label">{label}</span>
        <pre
          className="tool-content-truncated"
          onClick={() => setExpanded(true)}
        >
          {content}
        </pre>
      </div>
      {expanded && <ExpandPopover data={{ title, content }} onClose={() => setExpanded(false)} />}
    </>
  );
}

function ExpandPopover({ data, onClose }: { data: { title: string; content: string }; onClose: () => void }) {
  return (
    <div className="tool-popover-overlay" onClick={onClose}>
      <div className="tool-popover" onClick={e => e.stopPropagation()}>
        <div className="tool-popover-header">
          <span className="tool-popover-name">{data.title}</span>
          <button className="tool-popover-close" onClick={onClose}>&times;</button>
        </div>
        <div className="tool-popover-body">
          <pre className="tool-popover-pre">{data.content}</pre>
        </div>
      </div>
    </div>
  );
}
