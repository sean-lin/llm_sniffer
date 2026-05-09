import type { Session } from '../types';
import { deleteSession } from '../api';

interface Props {
  sessions: Session[];
  selected: string | null;
  onSelect: (id: string) => void;
  onRefresh: () => void;
}

export default function SessionList({ sessions, selected, onSelect, onRefresh }: Props) {
  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (confirm('Delete this session and all its data?')) {
      await deleteSession(id);
      onRefresh();
    }
  };

  return (
    <div className="session-list">
      {sessions.length === 0 ? (
        <div className="empty-sessions">No sessions yet</div>
      ) : (
        sessions.map(s => (
          <div
            key={s.id}
            className={`session-item ${selected === s.id ? 'active' : ''}`}
            onClick={() => onSelect(s.id)}
          >
            <div className="session-name">{s.name || 'Unnamed'}</div>
            <div className="session-meta">
              <span>{s.request_count} requests</span>
              <span>{formatTime(s.last_active)}</span>
            </div>
            <button className="delete-btn" onClick={e => handleDelete(e, s.id)} title="Delete">
              &times;
            </button>
          </div>
        ))
      )}
    </div>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}
