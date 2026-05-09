import type { ToolCall } from '../types';

interface Props {
  toolCalls: ToolCall[];
}

export default function ToolUseDisplay({ toolCalls }: Props) {
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

        return (
          <div key={i} className="tool-call-card">
            <div className="tool-call-header">
              <span className="tool-call-name">{tc.function.name}</span>
              <span className="tool-call-id">ID: {tc.id}</span>
            </div>
            <div className="tool-call-args">
              <span className="label">Arguments:</span>
              <pre>{typeof parsedArgs === 'string' ? parsedArgs : JSON.stringify(parsedArgs, null, 2)}</pre>
            </div>
          </div>
        );
      })}
    </div>
  );
}
