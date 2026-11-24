'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Barlow, Instrument_Serif } from 'next/font/google';
import {
  Sparkles, Twitter, Linkedin, FileText, Video,
  Loader2, CheckCircle2, Zap, Play, Brain,
  Rocket, Eye, Clapperboard, ArrowRight, Copy, Check,
  Download, X, AlertCircle, Instagram, Cpu, Wand2, History
} from 'lucide-react';

const barlow = Barlow({ subsets: ['latin'], weight: ['400', '500', '700'] });
const instrument = Instrument_Serif({ subsets: ['latin'], weight: '400', style: 'italic' });

// ── Toast notification system ──
function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error' | 'info'; onClose: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 4000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const colors = {
    success: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-300',
    error: 'from-red-500/20 to-red-600/10 border-red-500/30 text-red-300',
    info: 'from-indigo-500/20 to-indigo-600/10 border-indigo-500/30 text-indigo-300',
  };

  const icons = {
    success: <CheckCircle2 className="w-4 h-4" />,
    error: <AlertCircle className="w-4 h-4" />,
    info: <Sparkles className="w-4 h-4" />,
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 50, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.9 }}
      className={`fixed bottom-6 right-6 z-50 bg-gradient-to-r ${colors[type]} border backdrop-blur-xl rounded-2xl px-5 py-3.5 flex items-center gap-3 shadow-2xl max-w-sm`}
    >
      {icons[type]}
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100 transition-opacity">
        <X className="w-3.5 h-3.5" />
      </button>
    </motion.div>
  );
}

// ── Floating particle background ──
function Particles() {
  const [particles] = useState(() =>
    Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      delay: Math.random() * 15,
      duration: 10 + Math.random() * 20,
      size: 2 + Math.random() * 3,
      opacity: 0.1 + Math.random() * 0.3,
      r: 130 + Math.random() * 50,
      g: 100 + Math.random() * 50,
    }))
  );

  return (
    <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full"
          style={{
            left: `${p.x}%`,
            width: p.size,
            height: p.size,
            background: `rgba(${p.r}, ${p.g}, 241, ${p.opacity})`,
          }}
          animate={{
            y: ['100vh', '-10vh'],
            opacity: [0, p.opacity, p.opacity, 0],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: 'linear',
          }}
        />
      ))}
    </div>
  );
}

const EXAMPLE_TOPICS = [
  "The impact of AI on creative industries",
  "How remote work is reshaping global cities",
  "The psychology behind viral social media trends",
];

const STAGES = [
  { title: "Analyzing Intent", desc: "Building narrative arc", icon: <Brain className="w-4 h-4" /> },
  { title: "Generating Content", desc: "Twitter, LinkedIn, Blog, Instagram", icon: <Sparkles className="w-4 h-4" /> },
  { title: "Scripting Video", desc: "Scene narration + image prompts", icon: <Clapperboard className="w-4 h-4" /> },
  { title: "Generating Media", desc: "TTS voiceover + AI images", icon: <Eye className="w-4 h-4" /> },
  { title: "Rendering Video", desc: "FFmpeg cinematic engine", icon: <Rocket className="w-4 h-4" /> }
];

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, '') || 'http://localhost:8000';

type StageStatus = 'pending' | 'active' | 'done';


function GeneratorDashboard() {
  const [topic, setTopic] = useState('');
  const [bgmStyle, setBgmStyle] = useState('suspense');
  const [targetPlatform, setTargetPlatform] = useState('all');
  const [runId, setRunId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isReviewing, setIsReviewing] = useState(false);
  const [isRenderingFinal, setIsRenderingFinal] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [historyItems, setHistoryItems] = useState<any[]>([]);
  const [editedScript, setEditedScript] = useState<string[]>([]);
  const [stageStatuses, setStageStatuses] = useState<StageStatus[]>(Array(5).fill('pending'));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [results, setResults] = useState<Record<string, any>>({});
  const [hasResults, setHasResults] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [progressMessage, setProgressMessage] = useState('');
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (mounted) {
      try { setHistoryItems(JSON.parse(localStorage.getItem('cc_history') || '[]')); } catch { }
    }
  }, [mounted, isHistoryOpen]);

  useEffect(() => {
    if (results.review_data && editedScript.length === 0) {
      setEditedScript(results.review_data.script || []);
    }
  }, [results.review_data, editedScript.length]);

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const saveToHistory = useCallback((res: any, t: string) => {
    try {
      const history = JSON.parse(localStorage.getItem('cc_history') || '[]');
      history.unshift({
        id: res.review_data?.run_id || Date.now().toString(),
        topic: t,
        date: new Date().toISOString(),
        results: res
      });
      localStorage.setItem('cc_history', JSON.stringify(history.slice(0, 20)));
    } catch (e) { console.error('History save error', e); }
  }, []);

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast(`${label} copied to clipboard!`, 'success');
    } catch {
      showToast('Failed to copy', 'error');
    }
  };

  const handleGenerate = async () => {
    if (!topic) return;
    setIsGenerating(true);
    setResults({});
    setRunId(null);
    setHasResults(false);
    setIsReviewing(false);
    setIsRenderingFinal(false);
    setEditedScript([]);
    setStageStatuses(Array(5).fill('pending'));
    setProgressMessage('Initializing pipeline...');
    setElapsedTime(0);
    showToast('Pipeline launched! Streaming results...', 'info');

    // Start timer
    const startTime = Date.now();
    timerRef.current = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          include_video: true,
          bgm_style: bgmStyle,
          platforms: targetPlatform === 'all' ? ['twitter', 'linkedin', 'blog', 'instagram'] : [targetPlatform]
        })
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (!reader) throw new Error('No response body');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        let currentEvent = '';
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ') && currentEvent) {
            try {
              const data = JSON.parse(line.slice(6));

              if (currentEvent === 'stage') {
                setStageStatuses(prev => {
                  const next = [...prev];
                  next[data.id] = data.status as StageStatus;
                  return next;
                });
                if (data.status === 'active') {
                  setProgressMessage(data.name + '...');
                }
              } else if (currentEvent === 'data') {
                setResults(prev => ({ ...prev, [data.key]: data.content }));
                setHasResults(true);
              } else if (currentEvent === 'progress') {
                setProgressMessage(data.message);
              } else if (currentEvent === 'done') {
                if (data.requires_review) {
                  showToast('Pipeline paused for human review.', 'info');
                  setIsReviewing(true);
                } else {
                  showToast('Pipeline complete! All content generated.', 'success');
                  saveToHistory(results, topic);
                }
                if (data.run_id) setRunId(data.run_id);
              }
            } catch (parseErr) {
              console.warn('SSE parse error:', parseErr);
            }
            currentEvent = '';
          }
        }
      }
    } catch (e) {
      console.error(e);
      showToast('Pipeline connection failed. Check if Python server is running.', 'error');
    } finally {
      setIsGenerating(false);
      setProgressMessage('');
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const handleApproveAndRender = async () => {
    setIsReviewing(false);
    setIsRenderingFinal(true);
    setStageStatuses(prev => {
      const next = [...prev];
      next[4] = 'active'; // Rendering stage
      return next;
    });
    setProgressMessage("Starting final render (May take 1-2 minutes)...");

    try {
      showToast('Compiling director cut video...', 'info');
      const response = await fetch(`${API_BASE_URL}/api/render-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: results.review_data.run_id,
          script: editedScript,
          bgm_path: results.review_data.bgm_path
        })
      });
      const data = await response.json();
      if (!response.ok || data.status === 'error') {
        throw new Error(data.message || 'Render failed');
      }

      const newResults = {
        ...results,
        video_url: data.video_url,
        video_script: editedScript.join('\n'),
        video_status: 'Video generated successfully!'
      };

      setResults(newResults);
      setStageStatuses(prev => {
        const next = [...prev];
        next[4] = 'done';
        return next;
      });
      showToast('Video is ready!', 'success');
      saveToHistory(newResults, topic);

    } catch (err) {
      console.error(err);
      showToast('Failed to render video', 'error');
      setStageStatuses(prev => {
        const next = [...prev];
        next[4] = 'pending';
        return next;
      });
      setIsReviewing(true); // Let them try again
    } finally {
      setIsRenderingFinal(false);
      setProgressMessage('');
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  if (!mounted) return null;

  const completedCount = stageStatuses.filter(s => s === 'done').length;
  const isPipelineActive = isGenerating || isReviewing || isRenderingFinal;

  return (
    <div className="min-h-screen aurora-bg noise-overlay text-slate-200 font-sans selection:bg-indigo-500/30 relative">
      <Particles />

      <AnimatePresence>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      </AnimatePresence>

      <AnimatePresence>
        {isHistoryOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsHistoryOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="bg-slate-900 border border-slate-700/50 p-6 rounded-3xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-y-auto custom-scrollbar"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-indigo-500/20 rounded-xl">
                    <History className="w-5 h-5 text-indigo-400" />
                  </div>
                  <h2 className="text-xl font-bold text-white tracking-tight">Campaign History</h2>
                </div>
                <button onClick={() => setIsHistoryOpen(false)} className="text-slate-400 hover:text-white transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {historyItems.length === 0 ? (
                <div className="text-center py-12 text-slate-500">
                  <p>No past campaigns found.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {historyItems.map((item, i) => (
                    <div key={i} className="bg-slate-800/50 border border-slate-700/50 rounded-2xl p-4 flex flex-col sm:flex-row gap-4 items-start sm:items-center hover:bg-slate-800 transition-colors">
                      {item.results.video_url ? (
                        <div className="w-16 h-28 bg-black rounded-lg overflow-hidden flex-shrink-0 border border-slate-700">
                          <video src={item.results.video_url} className="w-full h-full object-cover" muted playsInline />
                        </div>
                      ) : (
                        <div className="w-16 h-28 bg-slate-900 rounded-lg flex-shrink-0 border border-slate-700 flex items-center justify-center">
                          <Clapperboard className="w-6 h-6 text-slate-600" />
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{new Date(item.date).toLocaleDateString()}</span>
                        </div>
                        <h3 className="text-sm font-bold text-slate-200 line-clamp-2 leading-snug">{item.topic.length > 80 ? item.topic.substring(0, 80) + '...' : item.topic}</h3>
                        <p className="text-xs text-slate-500 mt-2 line-clamp-1">{item.results.narrative || "No script details"}</p>
                      </div>

                      <button
                        onClick={() => {
                          setTopic(item.topic);
                          setResults(item.results);
                          setHasResults(true);
                          setStageStatuses(Array(5).fill('done'));
                          setRunId(item.results.review_data?.run_id || null);
                          setIsGenerating(false);
                          setIsReviewing(false);
                          setIsRenderingFinal(false);
                          setIsHistoryOpen(false);
                        }}
                        className="w-full sm:w-auto px-4 py-2 bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 text-xs font-bold rounded-xl transition-colors shrink-0"
                      >
                        Restore
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Header ── */}
      <header className="relative z-10 max-w-7xl mx-auto px-6 pt-10 pb-6">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 bg-indigo-500/30 rounded-2xl blur-xl pulse-ring" />
              <div className="relative p-3.5 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-2xl border border-indigo-500/30 glow-indigo">
                <Sparkles className="w-7 h-7 text-indigo-400" />
              </div>
            </div>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-gradient-animated">
                ContentCascade.ai
              </h1>
              <p className="text-slate-500 text-sm mt-0.5 font-medium tracking-wide">
                AI-Powered Omnichannel Production Engine
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-3">
            <button
              onClick={() => setIsHistoryOpen(true)}
              className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 hover:bg-slate-800 transition-colors rounded-full text-xs font-mono text-slate-300 border border-slate-700/50 cursor-pointer"
            >
              <History className="w-3.5 h-3.5" />
              History
            </button>
            {isPipelineActive ? (
              <div className="flex items-center gap-2 px-4 py-2 glass rounded-full text-xs font-mono">
                {isReviewing ? (
                  <Eye className="w-3 h-3 text-emerald-400" />
                ) : (
                  <Loader2 className="w-3 h-3 animate-spin text-indigo-400" />
                )}
                <span className={isReviewing ? "text-emerald-300" : "text-indigo-300"}>{formatTime(elapsedTime)}</span>
                <span className="text-slate-500">elapsed</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-4 py-2 glass rounded-full text-xs font-mono text-slate-400">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Pipeline Ready
              </div>
            )}
          </div>
        </motion.div>
      </header>

      {/* ── Main Content ── */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pb-16 grid grid-cols-1 lg:grid-cols-12 gap-8">

        {/* ── Left Column ── */}
        <div className="lg:col-span-5 space-y-6">

          {/* Input Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="glass-strong rounded-3xl p-7 glow-indigo"
          >
            <div className="flex items-center gap-2 mb-5">
              <Zap className="w-5 h-5 text-amber-400" />
              <h2 className="text-lg font-bold text-white tracking-tight">New Campaign</h2>
            </div>

            <div className="space-y-5">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Topic or Paste an Article URL</label>
                <textarea
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="e.g. The impact of AI on creative industries... OR https://techcrunch.com/article"
                  className="w-full h-28 bg-slate-950/60 border border-slate-700/50 rounded-2xl p-4 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 transition-all resize-none text-sm"
                />
                <div className="flex flex-wrap gap-2 mt-3">
                  {EXAMPLE_TOPICS.map((ex, i) => (
                    <motion.button
                      key={i}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={() => setTopic(ex)}
                      className="text-[11px] px-3 py-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 rounded-full border border-indigo-500/20 hover:border-indigo-500/40 transition-all font-medium"
                    >
                      {ex.length > 30 ? ex.slice(0, 30) + '...' : ex}
                    </motion.button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Background Music Style</label>
                <div className="relative">
                  <select
                    value={bgmStyle}
                    onChange={(e) => setBgmStyle(e.target.value)}
                    className="w-full appearance-none bg-slate-950/60 border border-slate-700/50 rounded-2xl px-4 py-3.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 transition-all text-sm cursor-pointer"
                  >
                    <option value="suspense">🎵 Suspense Drone (Deep & cinematic)</option>
                    <option value="heartbeat">🫀 Eerie Heartbeat (Fast & pulsing)</option>
                    <option value="tension">🔔 High-Pitched Tension (Shrill & anxious)</option>
                    <option value="none">🔇 No Music (Voiceover only)</option>
                  </select>
                  <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">Target Platform</label>
                <div className="relative">
                  <select
                    value={targetPlatform}
                    onChange={(e) => setTargetPlatform(e.target.value)}
                    className="w-full appearance-none bg-slate-950/60 border border-slate-700/50 rounded-2xl px-4 py-3.5 text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 focus:border-indigo-500/40 transition-all text-sm cursor-pointer"
                  >
                    <option value="all">🌍 All Platforms (Omnichannel)</option>
                    <option value="twitter">🐦 Twitter Thread Only</option>
                    <option value="linkedin">💼 LinkedIn Post Only</option>
                    <option value="instagram">📸 Instagram Caption Only</option>
                    <option value="blog">✍️ SEO Blog Post Only</option>
                  </select>
                  <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none">
                    <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                  </div>
                </div>
              </div>

              <motion.button
                onClick={handleGenerate}
                disabled={isPipelineActive || !topic}
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                className="w-full py-4 btn-shimmer text-white font-bold rounded-2xl transition-all shadow-lg shadow-indigo-500/30 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-3 relative overflow-hidden text-sm tracking-wide"
              >
                {isGenerating || isRenderingFinal ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Pipeline Active...
                  </>
                ) : isReviewing ? (
                  <>
                    <Eye className="w-5 h-5 text-emerald-300" />
                    Awaiting Approval
                  </>
                ) : (
                  <>
                    <Rocket className="w-5 h-5" />
                    Launch Pipeline
                    <ArrowRight className="w-4 h-4 ml-1" />
                  </>
                )}
              </motion.button>

              <AnimatePresence>
                {runId && !isGenerating && (
                  <motion.a
                    initial={{ opacity: 0, y: -10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -10, scale: 0.95 }}
                    href={`${API_BASE_URL}/api/download/${runId}`}
                    download
                    whileHover={{ scale: 1.01 }}
                    whileTap={{ scale: 0.98 }}
                    className="w-full py-4 mt-1 border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 font-bold rounded-2xl transition-all glow-emerald flex items-center justify-center gap-3 relative overflow-hidden text-sm tracking-wide"
                  >
                    <Download className="w-5 h-5" />
                    Export Campaign as .ZIP
                  </motion.a>
                )}
              </AnimatePresence>
            </div>
          </motion.div>

          {/* Pipeline Tracker — Now powered by real SSE events! */}
          <AnimatePresence>
            {isPipelineActive && (
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9, y: -10 }}
                transition={{ type: 'spring', damping: 20 }}
                className="glass-strong rounded-3xl p-7 relative overflow-hidden glow-purple"
              >
                <div className="absolute top-0 left-0 w-full h-1 bg-slate-800/50">
                  <motion.div
                    className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"
                    animate={{ width: `${(completedCount / STAGES.length) * 100}%` }}
                    transition={{ duration: 0.8, ease: 'easeInOut' }}
                  />
                </div>

                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em]">Live Pipeline</h3>
                  </div>
                  {progressMessage && (
                    <span className="text-[10px] text-indigo-300 font-mono bg-indigo-500/10 px-2.5 py-1 rounded-full">
                      {progressMessage}
                    </span>
                  )}
                </div>

                <div className="space-y-4">
                  {STAGES.map((s, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: stageStatuses[idx] === 'pending' ? 0.3 : 1, x: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className="flex items-center gap-4"
                    >
                      <div className={`flex items-center justify-center w-8 h-8 rounded-xl transition-all duration-500 ${stageStatuses[idx] === 'done'
                        ? 'bg-emerald-500/20 border border-emerald-500/40 glow-emerald'
                        : stageStatuses[idx] === 'active'
                          ? 'bg-indigo-500/20 border border-indigo-500/50 glow-indigo'
                          : 'bg-slate-800/30 border border-slate-700/30'
                        }`}>
                        {stageStatuses[idx] === 'done' ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        ) : stageStatuses[idx] === 'active' ? (
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                          >
                            {s.icon}
                          </motion.div>
                        ) : (
                          <span className="text-slate-600">{s.icon}</span>
                        )}
                      </div>

                      <div className="flex-1">
                        <div className={`font-semibold text-sm transition-colors ${stageStatuses[idx] !== 'pending' ? 'text-white' : 'text-slate-600'
                          }`}>{s.title}</div>
                        <div className="text-slate-500 text-xs mt-0.5">{s.desc}</div>
                      </div>

                      {stageStatuses[idx] === 'done' && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full"
                        >
                          DONE
                        </motion.span>
                      )}
                      {stageStatuses[idx] === 'active' && (
                        <span className="text-[10px] font-bold text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded-full animate-pulse">
                          LIVE
                        </span>
                      )}
                    </motion.div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Tech Stack Card — shown when idle */}
          {!isGenerating && !hasResults && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="glass rounded-2xl p-5"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-indigo-500/30 to-purple-500/30 rounded-lg flex items-center justify-center">
                  <Cpu className="w-4 h-4 text-indigo-400" />
                </div>
                <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Multi-Agent Architecture</span>
              </div>
              {/* Mini pipeline flow diagram */}
              <div className="space-y-2">
                {[
                  { label: 'Ideator Agent', sub: 'Groq Llama 3.3 70B', color: 'text-purple-400' },
                  { label: '4× Copywriters', sub: 'Twitter · LinkedIn · Blog · Instagram', color: 'text-indigo-400' },
                  { label: 'Video Producer', sub: 'Script + Imagen 3 Visuals', color: 'text-sky-400' },
                  { label: 'Render Engine', sub: 'FFmpeg · Ken Burns · TTS', color: 'text-emerald-400' },
                ].map((node, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className={`w-1.5 h-1.5 rounded-full ${node.color.replace('text-', 'bg-')}`} />
                    <div>
                      <span className={`text-xs font-semibold ${node.color}`}>{node.label}</span>
                      <span className="text-[10px] text-slate-600 ml-2">{node.sub}</span>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </div>

        {/* ── Right Column: Output Results ── */}
        <div className="lg:col-span-7">
          {hasResults ? (
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.6 }}
              className="space-y-6"
            >

              {/* Director's Cut Review Timeline UI  */}
              {(isReviewing || results.review_data) && !results.video_url && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-strong rounded-3xl overflow-hidden shadow-2xl glow-emerald relative border border-emerald-500/20"
                >
                  <div className="p-4 border-b border-slate-700/30 flex justify-between items-center bg-emerald-500/5">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 bg-gradient-to-br from-emerald-500/30 to-teal-500/30 rounded-lg flex items-center justify-center">
                        <Clapperboard className="w-3.5 h-3.5 text-emerald-400" />
                      </div>
                      <span className="font-bold text-sm text-white">Director&apos;s Cut Timeline</span>
                    </div>
                    {isReviewing && (
                      <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full animate-pulse border border-emerald-500/20">
                        ACTION REQUIRED
                      </span>
                    )}
                  </div>

                  <div className="p-5 space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar bg-black/20">
                    <p className="text-xs text-slate-400 font-medium mb-2">Review and edit the script below. We will use free fallback TTS if you edit.</p>

                    {results.review_data?.images?.map((imgUrl: string, idx: number) => (
                      <div key={idx} className="flex gap-4 p-3 rounded-xl bg-slate-900/50 border border-slate-800 hover:border-slate-700 transition-colors">
                        <div className="relative w-20 h-36 flex-shrink-0 rounded-lg overflow-hidden border border-slate-700/50">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={imgUrl} alt={`Scene ${idx + 1}`} className="w-full h-full object-cover" />
                          <div className="absolute top-1 left-1 bg-black/60 backdrop-blur-sm px-1.5 py-0.5 rounded text-[9px] font-bold text-slate-300">
                            Scene {idx + 1}
                          </div>
                        </div>
                        <div className="flex-1 flex flex-col">
                          <label className="text-[10px] uppercase font-bold text-slate-500 mb-1.5">Narration Text</label>
                          <textarea
                            value={editedScript[idx] || ''}
                            onChange={(e) => {
                              const next = [...editedScript];
                              next[idx] = e.target.value;
                              setEditedScript(next);
                            }}
                            disabled={!isReviewing}
                            className="w-full flex-1 bg-slate-950/50 border border-slate-700/60 rounded-lg p-3 text-slate-300 text-sm placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500/50 resize-none transition-all disabled:opacity-60"
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {isReviewing && (
                    <div className="p-4 border-t border-slate-700/30 bg-slate-900/40">
                      <motion.button
                        onClick={handleApproveAndRender}
                        disabled={isRenderingFinal}
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.98 }}
                        className="w-full py-4 border border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 font-bold rounded-2xl transition-all glow-emerald flex items-center justify-center gap-3 relative overflow-hidden text-sm tracking-wide"
                      >
                        {isRenderingFinal ? (
                          <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Rendering Master...
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="w-5 h-5" />
                            Approve & Render Final Video
                          </>
                        )}
                      </motion.button>
                    </div>
                  )}
                </motion.div>
              )}

              {/* Video Output Card — shows as soon as video data arrives */}
              {results.video_url && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="glass-strong rounded-3xl overflow-hidden shadow-2xl glow-purple"
                >
                  <div className="p-4 border-b border-slate-700/30 flex justify-between items-center">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 bg-gradient-to-br from-indigo-500/30 to-purple-500/30 rounded-lg flex items-center justify-center">
                        <Video className="w-3.5 h-3.5 text-indigo-400" />
                      </div>
                      <span className="font-bold text-sm text-white">Generated Video</span>
                    </div>
                    {results.video_url && (
                      <a
                        href={results.video_url}
                        download
                        className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 px-3 py-1.5 rounded-full border border-emerald-500/20 transition-all"
                      >
                        <Download className="w-3 h-3" />
                        Download
                      </a>
                    )}
                  </div>

                  <div className="aspect-[9/16] max-h-[520px] w-full bg-black/80 flex flex-col items-center justify-center relative overflow-hidden mx-auto">
                    {results.video_url ? (
                      <video
                        key={results.video_url}
                        src={results.video_url}
                        controls
                        autoPlay
                        playsInline
                        className="w-full h-full object-contain"
                      />
                    ) : isGenerating ? (
                      <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
                        <p className="text-indigo-300 text-sm font-medium">Rendering video...</p>
                      </div>
                    ) : (
                      <>
                        <div className="w-20 h-20 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mb-5">
                          <Play className="w-8 h-8 text-red-400 ml-1" />
                        </div>
                        <p className="text-red-400 text-sm font-bold">Video Engine Failed</p>
                        <p className="text-slate-600 text-xs mt-2 px-8 text-center">{results.video_status}</p>
                      </>
                    )}
                  </div>

                  {results.video_script && !isReviewing && (
                    <div className="p-5 border-t border-slate-700/30">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-[10px] uppercase text-slate-500 font-bold tracking-[0.15em]">Final Narration Script</h4>
                        <CopyButton text={results.video_script} label="Script" onCopy={copyToClipboard} />
                      </div>
                      <p className="text-sm text-slate-400 italic leading-relaxed">&quot;{results.video_script}&quot;</p>
                    </div>
                  )}
                </motion.div>
              )}

              {/* Text Outputs Grid — Cards appear as data streams in */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                <AnimatePresence>
                  {results.twitter && (
                    <OutputCard
                      key="twitter"
                      title="Twitter Thread"
                      icon={<Twitter className="w-3.5 h-3.5" />}
                      content={results.twitter}
                      accentColor="sky"
                      delay={0}
                      onCopy={copyToClipboard}
                      shareUrl={`https://twitter.com/intent/tweet?text=${encodeURIComponent(results.twitter)}`}
                    />
                  )}
                  {results.linkedin && (
                    <OutputCard
                      key="linkedin"
                      title="LinkedIn Post"
                      icon={<Linkedin className="w-3.5 h-3.5" />}
                      content={results.linkedin}
                      accentColor="blue"
                      delay={0.05}
                      onCopy={copyToClipboard}
                      shareUrl={`https://www.linkedin.com/feed/?shareActive=true&text=${encodeURIComponent(results.linkedin)}`}
                    />
                  )}
                  {results.instagram && (
                    <OutputCard
                      key="instagram"
                      title="Instagram Caption"
                      icon={<Instagram className="w-3.5 h-3.5" />}
                      content={results.instagram}
                      accentColor="rose"
                      delay={0.1}
                      onCopy={copyToClipboard}
                    />
                  )}
                  {results.blog && (
                    <OutputCard
                      key="blog"
                      title="SEO Blog Post"
                      icon={<FileText className="w-3.5 h-3.5" />}
                      content={results.blog}
                      accentColor="amber"
                      delay={0.15}
                      onCopy={copyToClipboard}
                    />
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.8, delay: 0.2 }}
              className="h-full min-h-[600px] flex flex-col items-center justify-center text-slate-500 glass rounded-3xl relative overflow-hidden"
            >
              <div className="absolute top-1/4 left-1/4 w-64 h-64 bg-indigo-500/5 rounded-full blur-3xl" />
              <div className="absolute bottom-1/4 right-1/4 w-48 h-48 bg-purple-500/5 rounded-full blur-3xl" />

              <motion.div
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
                className="relative"
              >
                <div className="absolute inset-0 bg-indigo-500/10 rounded-full blur-2xl scale-150" />
                <div className="relative w-20 h-20 rounded-full bg-gradient-to-br from-slate-800/80 to-slate-900/80 border border-slate-700/50 flex items-center justify-center mb-6">
                  <Wand2 className="w-8 h-8 text-slate-500" />
                </div>
              </motion.div>

              <p className="font-bold text-slate-300 text-xl mt-2">Awaiting Pipeline Activation</p>
              <p className="text-sm mt-3 max-w-sm text-center text-slate-500 leading-relaxed">
                Enter a topic to trigger the multi-agent generation sequence across all platforms.
              </p>

              <div className="flex items-center gap-5 mt-8">
                {[
                  { label: 'Twitter', icon: <Twitter className="w-4 h-4 text-sky-500/50" /> },
                  { label: 'LinkedIn', icon: <Linkedin className="w-4 h-4 text-blue-500/50" /> },
                  { label: 'Instagram', icon: <Instagram className="w-4 h-4 text-rose-500/50" /> },
                  { label: 'Blog', icon: <FileText className="w-4 h-4 text-amber-500/50" /> },
                  { label: 'Video', icon: <Video className="w-4 h-4 text-purple-500/50" /> },
                ].map((item, i) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 + i * 0.1 }}
                    className="flex flex-col items-center gap-1.5"
                  >
                    <div className="w-10 h-10 rounded-xl bg-slate-800/50 border border-slate-700/30 flex items-center justify-center">
                      {item.icon}
                    </div>
                    <span className="text-[10px] font-semibold text-slate-600">{item.label}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </div>
      </main>
    </div>
  );
}

// ── Copy button component ──
function CopyButton({ text, label, onCopy }: { text: string; label: string; onCopy: (text: string, label: string) => void }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy(text, label);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 text-[10px] font-semibold text-slate-500 hover:text-indigo-400 transition-colors px-2 py-1 rounded-lg hover:bg-indigo-500/10"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

// ── Output card with copy button ──
function OutputCard({ title, icon, content, accentColor, delay, onCopy, shareUrl }: {
  title: string;
  icon: React.ReactNode;
  content: string;
  accentColor: string;
  delay: number;
  onCopy: (text: string, label: string) => void;
  shareUrl?: string;
}) {
  const colorMap: Record<string, { border: string; bg: string; text: string; iconBg: string }> = {
    sky: {
      border: 'hover:border-sky-500/30',
      bg: 'hover:shadow-sky-500/5',
      text: 'text-sky-400',
      iconBg: 'from-sky-500/20 to-sky-600/10',
    },
    blue: {
      border: 'hover:border-blue-500/30',
      bg: 'hover:shadow-blue-500/5',
      text: 'text-blue-400',
      iconBg: 'from-blue-500/20 to-blue-600/10',
    },
    amber: {
      border: 'hover:border-amber-500/30',
      bg: 'hover:shadow-amber-500/5',
      text: 'text-amber-400',
      iconBg: 'from-amber-500/20 to-amber-600/10',
    },
    rose: {
      border: 'hover:border-rose-500/30',
      bg: 'hover:shadow-rose-500/5',
      text: 'text-rose-400',
      iconBg: 'from-rose-500/20 to-rose-600/10',
    },
  };

  const colors = colorMap[accentColor] || colorMap.sky;

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className={`glass-strong rounded-2xl overflow-hidden transition-all duration-300 hover:shadow-xl ${colors.border} ${colors.bg}`}
    >
      <div className="p-4 border-b border-slate-700/20 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className={`w-7 h-7 bg-gradient-to-br ${colors.iconBg} rounded-lg flex items-center justify-center ${colors.text}`}>
            {icon}
          </div>
          <h3 className="font-bold text-sm text-white">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          {shareUrl && (
            <a
              href={shareUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px] font-semibold text-slate-500 hover:text-sky-400 transition-colors px-2 py-1 rounded-lg hover:bg-sky-500/10"
            >
              Share &rarr;
            </a>
          )}
          <CopyButton text={content || ''} label={title} onCopy={onCopy} />
        </div>
      </div>
      <div className="p-5 text-sm text-slate-400 whitespace-pre-wrap leading-relaxed max-h-[300px] overflow-y-auto custom-scrollbar">
        {content || "No content generated."}
      </div>
    </motion.div>
  );
}

// ── Hero Section with Video Background ──
function HeroSection({ onLaunch }: { onLaunch: () => void }) {
  return (
    <div className="relative w-full min-h-[95vh] flex flex-col items-center justify-start overflow-hidden bg-black selection:bg-indigo-500/30">

      {/* Looping Video Background */}
      <video
        src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260228_065522_522e2295-ba22-457e-8fdb-fbcd68109c73.mp4"
        autoPlay
        muted
        loop
        playsInline
        className="absolute inset-0 w-full h-full object-cover z-0 opacity-80"
      />

      {/* Subtle top/bottom dark gradient */}
      <div className="absolute inset-0 z-0 bg-gradient-to-b from-black/90 via-black/10 to-black/90 pointer-events-none" />

      {/* Navbar */}
      <nav className="relative z-20 w-[95%] max-w-7xl mx-auto mt-6 flex items-center justify-between px-6 py-4 glass-strong rounded-[16px] shadow-[0_0_30px_rgba(99,102,241,0.15)] border border-white/10 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="relative p-2 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-xl border border-indigo-500/30 glow-indigo">
            <Sparkles className="w-4 h-4 text-indigo-400" />
          </div>
          <span className="text-white font-bold text-lg tracking-tight">ContentCascade.ai</span>
        </div>

        <div className={`hidden md:flex items-center gap-8 text-white/80 text-[14px] ${barlow.className} font-medium tracking-wide`}>
          <a href="#" className="hover:text-white hover:text-shadow-sm transition-all duration-300">Features</a>
          <a href="#" className="hover:text-white hover:text-shadow-sm transition-all duration-300">Agents</a>
          <a href="#" className="hover:text-white hover:text-shadow-sm transition-all duration-300">Workflow</a>
          <a href="#" className="hover:text-white hover:text-shadow-sm transition-all duration-300">Pricing</a>
        </div>

        <button
          onClick={onLaunch}
          className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 text-white px-5 py-2.5 rounded-full text-sm font-semibold transition-all shadow-lg hover:shadow-indigo-500/25"
        >
          <Wand2 className="w-4 h-4" />
          Launch Pipeline
        </button>
      </nav>

      {/* Hero Content */}
      <div className="relative z-10 flex-col items-center justify-center flex-grow flex w-full max-w-5xl mx-auto text-center px-6 mt-[-5vh]">

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="flex flex-col items-center justify-center"
        >
          <span className={`text-white font-bold text-5xl md:text-7xl tracking-[-4px] ${barlow.className}`}>
            One Topic.
          </span>
          <span className={`text-transparent bg-clip-text bg-gradient-to-r from-white via-indigo-200 to-purple-300 text-[64px] md:text-[84px] leading-tight ${instrument.className} pb-2`}>
            Infinite Content.
          </span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className={`text-gray-300 text-[18px] max-w-2xl mt-6 font-medium ${barlow.className}`}
        >
          The AI engine that turns a single prompt or URL into a fully-synced HD video, Twitter thread, and SEO blog in 60 seconds.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="mt-10 flex flex-col items-center gap-5"
        >
          <button
            onClick={onLaunch}
            className="group flex items-center gap-3 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:from-indigo-400 hover:via-purple-400 hover:to-pink-400 text-white px-8 py-4 rounded-[32px] text-lg font-bold transition-all shadow-[0_0_40px_rgba(168,85,247,0.4)] hover:shadow-[0_0_60px_rgba(168,85,247,0.6)] hover:scale-[1.02] border border-white/20"
          >
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Play className="w-4 h-4 fill-white flex-shrink-0 ml-1" />
            </div>
            Generate Your Campaign
          </button>

          <a href="#tech-specs" className="text-white/60 text-sm hover:text-white underline underline-offset-4 decoration-white/30 transition-colors">
            Read the Technical Specs
          </a>
        </motion.div>

      </div>
    </div>
  );
}

export default function Page() {
  const scrollToDashboard = () => {
    document.getElementById('generator-dashboard')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="flex flex-col min-h-screen bg-black">
      <HeroSection onLaunch={scrollToDashboard} />
      <div id="generator-dashboard">
        <GeneratorDashboard />
      </div>
    </div>
  );
}
