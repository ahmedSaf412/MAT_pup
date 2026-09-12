'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { usePose } from '../context/PoseContext';
import api from '../services/api';
import styles from './ChatBot.module.css';

// ── Phrases that trigger live form analysis (DTW feedback) ─────────────────
const FORM_ANALYSIS_TRIGGERS = [
  'analyze my form',
  'analyze my current form',
  'check my form',
  'review my form',
  'how is my form',
  'what am i doing wrong',
  'correct my form',
  'give me feedback',
  'rate my form',
];

const TRAINEE_SUGGESTIONS = [
  "Analyze my form",
  "How do I perform a front kick correctly?",
  "What are common mistakes in a reverse punch?",
  "What should my stance look like for Gedan Barai?",
];

const COACH_SUGGESTIONS = [
  "Analyze common errors for the front kick",
  "What correction pattern do you see for gyaku zuki?",
  "How to fix consistent guard dropping?",
  "Tips for improving hip rotation in mae geri?",
];

export default function ChatBot() {
  const { isCoach } = useAuth();
  const { currentMoveId, currentLandmarkFrames } = usePose();
  const [isOpen,    setIsOpen]    = useState(false);
  const [messages,  setMessages]  = useState([
    {
      id: 'welcome',
      role: 'bot',
      text: isCoach
        ? "Hello Coach! I'm your AI coaching assistant powered by Groq LLaMA-3. Ask me about trainee technique, corrections, or training plans. 🏆"
        : "Hello! I'm your AI Karate Sensei powered by Groq LLaMA-3. Ask me anything about technique, form, or say \"Analyze my form\" after training for live feedback! 🥋",
    },
  ]);
  const [input,    setInput]    = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  const suggestions = isCoach ? COACH_SUGGESTIONS : TRAINEE_SUGGESTIONS;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    const userMsg = { id: Date.now(), role: 'user', text: text.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const lower = text.toLowerCase();
      const isFormRequest = FORM_ANALYSIS_TRIGGERS.some(t => lower.includes(t));

      if (isFormRequest) {
        // ── Live DTW form analysis ─────────────────────────────────────────
        if (!currentMoveId || !currentLandmarkFrames || currentLandmarkFrames.length < 5) {
          setMessages(prev => [...prev, {
            id: Date.now() + 1, role: 'bot',
            text: "I don't have your pose data yet! Please start training, perform a move, and then ask me to analyze your form. 🥋",
          }]);
          return;
        }

        setMessages(prev => [...prev, {
          id: Date.now() + 1, role: 'bot',
          text: `🔍 Analyzing your ${currentMoveId.replace('_', ' ')} using DTW comparison…`,
        }]);

        const res = await api.post('/api/rag/feedback', {
          move_id: currentMoveId,
          frames:  currentLandmarkFrames,   // all 30 landmark frames
        });

        const feedback = res.data?.feedback || "I couldn't generate feedback. Please try again.";
        setMessages(prev => [
          ...prev.slice(0, -1),            // remove the "analyzing…" message
          { id: Date.now() + 2, role: 'bot', text: feedback },
        ]);
      } else {
        // ── General RAG chat ───────────────────────────────────────────────
        const res = await api.post('/api/rag/chat', {
          message: text.trim(),
          move_id: currentMoveId || null,
        });

        const botText = res.data?.response || "I couldn't generate a response. Please try again.";
        setMessages(prev => [...prev, { id: Date.now() + 1, role: 'bot', text: botText }]);
      }
    } catch (err) {
      const errMsg = err.response?.status === 500
        ? "The AI coach encountered an error. Check that the backend is running."
        : "Network error — check that the backend server is running.";
      setMessages(prev => [...prev, { id: Date.now() + 1, role: 'bot', text: errMsg }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <>
      {/* Floating toggle button */}
      <button
        className={`${styles.toggleBtn} ${isOpen ? styles.open : ''}`}
        onClick={() => {
          setIsOpen(!isOpen);
          if (!isOpen) setTimeout(() => inputRef.current?.focus(), 100);
        }}
        id="chatbot-toggle"
        aria-label="Toggle AI Assistant"
      >
        {isOpen ? '✕' : '🤖'}
      </button>

      {/* Chat panel */}
      {isOpen && (
        <div className={styles.chatPanel}>
          {/* Header */}
          <div className={styles.chatHeader}>
            <div className={styles.headerInfo}>
              <span className={styles.headerIcon}>{isCoach ? '🏆' : '🥋'}</span>
              <div>
                <div className={styles.headerTitle}>
                  {isCoach ? 'Coach Assistant' : 'Training Assistant'}
                </div>
                <div className={styles.headerStatus}>
                  <span className={styles.statusDot} /> Groq LLaMA-3
                  {currentMoveId && (
                    <span style={{ marginLeft: 6, opacity: 0.6, fontSize: '0.7rem' }}>
                      · {currentMoveId.replace('_', ' ')}
                    </span>
                  )}
                  {currentLandmarkFrames && (
                    <span style={{ marginLeft: 4, color: '#4ade80', fontSize: '0.7rem' }}>
                      ● ready
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className={styles.messages}>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`${styles.message} ${msg.role === 'user' ? styles.userMsg : styles.botMsg}`}
              >
                {msg.role === 'bot' && <div className={styles.botAvatar}>🤖</div>}
                <div className={styles.msgBubble}>
                  {msg.text.split('\n').map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className={`${styles.message} ${styles.botMsg}`}>
                <div className={styles.botAvatar}>🤖</div>
                <div className={styles.typingIndicator}>
                  <span /><span /><span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions */}
          {messages.length <= 2 && (
            <div className={styles.suggestions}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  className={styles.suggestionChip}
                  onClick={() => sendMessage(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <form className={styles.inputArea} onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className={styles.chatInput}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                currentLandmarkFrames
                  ? "Ask anything or say 'Analyze my form'…"
                  : isCoach ? "Ask about trainee analysis…" : "Ask about techniques…"
              }
              id="chatbot-input"
              disabled={isTyping}
            />
            <button
              type="submit"
              className={styles.sendBtn}
              disabled={!input.trim() || isTyping}
              id="chatbot-send"
            >
              ➤
            </button>
          </form>
        </div>
      )}
    </>
  );
}
