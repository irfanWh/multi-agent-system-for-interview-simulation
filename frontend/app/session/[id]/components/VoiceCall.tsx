"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Button } from "@/components/ui/Button";

type CallState =
  | "idle"
  | "listening"
  | "user_speaking"
  | "processing"
  | "agent_thinking"
  | "agent_speaking"
  | "session_complete";

interface VoiceCallProps {
  sessionId: string;
  wsUrl: string;
  accessCode?: string;
  onComplete: () => void;
}

export function VoiceCall({ sessionId, wsUrl, accessCode, onComplete }: VoiceCallProps) {
  const [callState, setCallState] = useState<CallState>("idle");
  const [transcript, setTranscript] = useState("");
  const [currentAnchor, setCurrentAnchor] = useState("");
  const [energy, setEnergy] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);       // 16kHz for mic capture
  const playCtxRef = useRef<AudioContext | null>(null);      // 48kHz for TTS playback
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const callStateRef = useRef<CallState>("idle");            // mirror for closures

  // TTS Playback state
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const isPlayingRef = useRef<boolean>(false);
  const ttsBufferRef = useRef<Uint8Array[]>([]);

  // Keep ref in sync with state
  const updateCallState = useCallback((newState: CallState) => {
    callStateRef.current = newState;
    setCallState(newState);
  }, []);

  const unmuteMic = useCallback(() => {
    if (workletNodeRef.current) {
      workletNodeRef.current.port.postMessage({ type: 'unmute' });
    }
  }, []);

  const muteMic = useCallback(() => {
    if (workletNodeRef.current) {
      workletNodeRef.current.port.postMessage({ type: 'mute' });
    }
  }, []);

  const initVoiceCall = async () => {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;

      // Separate contexts: mic at 16kHz (Whisper), playback at default (48kHz)
      const micCtx = new AudioContextClass({ sampleRate: 16000 });
      micCtxRef.current = micCtx;

      const playCtx = new AudioContextClass(); // browser default 48kHz
      playCtxRef.current = playCtx;

      await micCtx.audioWorklet.addModule('/vad-processor.js');

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
      });
      mediaStreamRef.current = stream;

      const source = micCtx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      const workletNode = new AudioWorkletNode(micCtx, 'vad-processor');
      workletNodeRef.current = workletNode;
      source.connect(workletNode);

      const wsAccess = accessCode ? `?access_code=${encodeURIComponent(accessCode)}` : "";
      const ws = new WebSocket(`${wsUrl}/session/${sessionId}${wsAccess}`);
      wsRef.current = ws;
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: "session_start", session_id: sessionId, mode: "voice" }));
        updateCallState("listening");
      };

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          const view = new Uint8Array(event.data);
          if (view[0] === 0x01) {
            ttsBufferRef.current.push(new Uint8Array(event.data.slice(1)));
          }
          return;
        }

        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "transcript":
            setTranscript(msg.text);
            break;
          case "interviewer_thinking":
            updateCallState("agent_thinking");
            break;
          case "tts_start":
            updateCallState("agent_speaking");
            ttsBufferRef.current = [];
            muteMic();
            break;
          case "tts_end":
            // Assemble all accumulated chunks into one WAV and play
            if (ttsBufferRef.current.length > 0) {
              const totalLength = ttsBufferRef.current.reduce((acc, val) => acc + val.length, 0);
              const combined = new Uint8Array(totalLength);
              let offset = 0;
              for (const chunk of ttsBufferRef.current) {
                combined.set(chunk, offset);
                offset += chunk.length;
              }
              ttsBufferRef.current = [];
              enqueueChunk(combined.buffer);
            } else {
              // No audio chunks received — transition immediately
              finishAgentSpeaking();
            }
            break;
          case "tts_error":
            // Backend couldn't generate TTS — unmute and go back to listening
            finishAgentSpeaking();
            break;
          case "anchor_change":
            if (msg.anchor_title) setCurrentAnchor(msg.anchor_title);
            break;
          case "session_complete":
            updateCallState("session_complete");
            break;
        }
      };

      ws.onclose = () => {
        updateCallState("idle");
      };

      // Worklet message handler — uses ref to avoid stale closure
      workletNode.port.onmessage = (e) => {
        if (e.data.type === 'frame') {
          const f32 = new Float32Array(e.data.pcm);
          const i16 = new Int16Array(f32.length);
          for (let i = 0; i < f32.length; i++) {
            const s = Math.max(-1, Math.min(1, f32[i]));
            i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(i16.buffer);
          }

          setEnergy(e.data.energy);

          // Use ref (not state) to avoid stale closure
          const current = callStateRef.current;
          if (e.data.energy > 0.01 && current === "listening") {
            updateCallState("user_speaking");
          } else if (e.data.energy <= 0.01 && current === "user_speaking") {
            updateCallState("listening");
          }
        }
      };

    } catch (err) {
      console.error("Mic error:", err);
      alert("Failed to access microphone or start audio.");
    }
  };

  const finishAgentSpeaking = useCallback(() => {
    unmuteMic();
    updateCallState("listening");
  }, [unmuteMic, updateCallState]);

  const enqueueChunk = (chunk: ArrayBuffer) => {
    audioQueueRef.current.push(chunk);
    if (!isPlayingRef.current) {
      playNext();
    }
  };

  const playNext = async () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      finishAgentSpeaking();
      return;
    }

    isPlayingRef.current = true;
    const chunk = audioQueueRef.current.shift()!;
    const ctx = playCtxRef.current;  // Use playback context, not mic context
    if (!ctx) {
      finishAgentSpeaking();
      return;
    }

    try {
      // decodeAudioData needs a copy because it detaches the buffer
      const copy = chunk.slice(0);
      const buffer = await ctx.decodeAudioData(copy);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.onended = () => {
        playNext();
      };
      source.start();
    } catch (e) {
      console.error("Decode error", e);
      playNext(); // skip bad chunk
    }
  };

  const endCall = () => {
    wsRef.current?.close();
    mediaStreamRef.current?.getTracks().forEach(t => t.stop());
    micCtxRef.current?.close();
    playCtxRef.current?.close();
    onComplete();
  };

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      mediaStreamRef.current?.getTracks().forEach(t => t.stop());
      micCtxRef.current?.close();
      playCtxRef.current?.close();
    };
  }, []);

  if (callState === "idle") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6">
        <div className="text-xl text-slate-300">Ready to start the voice interview?</div>
        <Button onClick={initVoiceCall} className="bg-indigo-600 hover:bg-indigo-500 rounded-full px-8 py-6 text-lg">
          🎙️ Start voice interview
        </Button>
      </div>
    );
  }

  if (callState === "session_complete") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6">
        <div className="text-2xl font-bold text-green-400">✅ Interview complete!</div>
        <Button onClick={endCall} className="px-6 py-3">See Profile & Report</Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-between h-full py-12 px-4 w-full max-w-2xl mx-auto">

      {/* Top section: Topic */}
      <div className="flex flex-col items-center gap-2">
        <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-xl shadow-lg">
          AI
        </div>
        {currentAnchor && (
          <div className="mt-4 px-4 py-1.5 bg-indigo-900/40 border border-indigo-500/30 rounded-full text-indigo-200 text-sm font-medium tracking-wide">
            📌 {currentAnchor}
          </div>
        )}
      </div>

      {/* Center section: State / Animations */}
      <div className="flex flex-col items-center justify-center flex-1 w-full gap-8">

        {callState === "agent_speaking" && (
          <div className="flex flex-col items-center gap-4">
            <div className="flex gap-2 h-16 items-center">
              <div className="w-2 bg-indigo-400 rounded-full animate-[pulse_1s_ease-in-out_infinite]" style={{ height: '40%' }} />
              <div className="w-2 bg-indigo-400 rounded-full animate-[pulse_1.2s_ease-in-out_infinite_0.1s]" style={{ height: '80%' }} />
              <div className="w-2 bg-indigo-400 rounded-full animate-[pulse_0.8s_ease-in-out_infinite_0.2s]" style={{ height: '60%' }} />
              <div className="w-2 bg-indigo-400 rounded-full animate-[pulse_1.5s_ease-in-out_infinite_0.3s]" style={{ height: '100%' }} />
              <div className="w-2 bg-indigo-400 rounded-full animate-[pulse_1.1s_ease-in-out_infinite_0.4s]" style={{ height: '50%' }} />
            </div>
            <div className="text-indigo-300 font-medium tracking-wide">Interviewer is speaking...</div>
            <div className="flex items-center gap-2 mt-4 px-3 py-1.5 bg-red-900/30 rounded-full text-red-400 text-xs">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" clipRule="evenodd" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
              </svg>
              Mic muted
            </div>
          </div>
        )}

        {(callState === "listening" || callState === "user_speaking") && (
          <div className="flex flex-col items-center gap-6">
            <div className="relative flex items-center justify-center w-32 h-32">
              <div className="absolute inset-0 bg-green-500 rounded-full opacity-20 animate-ping" />
              <div className="absolute inset-4 bg-green-500 rounded-full opacity-30 animate-pulse" />
              <div
                className="z-10 bg-green-500 rounded-full transition-all duration-75"
                style={{
                  width: `${60 + Math.min(energy * 300, 40)}px`,
                  height: `${60 + Math.min(energy * 300, 40)}px`
                }}
              />
            </div>
            <div className="text-green-400 font-medium tracking-wide">
              {callState === "user_speaking" ? "Listening to you..." : "Your turn — speak now..."}
            </div>
          </div>
        )}

        {(callState === "processing" || callState === "agent_thinking") && (
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
            <div className="text-indigo-300 font-medium tracking-wide">
              {callState === "processing" ? "Processing..." : "Interviewer is thinking..."}
            </div>
          </div>
        )}

        {transcript && (callState === "processing" || callState === "agent_thinking" || callState === "agent_speaking") && (
          <div className="w-full max-w-lg mt-8 p-4 bg-slate-800/50 rounded-2xl border border-slate-700/50">
            <div className="text-xs text-slate-400 mb-2 uppercase tracking-wider font-semibold">You said:</div>
            <div className="text-slate-200 italic">"{transcript}"</div>
          </div>
        )}
      </div>

      {/* Bottom section: End Call */}
      <div className="mt-auto pt-8">
        <Button onClick={endCall} variant="secondary" className="bg-red-600 hover:bg-red-500 text-white rounded-full px-6">
          End Call
        </Button>
      </div>

    </div>
  );
}
