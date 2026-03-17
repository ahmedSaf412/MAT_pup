'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import styles from './ChatBot.module.css';

const TRAINER_SUGGESTIONS = [
  "How do I perform a front kick correctly?",
  "What should my stance look like for a roundhouse kick?",
  "How can I improve my balance during kicks?",
  "What are common mistakes in a reverse punch?",
];

const COACH_SUGGESTIONS = [
  "Analyze this trainee's kick technique",
  "What correction pattern do you see?",
  "Suggest a training plan for hip flexibility",
  "How to fix consistent guard dropping?",
];

// Mock response generator
function generateBotResponse(message, isCoach) {
  const lower = message.toLowerCase();

  if (isCoach) {
    if (lower.includes('analyze') || lower.includes('technique')) {
      return "Based on the pose data, the trainee shows consistent hip rotation deficit of ~15°. Recommend focusing on hip flexibility drills and slow-motion practice of the full rotation arc. The guard hand position has improved by 23% since last session.";
    }
    if (lower.includes('correction') || lower.includes('pattern')) {
      return "Common correction patterns for this trainee:\n\n🔴 Guard dropping during kicks (78% of sessions)\n🟡 Incomplete hip rotation (65%)\n🟢 Stance width improving (was 45%, now 82% correct)\n\nRecommend: 3 sets of guard awareness drills before each session.";
    }
    if (lower.includes('plan') || lower.includes('flexibility')) {
      return "Suggested Training Plan:\n\n📋 Week 1-2: Dynamic stretching focus\n📋 Week 3-4: Slow technique drills with pause at full extension\n📋 Week 5-6: Speed building with correct form\n\nInclude hip circles and leg swings as warm-up every session.";
    }
    return "As a coaching assistant, I can help you analyze trainee performance, identify correction patterns, and suggest training plans. What would you like to focus on?";
  }

  // Trainer responses
  if (lower.includes('front kick') || lower.includes('kick')) {
    return "**Front Kick (Mae Geri) Tips:**\n\n1️⃣ Start in fighting stance, weight slightly back\n2️⃣ Lift your knee to waist height first\n3️⃣ Snap your foot forward, striking with the ball of the foot\n4️⃣ Retract quickly to knee-up position\n5️⃣ Return to stance\n\n💡 Key: Chamber the knee HIGH before extending!";
  }
  if (lower.includes('stance') || lower.includes('roundhouse')) {
    return "**Roundhouse Kick Stance:**\n\n🦶 Feet shoulder-width apart\n🔄 Pivot on the supporting foot (heel turns toward target)\n📐 Hips rotate fully through the kick\n🤜 Keep guard hands up near chin\n\n⚠️ Most common error: Not pivoting the support foot enough!";
  }
  if (lower.includes('balance')) {
    return "**Balance Improvement Drills:**\n\n1. Single-leg stance holds (30 sec each side)\n2. Slow-motion front kicks with 3-second pause at extension\n3. Walking stance transitions\n4. Eyes-closed balance practice\n\n🎯 Practice 5 minutes daily for noticeable improvement in 2 weeks!";
  }
  return "I'm your AI training assistant! I can help with:\n\n🥋 Technique explanations and tips\n📐 Form and stance guidance\n🏋️ Training recommendations\n🔧 Correction explanations\n\nAsk me anything about martial arts techniques!";
}

export default function ChatBot() {
  const { isCoach } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'bot',
      text: isCoach
        ? "Hello Coach! I'm your AI coaching assistant. I can help analyze trainee performance, suggest corrections, and create training plans."
        : "Hello! I'm your AI martial arts assistant. Ask me about techniques, corrections, or training tips! 🥋",
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const suggestions = isCoach ? COACH_SUGGESTIONS : TRAINER_SUGGESTIONS;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim()) return;

    const userMsg = { id: Date.now(), role: 'user', text: text.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    // Simulate AI response time
    setTimeout(() => {
      const response = generateBotResponse(text, isCoach);
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'bot', text: response },
      ]);
      setIsTyping(false);
    }, 800 + Math.random() * 1200);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <>
      {/* Floating Toggle Button */}
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

      {/* Chat Panel */}
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
                  <span className={styles.statusDot} /> AI Powered
                </div>
              </div>
            </div>
          </div>

          {/* Messages */}
          <div className={styles.messages}>
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`${styles.message} ${
                  msg.role === 'user' ? styles.userMsg : styles.botMsg
                }`}
              >
                {msg.role === 'bot' && (
                  <div className={styles.botAvatar}>🤖</div>
                )}
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
              placeholder={isCoach ? "Ask about trainee analysis..." : "Ask about techniques..."}
              id="chatbot-input"
            />
            <button
              type="submit"
              className={styles.sendBtn}
              disabled={!input.trim()}
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
