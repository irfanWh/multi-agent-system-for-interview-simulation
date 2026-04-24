"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";

interface AudioPlayerProps {
  wsRef: React.MutableRefObject<WebSocket | null>;
  isAudioMode: boolean;
  onSpeakingStateChange: (isSpeaking: boolean) => void;
}

export function AudioPlayer({ wsRef, isAudioMode, onSpeakingStateChange }: AudioPlayerProps) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const chunksBufferRef = useRef<Uint8Array[]>([]);
  
  const [isPlaying, setIsPlaying] = useState(false);

  // Initialize AudioContext
  useEffect(() => {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (AudioContextClass) {
      audioContextRef.current = new AudioContextClass();
    }
    return () => {
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close();
      }
    };
  }, []);

  const playNextInQueue = useCallback(async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      setIsPlaying(false);
      onSpeakingStateChange(false);
      return;
    }

    if (!audioContextRef.current) return;

    isPlayingRef.current = true;
    setIsPlaying(true);
    onSpeakingStateChange(true);

    const arrayBuffer = audioQueueRef.current.shift()!;
    
    try {
      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);
      
      source.onended = () => {
        playNextInQueue();
      };
      
      source.start(0);
    } catch (err) {
      console.error("Audio decoding failed:", err);
      // Skip this one and play next
      playNextInQueue();
    }
  }, [onSpeakingStateChange]);

  useEffect(() => {
    if (!wsRef.current) return;

    const handleMessage = (event: MessageEvent) => {
      // Handle binary chunks
      if (event.data instanceof Blob) {
        if (!isAudioMode) return;
        const reader = new FileReader();
        reader.onload = () => {
          if (reader.result) {
            chunksBufferRef.current.push(new Uint8Array(reader.result as ArrayBuffer));
          }
        };
        reader.readAsArrayBuffer(event.data);
        return;
      }

      // Handle JSON control messages
      if (typeof event.data === "string") {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "tts_start") {
            chunksBufferRef.current = [];
          } 
          else if (data.type === "tts_end") {
            // Assemble chunks into one ArrayBuffer
            if (chunksBufferRef.current.length > 0) {
              const totalLength = chunksBufferRef.current.reduce((acc, chunk) => acc + chunk.length, 0);
              const combined = new Uint8Array(totalLength);
              let offset = 0;
              for (const chunk of chunksBufferRef.current) {
                combined.set(chunk, offset);
                offset += chunk.length;
              }
              
              audioQueueRef.current.push(combined.buffer);
              chunksBufferRef.current = [];
              
              if (!isPlayingRef.current) {
                playNextInQueue();
              }
            }
          }
        } catch (err) {
          // not JSON, ignore
        }
      }
    };

    wsRef.current.addEventListener("message", handleMessage);
    
    return () => {
      if (wsRef.current) {
        wsRef.current.removeEventListener("message", handleMessage);
      }
    };
  }, [wsRef, isAudioMode, playNextInQueue]);

  if (!isAudioMode) return null;

  return (
    <div className="flex items-center justify-center p-4">
      {isPlaying ? (
        <div className="flex flex-col items-center gap-2">
          <div className="flex gap-1 h-8 items-center">
            <div className="w-1.5 h-full bg-blue-500 rounded-full animate-[pulse_1s_ease-in-out_infinite]" />
            <div className="w-1.5 h-2/3 bg-blue-500 rounded-full animate-[pulse_1.2s_ease-in-out_infinite_0.1s]" />
            <div className="w-1.5 h-4/5 bg-blue-500 rounded-full animate-[pulse_0.8s_ease-in-out_infinite_0.2s]" />
            <div className="w-1.5 h-1/2 bg-blue-500 rounded-full animate-[pulse_1.5s_ease-in-out_infinite_0.3s]" />
            <div className="w-1.5 h-full bg-blue-500 rounded-full animate-[pulse_1.1s_ease-in-out_infinite_0.4s]" />
          </div>
          <span className="text-xs text-blue-600 font-medium">Interviewer Speaking...</span>
        </div>
      ) : (
        <div className="text-xs text-slate-400">Audio ready</div>
      )}
    </div>
  );
}
