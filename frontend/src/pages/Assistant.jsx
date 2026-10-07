import { AlertCircle, Bot, Database, Send, Sparkles, User } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { aiApi } from '../api/endpoints';
import { Badge, Card, PageHeader, Spinner } from '../components/ui';
import { useApi } from '../hooks/useApi';
import { humanise } from '../utils/format';

const GREETING = {
  role: 'assistant',
  content:
    "Hello. I can answer questions about your sales, revenue, products, customers, stock and forecasts. Every answer is built from your actual business data, so if the data is not there I will tell you rather than guess.",
  meta: null,
};

export default function Assistant() {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const { data: status } = useApi(() => aiApi.status(), []);
  const suggestions = status?.suggested_questions ?? [];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const send = async (question) => {
    const text = (question ?? input).trim();
    if (!text || sending) return;

    setMessages((current) => [...current, { role: 'user', content: text }]);
    setInput('');
    setSending(true);

    try {
      const response = await aiApi.chat(text, true);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: response.answer,
          meta: {
            intent: response.routing.intent,
            agent: response.routing.agent,
            confidence: response.routing.confidence,
            sources: response.sources,
            dataAvailable: response.data_available,
            provider: response.provider,
            elapsedMs: response.elapsed_ms,
            suggestions: response.suggestions,
          },
        },
      ]);
    } catch (err) {
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: err.message, error: true },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <PageHeader
        title="AI Business Assistant"
        description="Ask about your business in plain language. Answers come from your data."
        actions={
          status && (
            <Badge className="bg-slate-100 text-slate-600">
              <Sparkles className="mr-1 h-3 w-3" />
              {status.provider.active === 'offline'
                ? 'Offline mode'
                : `${status.provider.active} · ${status.provider.model ?? ''}`}
            </Badge>
          )
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <Card className="lg:col-span-3" bodyClassName="p-0">
          <div ref={scrollRef} className="h-[calc(100vh-22rem)] min-h-[24rem] overflow-y-auto p-5">
            <div className="space-y-5">
              {messages.map((message, index) => (
                <Message key={index} message={message} onFollowUp={send} />
              ))}
              {sending && (
                <div className="flex gap-3">
                  <Avatar role="assistant" />
                  <div className="flex items-center gap-2 rounded-xl bg-slate-50 px-4 py-3">
                    <Spinner className="h-4 w-4" />
                    <span className="text-sm text-slate-500">
                      Retrieving your business data…
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <form
            className="flex gap-2 border-t border-surface-border p-4"
            onSubmit={(event) => {
              event.preventDefault();
              send();
            }}
          >
            <input
              className="input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about sales, stock, customers or forecasts…"
              disabled={sending}
              aria-label="Your question"
            />
            <button type="submit" className="btn-primary" disabled={sending || !input.trim()}>
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>
        </Card>

        <div className="space-y-4">
          <Card title="Suggested questions" bodyClassName="p-3">
            <div className="flex flex-col gap-1.5">
              {suggestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="rounded-lg px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:bg-brand-50 hover:text-brand-700"
                  onClick={() => send(question)}
                  disabled={sending}
                >
                  {question}
                </button>
              ))}
            </div>
          </Card>

          <Card title="How answers are produced">
            <ol className="space-y-2 text-xs text-slate-600">
              {[
                'Your question is classified into an intent',
                'The matching agent queries your database and models',
                'Retrieved facts are assembled into a context',
                'The answer is written from those facts only',
              ].map((step, index) => (
                <li key={step} className="flex gap-2">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-brand-100 text-[10px] font-semibold text-brand-700">
                    {index + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
            <p className="mt-3 border-t border-surface-border pt-3 text-xs text-slate-500">
              The assistant never invents figures. If your data cannot answer a question, it
              says so.
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}

function Avatar({ role }) {
  const assistant = role === 'assistant';
  return (
    <span
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
        assistant ? 'bg-brand-100 text-brand-700' : 'bg-slate-200 text-slate-600'
      }`}
    >
      {assistant ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
    </span>
  );
}

function Message({ message, onFollowUp }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="flex justify-end gap-3">
        <div className="max-w-[85%] rounded-xl bg-brand-600 px-4 py-2.5 text-sm text-white">
          {message.content}
        </div>
        <Avatar role="user" />
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <Avatar role="assistant" />
      <div className="min-w-0 max-w-[90%] flex-1">
        <div
          className={`rounded-xl px-4 py-3 text-sm ${
            message.error
              ? 'border border-red-200 bg-red-50 text-red-700'
              : 'bg-slate-50 text-slate-800'
          }`}
        >
          {message.error && (
            <span className="mb-1 flex items-center gap-1.5 font-medium">
              <AlertCircle className="h-4 w-4" />
              Could not answer
            </span>
          )}
          <div className="whitespace-pre-wrap leading-relaxed">{message.content}</div>
        </div>

        {message.meta && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            <Badge className="bg-slate-100 text-slate-600">
              {humanise(message.meta.agent)}
            </Badge>
            <Badge className="bg-slate-100 text-slate-600">
              {humanise(message.meta.intent)}
            </Badge>
            {!message.meta.dataAvailable && (
              <Badge className="bg-amber-50 text-amber-700">Insufficient data</Badge>
            )}
            {message.meta.sources?.length > 0 && (
              <span className="inline-flex items-center gap-1">
                <Database className="h-3 w-3" />
                {message.meta.sources.join(' · ')}
              </span>
            )}
            <span>{message.meta.elapsedMs} ms</span>
          </div>
        )}

        {message.meta?.suggestions?.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {message.meta.suggestions.slice(0, 3).map((question) => (
              <button
                key={question}
                type="button"
                className="rounded-full border border-surface-border bg-white px-3 py-1 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-700"
                onClick={() => onFollowUp(question)}
              >
                {question}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
