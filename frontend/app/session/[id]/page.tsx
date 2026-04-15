"use client";

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { WS_URL } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';

interface Message {
  id: string;
  sender: 'server' | 'client' | 'system';
  text: string;
  type?: 'question' | 'follow_up' | 'session_complete' | 'error';
  turn?: number;
  total?: number;
}

export default function InterviewSession() {
  const { id } = useParams();
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
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
    
    // Connect to WebSockets
    const ws = new WebSocket(`${WS_URL}/session/${id}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'system', text: 'Connected to InterviewAI' }]);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const newMsg: Message = {
        id: Date.now().toString() + Math.random(),
        sender: data.type === 'error' ? 'system' : 'server',
        text: data.text || data.message || '',
        type: data.type,
        turn: data.turn,
        total: data.total
      };
      
      setMessages(prev => [...prev, newMsg]);

      if (data.type === 'session_complete') {
        setIsComplete(true);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'system', text: 'Disconnected from server' }]);
    };

    return () => {
      ws.close();
    };
  }, [id]);

  const sendMessage = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputValue.trim() || !wsRef.current || !isConnected) return;

    const payload = { type: 'answer', text: inputValue };
    wsRef.current.send(JSON.stringify(payload));
    
    setMessages(prev => [...prev, { id: Date.now().toString(), sender: 'client', text: inputValue }]);
    setInputValue('');
  };

  return (
    <div className="flex flex-col h-screen max-w-4xl mx-auto p-4 md:p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          Live Interview
        </h1>
        {isComplete && (
          <Button onClick={() => router.push('/profile')}>Return to Dashboard</Button>
        )}
      </div>

      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender === 'client' ? 'justify-end' : 'justify-start'}`}>
              <div 
                className={`max-w-[85%] rounded-2xl p-4 ${
                  msg.sender === 'client' 
                    ? 'bg-blue-600 text-white rounded-tr-sm' 
                    : msg.sender === 'system' 
                      ? 'bg-amber-100 text-amber-800 text-sm mx-auto'
                      : 'bg-white border border-slate-200 text-slate-800 shadow-sm rounded-tl-sm'
                }`}
              >
                {msg.sender === 'server' && msg.type === 'question' && (
                  <div className="text-xs font-semibold text-blue-600 uppercase tracking-wider mb-2">
                    Question {msg.turn} of {msg.total}
                  </div>
                )}
                {msg.sender === 'server' && msg.type === 'follow_up' && (
                  <div className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-2">
                    Follow-up
                  </div>
                )}
                <div className="whitespace-pre-wrap leading-relaxed">{msg.text}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </CardContent>
        
        <div className="p-4 border-t bg-white">
          <form onSubmit={sendMessage} className="flex gap-2">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder={isComplete ? "Interview finished" : "Type your answer... (Press Enter to send)"}
              disabled={!isConnected || isComplete}
              className="flex-1 resize-none rounded-md border border-slate-300 p-3 pr-12 focus:outline-none focus:ring-2 focus:ring-blue-600 min-h-[60px] max-h-[200px]"
              rows={2}
            />
            <Button 
              type="submit" 
              disabled={!isConnected || isComplete || !inputValue.trim()}
              className="px-6"
            >
              Send
            </Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
