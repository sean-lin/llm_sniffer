import { useState } from 'react';
import Markdown from 'react-markdown';

interface ToolDef {
  type?: string;
  function?: {
    name: string;
    description?: string;
    parameters?: Record<string, unknown>;
  };
  name?: string;
  description?: string;
  input_schema?: Record<string, unknown>;
}

interface Props {
  tools: unknown[];
}

export default function ToolsTableDisplay({ tools }: Props) {
  const [popover, setPopover] = useState<{ name: string; description: string } | null>(null);

  const parsed = (tools as ToolDef[]).map(t => {
    if (t.function) {
      return {
        name: t.function.name,
        description: t.function.description || '',
        parameters: t.function.parameters,
      };
    }
    return {
      name: t.name || '',
      description: t.description || '',
      parameters: t.input_schema,
    };
  });

  return (
    <div className="tools-table-section">
      <table className="tools-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Parameters</th>
          </tr>
        </thead>
        <tbody>
          {parsed.map((tool, i) => (
            <tr key={i}>
              <td className="tool-name-cell">{tool.name}</td>
              <td
                className="tool-desc-cell"
                onClick={() => tool.description && setPopover({ name: tool.name, description: tool.description })}
              >
                <span className="tool-desc-truncated">{tool.description || '-'}</span>
              </td>
              <td className="tool-params-cell">
                {tool.parameters ? (
                  <ParamsDisplay params={tool.parameters} />
                ) : (
                  <span className="no-params">-</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {popover && (
        <div className="tool-popover-overlay" onClick={() => setPopover(null)}>
          <div className="tool-popover" onClick={e => e.stopPropagation()}>
            <div className="tool-popover-header">
              <span className="tool-popover-name">{popover.name}</span>
              <button className="tool-popover-close" onClick={() => setPopover(null)}>&times;</button>
            </div>
            <div className="tool-popover-body">
              <Markdown>{popover.description}</Markdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ParamsDisplay({ params }: { params: Record<string, unknown> }) {
  const properties = (params.properties || {}) as Record<string, { type?: string; description?: string }>;
  const required = (params.required || []) as string[];
  const entries = Object.entries(properties);

  if (entries.length === 0) {
    return <span className="no-params">none</span>;
  }

  return (
    <div className="params-list">
      {entries.map(([name, schema]) => (
        <div key={name} className="param-item">
          <code className="param-name">
            {name}{required.includes(name) && <span className="param-required">*</span>}
          </code>
          <span className="param-type">{schema.type || 'any'}</span>
          {schema.description && <span className="param-desc">{schema.description}</span>}
        </div>
      ))}
    </div>
  );
}
