import { useState } from 'react';
import type { ToolCall } from '../types';

interface Props {
  toolCalls: ToolCall[];
}

export default function ToolUseDisplay({ toolCalls }: Props) {
  const [expandedContent, setExpandedContent] = useState<{ title: string; content: string } | null>(null);

  return (
    <div className="tool-use-display">
      <h4>Tool Calls</h4>
      {toolCalls.map((tc, i) => {
        let parsedArgs: unknown;
        try {
          parsedArgs = JSON.parse(tc.function.arguments);
        } catch {
          parsedArgs = tc.function.arguments;
        }
        const argsStr = typeof parsedArgs === 'string' ? parsedArgs : JSON.stringify(parsedArgs, null, 2);

        return (
          <div key={i} className="tool-call-card">
            <div className="tool-call-header">
              <span className="tool-call-name">{tc.function.name}</span>
              <span className="tool-call-id">ID: {tc.id}</span>
            </div>
            <div className="tool-call-args">
              <span className="label">Arguments:</span>
              <pre
                className="tool-content-truncated"
                onClick={() => setExpandedContent({ title: `${tc.function.name} - Arguments`, content: argsStr })}
              >
                {argsStr}
              </pre>
            </div>
          </div>
        );
      })}

      {expandedContent && (
        <div className="tool-popover-overlay" onClick={() => setExpandedContent(null)}>
          <div className="tool-popover" onClick={e => e.stopPropagation()}>
            <div className="tool-popover-header">
              <span className="tool-popover-name">{expandedContent.title}</span>
              <button className="tool-popover-close" onClick={() => setExpandedContent(null)}>&times;</button>
            </div>
            <div className="tool-popover-body">
              <pre className="tool-popover-pre">{expandedContent.content}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
