'use client';

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { usePose } from '../context/PoseContext';
import styles from './ChatBot.module.css';
import { ragChat, getRagFeedback } from '../services/api';

const TRAINER_SUGGESTIONS = [
  "How do I perform a front kick correctly?",
  "What should my stance look like for a roundhouse kick?",
  "How can I improve my balance during kicks?",
  "What are common mistakes in a reverse punch?",
  "Can you analyze my current form?"
];

const COACH_SUGGESTIONS = [
  "Analyze this trainee's kick technique",
  "What correction pattern do you see?",
  "Suggest a training plan for hip flexibility",
  "How to fix consistent guard dropping?",
];

export default function ChatBot() {
  const { isCoach } = useAuth();
  const { currentMoveId, currentLandmarks } = usePose();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'bot',
      text: isCoach
        ? "Hello Coach! I'm your AI coaching assistant using real-time RAG intelligence."
        : "Hello! I'm your AI martial arts assistant. Ask me about techniques, corrections, or hit the 'Analyze Form' suggestion to get live feedback on your current pose! 🥋",
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

    try {
      let responseText = "";
      let sources = [];
      
      // Special trigger for live form evaluation
      if (text.toLowerCase().includes("analyze my current form")) {
        if (!currentMoveId || !currentLandmarks || currentLandmarks.length === 0) {
          responseText = "I don't have enough pose data right now. Please stand in front of the camera and attempt a move first!";
        } else {
          const fb = await getRagFeedback(currentMoveId, currentLandmarks);
          responseText = fb.feedback;
          sources = fb.sources;
        }
      } else {
        // Normal chat
        const res = await ragChat(text, currentMoveId);
        responseText = res.response;
        sources = res.sources;
      }
      
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'bot', text: responseText, sources: sources },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: 'bot', text: "Sorry, my AI brain (API) is having trouble connecting correctly right now." },
      ]);
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

      {isOpen && (
        <div className={styles.chatPanel}>
          <div className={styles.chatHeader}>
            <div className={styles.headerInfo}>
              <span className={styles.headerIcon}>{isCoach ? '🏆' : '🥋'}</span>
              <div>
                <div className={styles.headerTitle}>
                  {isCoach ? 'Coach Assistant' : 'Training Assistant'}
                </div>
                <div className={styles.headerStatus}>
                  <span className={styles.statusDot} /> AI Powered (RAG)
                </div>
              </div>
            </div>
          </div>

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
                  {msg.text.split('\\n').map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                  {msg.sources && msg.sources.length > 0 && (
                    <div style={{marginTop: '8px', fontSize: '10px', color: '#999'}}>
                      <hr style={{opacity: 0.2, margin: '4px 0'}}/>
                      <i>Sources: {msg.sources.map(s => s.metadata.topic).join(', ')}</i>
                    </div>
                  )}
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

          <form className={styles.inputArea} onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              type="text"
              className={styles.chatInput}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask me anything or say 'analyze my current form'..."
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
