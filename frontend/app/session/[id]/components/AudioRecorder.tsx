"use client";

import { useState, useRef, useCallback } from 'react';

export function AudioRecorder({
  onSendMessage,
  wsRef,
  isConnected,
  isRecordingMode
}: {
  onSendMessage: (txt: string) => void;
  wsRef: React.MutableRefObject<WebSocket | null>;
  isConnected: boolean;
  isRecordingMode: boolean;
}) {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0 && wsRef.current && isConnected) {
          // Send raw binary to backend over websocket
          wsRef.current.send(event.data);
        }
      };

      // 250ms chunks
      mediaRecorder.start(250);
      setIsRecording(true);
    } catch (err) {
      alert("Microphone permission denied or not available.");
    }
  }, [wsRef, isConnected]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
      setIsRecording(false);
    }
  }, [isRecording]);

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  if (!isRecordingMode) return null;

  return (
    <div className="flex items-center gap-4 border p-3 rounded-md bg-slate-50">
      <div 
        onClick={toggleRecording}
        className={`cursor-pointer flex items-center justify-center p-3 rounded-full transition-colors ${
          isRecording 
            ? "bg-red-100 text-red-600 animate-pulse hover:bg-red-200" 
            : "bg-blue-100 text-blue-600 hover:bg-blue-200"
        }`}
      >
        {isRecording ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
          </svg>
        )}
      </div>
      <div className="text-sm font-medium text-slate-700">
        {isRecording 
          ? "Ecoute en cours... Parlez (les blancs valident la réponse)." 
          : "Microphone coupé"}
      </div>
    </div>
  );
}
