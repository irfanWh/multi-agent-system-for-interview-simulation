"use client";

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { WS_URL } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { AudioRecorder } from './components/AudioRecorder';
import { AudioPlayer } from './components/AudioPlayer';

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
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [useAudio, setUseAudio] = useState(false);
  const [currentAnchor, setCurrentAnchor] = useState<string | null>(null);
  const [isInterviewerSpeaking, setIsInterviewerSpeaking] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (!id) return;

    const ws = new WebSocket(`${WS_URL}/session/${id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // Update current anchor topic when server provides it
      if (data.anchor_title) {
        setCurrentAnchor(data.anchor_title);
      }

      if (data.type === 'transcript') {
        setMessages(prev => [...prev, {
          id: Date.now().toString() + Math.random(),
          sender: 'client',
          text: `🎤 ${data.text}`,
          type: 'transcript'
        }]);
        return;
      }

      const text = data.text || data.message || '';
      if (!text) return;

      setMessages(prev => [...prev, {
        id: Date.now().toString() + Math.random(),
        sender: data.type === 'error' ? 'system' : 'server',
        text,
        type: data.type,
        anchor_title: data.anchor_title
      }]);

      if (data.type === 'session_complete') {
        setIsComplete(true);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    return () => { ws.close(); };
  }, [id]);

  const sendMessage = (textOrEvent?: string | React.FormEvent) => {
    let textToSend = inputValue;

    if (textOrEvent && typeof textOrEvent !== 'string' && 'preventDefault' in textOrEvent) {
      textOrEvent.preventDefault();
    } else if (typeof textOrEvent === 'string') {
      textToSend = textOrEvent;
    }

    if (!textToSend.trim() || !wsRef.current || !isConnected) return;

    wsRef.current.send(JSON.stringify({ type: 'answer', text: textToSend }));
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      sender: 'client',
      text: textToSend
    }]);
    setInputValue('');
  };

  const toggleMode = (newState: boolean) => {
    setUseAudio(newState);
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({ type: 'set_mode', mode: newState ? 'audio' : 'text' }));
    }
  };

  return (
    <div className="session-page">
      {/* Header */}
      <div className="session-header">
        <div className="session-header-left">
          <div className={`connection-dot ${isConnected ? 'connected' : 'disconnected'}`} />
          <h1 className="session-title">Live Interview</h1>
          {currentAnchor && !isComplete && (
            <div className="topic-pill">
              <span className="topic-label">Topic</span>
              <span className="topic-name">{currentAnchor}</span>
            </div>
          )}
        </div>
        <div className="session-header-right">
          <label className="mode-toggle">
            <input
              type="checkbox"
              checked={useAudio}
              onChange={(e) => toggleMode(e.target.checked)}
            />
            <span>{useAudio ? '🎙️ Audio' : '⌨️ Text'}</span>
          </label>
          {isComplete && (
            <Button onClick={() => router.push('/profile')}>View Report</Button>
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

        {/* Audio Player (Hidden visually or shows waveform) */}
        <AudioPlayer 
          wsRef={wsRef} 
          isAudioMode={useAudio} 
          onSpeakingStateChange={setIsInterviewerSpeaking} 
        />

        {/* Input */}
        {!isComplete && (
          <div className="input-area">
            <AudioRecorder
              onSendMessage={sendMessage}
              wsRef={wsRef}
              isConnected={isConnected}
              isRecordingMode={useAudio}
              isDisabled={isInterviewerSpeaking}
            />
            {!useAudio && (
              <form
                onSubmit={(e) => { e.preventDefault(); sendMessage(); }}
                className="text-input-form"
              >
                <textarea
                  id="answer-input"
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
                <Button
                  type="submit"
                  id="send-answer-btn"
                  disabled={!isConnected || !inputValue.trim()}
                >
                  Send →
                </Button>
              </form>
            )}
          </div>
        )}

        {isComplete && (
          <div className="complete-banner">
            <span>✅ Interview complete! Your responses have been recorded and are being evaluated.</span>
            <Button onClick={() => router.push('/profile')}>See Profile & Report</Button>
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
        .mode-toggle {
          display: flex; align-items: center; gap: 8px;
          cursor: pointer; font-size: 14px; color: #94a3b8;
        }
        .mode-toggle input { cursor: pointer; }
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
          letter-spacing: 0.06em; margin-bottom: 8px;
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
        .answer-textarea::placeholder { color: #475569; }
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
          gap: 16px;
          flex-shrink: 0;
        }
      `}</style>
    </div>
  );
}
