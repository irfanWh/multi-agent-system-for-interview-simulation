"use client";

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { WS_URL } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { VoiceCall } from './components/VoiceCall';

interface Message {
  id: string;
  sender: 'server' | 'client' | 'system';
  text: string;
  type?: 'question' | 'follow_up' | 'session_complete' | 'error' | 'transcript';
  anchor_title?: string;
}

export default function InterviewSession() {
  const { id } = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // Start with chosen mode from query param, or prompt user
  const initialMode = searchParams.get('mode') as 'text' | 'voice' | null;
  const accessCode = searchParams.get('access_code') || (typeof window !== 'undefined' ? sessionStorage.getItem(`access_code:${id}`) : null);
  const [mode, setMode] = useState<'text' | 'voice' | null>(initialMode);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [currentAnchor, setCurrentAnchor] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!id || mode !== 'text') return;

    const wsAccess = accessCode ? `?access_code=${encodeURIComponent(accessCode)}` : '';
    const ws = new WebSocket(`${WS_URL}/session/${id}${wsAccess}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "session_start", session_id: id, mode: "text" }));
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) return; // Text mode ignores binary
      
      const data = JSON.parse(event.data);

      if (data.anchor_title) {
        setCurrentAnchor(data.anchor_title);
      }

      if (data.type === 'transcript') {
        return; // Ignore in text mode
      }

      const text = data.text || data.message || '';
      if (!text && data.type !== 'session_complete') return;

      if (text) {
        setMessages(prev => [...prev, {
          id: Date.now().toString() + Math.random(),
          sender: data.type === 'error' ? 'system' : 'server',
          text,
          type: data.type,
          anchor_title: data.anchor_title
        }]);
      }

      if (data.type === 'session_complete') {
        setIsComplete(true);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => { ws.close(); };
  }, [id, mode, accessCode]);

  const sendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || !wsRef.current || !isConnected) return;

    wsRef.current.send(JSON.stringify({ type: 'answer', text: inputValue }));
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      sender: 'client',
      text: inputValue
    }]);
    setInputValue('');
  };

  if (!mode) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-slate-900 gap-8 text-white">
        <h1 className="text-3xl font-bold">Choose Interview Mode</h1>
        <div className="flex gap-6">
          <Button onClick={() => setMode('voice')} className="bg-indigo-600 hover:bg-indigo-500 rounded-xl px-8 py-6 text-xl">
            🎙️ Voice Call (Recommended)
          </Button>
          <Button onClick={() => setMode('text')} variant="outline" className="text-slate-300 border-slate-600 rounded-xl px-8 py-6 text-xl">
            ⌨️ Text Chat
          </Button>
        </div>
      </div>
    );
  }

  if (mode === 'voice') {
    return (
      <div className="h-screen bg-slate-900 text-slate-100">
        <VoiceCall 
          sessionId={id as string} 
          wsUrl={WS_URL} 
          accessCode={accessCode || undefined}
          onComplete={() => router.push(`/session/${id}/report`)} 
        />
      </div>
    );
  }

  // Text Mode UI
  return (
    <div className="session-page">
      {/* Header */}
      <div className="session-header">
        <div className="session-header-left">
          <div className={`connection-dot ${isConnected ? 'connected' : 'disconnected'}`} />
          <h1 className="session-title">Live Interview (Text)</h1>
          {currentAnchor && !isComplete && (
            <div className="topic-pill">
              <span className="topic-label">Topic</span>
              <span className="topic-name">{currentAnchor}</span>
            </div>
          )}
        </div>
        <div className="session-header-right">
          {isComplete && (
            <Button onClick={() => router.push(`/session/${id}/report`)}>View Report</Button>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="chat-container">
        <div className="messages-area">
          {messages.length === 0 && isConnected && (
            <div className="chat-placeholder">
              <div className="chat-placeholder-icon">🎯</div>
              <p>The interviewer is preparing your session…</p>
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message-row ${msg.sender === 'client' ? 'message-row-right' : msg.sender === 'system' ? 'message-row-center' : 'message-row-left'}`}
            >
              {msg.sender === 'server' && (
                <div className="avatar avatar-interviewer">AI</div>
              )}
              <div className={`bubble ${
                msg.sender === 'client'
                  ? 'bubble-candidate'
                  : msg.sender === 'system'
                    ? 'bubble-system'
                    : 'bubble-interviewer'
              }`}>
                {msg.anchor_title && msg.type === 'question' && (
                  <div className="bubble-anchor-tag">📌 {msg.anchor_title}</div>
                )}
                <div className="bubble-text">{msg.text}</div>
              </div>
              {msg.sender === 'client' && (
                <div className="avatar avatar-candidate">You</div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        {!isComplete && (
          <div className="input-area">
            <form onSubmit={sendMessage} className="text-input-form">
              <textarea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Type your answer… (Enter to send, Shift+Enter for new line)"
                disabled={!isConnected}
                className="answer-textarea"
                rows={2}
              />
              <Button type="submit" disabled={!isConnected || !inputValue.trim()}>
                Send →
              </Button>
            </form>
          </div>
        )}

        {isComplete && (
          <div className="complete-banner">
            <span>✅ Interview complete! Your responses have been recorded and are being evaluated.</span>
            <Button onClick={() => router.push(`/session/${id}/report`)}>See Dashboard & Report</Button>
          </div>
        )}
      </div>

      <style>{`
        .session-page {
          display: flex;
          flex-direction: column;
          height: 100vh;
          background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
          font-family: 'Inter', system-ui, sans-serif;
          color: #e2e8f0;
        }
        .session-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          background: rgba(15,23,42,0.8);
          border-bottom: 1px solid rgba(255,255,255,0.08);
          backdrop-filter: blur(12px);
          flex-shrink: 0;
        }
        .session-header-left { display: flex; align-items: center; gap: 12px; }
        .session-header-right { display: flex; align-items: center; gap: 12px; }
        .connection-dot {
          width: 10px; height: 10px; border-radius: 50%;
          flex-shrink: 0;
          box-shadow: 0 0 8px currentColor;
        }
        .connection-dot.connected { background: #22c55e; color: #22c55e; }
        .connection-dot.disconnected { background: #ef4444; color: #ef4444; }
        .session-title { font-size: 18px; font-weight: 700; color: #f1f5f9; }
        .topic-pill {
          display: flex; align-items: center; gap: 6px;
          background: rgba(99,102,241,0.2);
          border: 1px solid rgba(99,102,241,0.4);
          border-radius: 999px;
          padding: 4px 12px;
          font-size: 12px;
        }
        .topic-label { color: #818cf8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
        .topic-name { color: #c7d2fe; }
        .chat-container {
          display: flex;
          flex-direction: column;
          flex: 1;
          overflow: hidden;
          max-width: 900px;
          width: 100%;
          margin: 0 auto;
          padding: 0 16px;
        }
        .messages-area {
          flex: 1;
          overflow-y: auto;
          padding: 24px 0;
          display: flex;
          flex-direction: column;
          gap: 16px;
          scroll-behavior: smooth;
        }
        .messages-area::-webkit-scrollbar { width: 4px; }
        .messages-area::-webkit-scrollbar-track { background: transparent; }
        .messages-area::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 2px; }
        .chat-placeholder {
          display: flex; flex-direction: column;
          align-items: center; justify-content: center;
          gap: 12px; flex: 1; color: #64748b; font-size: 14px;
        }
        .chat-placeholder-icon { font-size: 36px; }
        .message-row {
          display: flex;
          align-items: flex-end;
          gap: 10px;
        }
        .message-row-right { flex-direction: row-reverse; }
        .message-row-center { justify-content: center; }
        .avatar {
          width: 32px; height: 32px; border-radius: 50%;
          display: flex; align-items: center; justify-content: center;
          font-size: 10px; font-weight: 700;
          flex-shrink: 0;
        }
        .avatar-interviewer { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; }
        .avatar-candidate { background: linear-gradient(135deg, #0ea5e9, #6366f1); color: white; }
        .bubble {
          max-width: 70%;
          padding: 14px 18px;
          border-radius: 18px;
          line-height: 1.6;
          font-size: 15px;
          box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }
        .bubble-interviewer {
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          color: #e2e8f0;
          border-bottom-left-radius: 4px;
        }
        .bubble-candidate {
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: white;
          border-bottom-right-radius: 4px;
        }
        .bubble-system {
          background: rgba(234,179,8,0.1);
          border: 1px solid rgba(234,179,8,0.3);
          color: #fde68a;
          font-size: 13px;
          border-radius: 8px;
          max-width: 90%;
        }
        .bubble-anchor-tag {
          font-size: 11px; font-weight: 600;
          color: #818cf8; text-transform: uppercase;
          margin-bottom: 8px;
        }
        .bubble-text { white-space: pre-wrap; }
        .input-area {
          padding: 16px 0 24px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          border-top: 1px solid rgba(255,255,255,0.08);
          flex-shrink: 0;
        }
        .text-input-form {
          display: flex;
          gap: 10px;
          align-items: flex-end;
        }
        .answer-textarea {
          flex: 1;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.12);
          border-radius: 14px;
          padding: 14px 18px;
          color: #f1f5f9;
          font-size: 15px;
          font-family: inherit;
          resize: none;
          outline: none;
          line-height: 1.5;
          transition: border-color 0.2s;
        }
        .answer-textarea:focus { border-color: rgba(99,102,241,0.6); }
        .complete-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 20px;
          background: rgba(34,197,94,0.1);
          border: 1px solid rgba(34,197,94,0.3);
          border-radius: 12px;
          margin-bottom: 8px;
          font-size: 14px;
          color: #86efac;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}
