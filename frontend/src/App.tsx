import { useState, useEffect, useCallback } from 'react';
import type { Session, RequestSummary, RequestDetail } from './types';
import { fetchSessions, fetchSessionRequests, fetchRequestDetail } from './api';
import SessionList from './components/SessionList';
import ConversationView from './components/ConversationView';
import TurnDetail from './components/TurnDetail';

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [requests, setRequests] = useState<RequestSummary[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<RequestDetail | null>(null);

  const loadSessions = useCallback(async () => {
    const data = await fetchSessions();
    setSessions(data);
  }, []);

  useEffect(() => {
    loadSessions();
    const interval = setInterval(loadSessions, 5000);
    return () => clearInterval(interval);
  }, [loadSessions]);

  useEffect(() => {
    if (selectedSession) {
      fetchSessionRequests(selectedSession).then(setRequests);
    } else {
      setRequests([]);
    }
  }, [selectedSession]);

  const handleSelectRequest = async (id: number) => {
    const detail = await fetchRequestDetail(id);
    setSelectedRequest(detail);
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>LLM Sniffer</h1>
        </div>
        <SessionList
          sessions={sessions}
          selected={selectedSession}
          onSelect={setSelectedSession}
          onRefresh={loadSessions}
        />
      </aside>
      <main className="main-panel">
        {selectedRequest ? (
          <TurnDetail
            detail={selectedRequest}
            onBack={() => setSelectedRequest(null)}
          />
        ) : selectedSession ? (
          <ConversationView
            requests={requests}
            onSelectRequest={handleSelectRequest}
          />
        ) : (
          <div className="empty-state">
            <p>Select a session from the sidebar to view conversations</p>
          </div>
        )}
      </main>
    </div>
  );
}
