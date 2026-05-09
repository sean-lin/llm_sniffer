import type { Message } from '../types';

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
  const content = message.content;

  if (typeof content === 'string') {
    return <div className="message-content"><pre className="message-text">{content}</pre></div>;
  }

  if (Array.isArray(content)) {
    return (
      <div className="message-content">
        {content.map((block, i) => {
          if (block.type === 'text' && block.text) {
            return <pre key={i} className="message-text">{block.text}</pre>;
          }
          if (block.type === 'image_url' && block.image_url) {
            return <img key={i} className="inline-image" src={block.image_url.url} alt="content" />;
          }
          if (block.type === 'tool_use') {
            return (
              <div key={i} className="tool-use-inline">
                <span className="tool-label">Tool: {(block as Record<string, unknown>).name as string}</span>
                <pre>{JSON.stringify((block as Record<string, unknown>).input, null, 2)}</pre>
              </div>
            );
          }
          if (block.type === 'tool_result') {
            return (
              <div key={i} className="tool-result-inline">
                <span className="tool-label">Tool Result</span>
                <pre>{JSON.stringify(block, null, 2)}</pre>
              </div>
            );
          }
          return <pre key={i} className="unknown-block">{JSON.stringify(block, null, 2)}</pre>;
        })}
      </div>
    );
  }

  return <div className="message-content"><pre>{JSON.stringify(content, null, 2)}</pre></div>;
}
