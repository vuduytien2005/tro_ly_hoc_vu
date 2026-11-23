import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CircleAlert,
  CircleCheck,
  GraduationCap,
  Presentation,
  RotateCcw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { AnswerText, SourceList } from "../components/chat/Answer";
import { Composer, type Draft } from "../components/chat/Composer";
import { Feedback } from "../components/chat/Feedback";
import {
  PendingActionCard,
  type CardState,
} from "../components/chat/PendingActionCard";
import { StatusBanner } from "../components/chat/StatusBanner";
import {
  ToolChips,
  toolLabel,
  type ToolChip,
} from "../components/chat/ToolChips";
import { TracePanel } from "../components/chat/TracePanel";
import { FontButtons } from "../components/FontButtons";
import { ApiError, api } from "../lib/api";
import { DEMO_PROMPTS } from "../lib/demoPrompts";
import { CANCEL_PREFIX, CONFIRM_PREFIX } from "../lib/format";
import { fetchHealth, isRetryable } from "../lib/health";
import { readPrefill } from "../lib/reminders";
import {
  traceKey,
  useFontScale,
  usePresentationMode,
  type FontScale,
} from "../lib/presentation";
import { postSse } from "../lib/sse";
import type {
  AgentEvent,
  Citation,
  Conversation,
  Message,
  MessagesResponse,
  PendingAction,
} from "../lib/types";

const SUGGESTIONS = [
  "Em còn thiếu gì để tốt nghiệp?",
  "Lịch thi của em",
  "Học lại môn bị F thế nào?",
  "Xin giấy xác nhận sinh viên",
];

/** Lượt đang chạy (đang stream) — hiển thị tạm cho tới khi tải lại tin nhắn từ server. */
interface LiveTurn {
  userText: string;
  text: string;
  chips: ToolChip[];
  citations: Citation[] | null;
  breakNext: boolean; // có tool chen giữa -> đoạn chữ tiếp theo xuống đoạn mới
  finished: boolean;
}

/** Lỗi hiển thị dưới cuộc trò chuyện; `retryText` = tin nhắn gửi lại khi bấm "Thử lại". */
interface ChatError {
  text: string;
  retryText?: string;
}

interface CardOverride {
  state: CardState | "an";
  error?: string;
}

export default function ChatPage() {
  const { id } = useParams();
  const conversationId = id ? Number(id) : null;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [live, setLive] = useState<LiveTurn | null>(null);
  const [error, setError] = useState<ChatError | null>(null);
  const lastTextRef = useRef<string | null>(null);
  const [liveCards, setLiveCards] = useState<PendingAction[]>([]);
  const [overrides, setOverrides] = useState<Record<string, CardOverride>>({});
  const abortRef = useRef<AbortController | null>(null);
  const justCreatedRef = useRef<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [draft, setDraft] = useState<Draft | null>(null);

  // Chuông nhắc việc chuyển sang /chat kèm câu hỏi soạn sẵn: đặt vào ô nhập (không tự gửi),
  // rồi xóa state để tải lại trang không đặt lại lần nữa.
  const location = useLocation();
  const prefill = readPrefill(location.state);
  const [seenPrefillKey, setSeenPrefillKey] = useState<string | null>(null);
  if (prefill && location.key !== seenPrefillKey) {
    setSeenPrefillKey(location.key);
    setDraft((d) => ({ text: prefill, n: (d?.n ?? 0) + 1 }));
  }
  useEffect(() => {
    if (prefill) navigate(location.pathname, { replace: true, state: null });
  }, [prefill, navigate, location.pathname]);

  // Chế độ trình bày: chỉ khi backend bật CHE_DO_TRINH_BAY (dùng chung query /health với banner)
  const health = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
  });
  const presentationAllowed = health.data?.che_do_trinh_bay === true;
  const [presentationOn, setPresentationOn] = usePresentationMode();
  const presenting = presentationAllowed && presentationOn;
  const [fontScale, setFontScale] = useFontScale();
  const convIdRef = useRef<number | null>(conversationId);
  useEffect(() => {
    convIdRef.current = conversationId;
  }, [conversationId]);
  const refreshTrace = useCallback(
    (convId: number | null = convIdRef.current) =>
      queryClient.invalidateQueries({ queryKey: traceKey(convId) }),
    [queryClient],
  );

  const messages = useQuery({
    queryKey: ["messages", conversationId],
    queryFn: () =>
      api<MessagesResponse>(`/api/conversations/${conversationId}/messages`),
    enabled: conversationId != null,
  });

  // Chuyển hội thoại -> hủy luồng đang chạy, xóa trạng thái tạm.
  // Ngoại lệ: vừa tạo hội thoại mới trong lượt gửi đầu tiên (URL đổi nhưng luồng phải giữ).
  useEffect(() => {
    if (
      justCreatedRef.current != null &&
      justCreatedRef.current === conversationId
    ) {
      justCreatedRef.current = null;
      return;
    }
    abortRef.current?.abort();
    setLive(null);
    setError(null);
    setLiveCards([]);
    setOverrides({});
  }, [conversationId]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.data, live?.text, live?.chips.length, liveCards.length]);

  const busy = live != null && !live.finished;

  const onEvent = useCallback(
    (event: AgentEvent) => {
      switch (event.event) {
        case "token":
          setLive(
            (t) =>
              t && {
                ...t,
                text:
                  t.text +
                  (t.breakNext && t.text ? "\n\n" : "") +
                  event.data.text,
                breakNext: false,
              },
          );
          break;
        case "tool_start":
          setLive(
            (t) =>
              t && {
                ...t,
                breakNext: true,
                chips: [
                  ...t.chips,
                  {
                    ten: event.data.ten,
                    nhan: toolLabel(event.data.ten, event.data.nhan),
                    trang_thai: "dang_chay",
                  },
                ],
              },
          );
          break;
        case "tool_end":
          setLive((t) => {
            if (!t) return t;
            const chips = [...t.chips];
            const i = chips.findLastIndex(
              (c) => c.ten === event.data.ten && c.trang_thai === "dang_chay",
            );
            if (i >= 0)
              chips[i] = {
                ...chips[i],
                trang_thai:
                  event.data.trang_thai === "thanh_cong" ? "thanh_cong" : "loi",
              };
            return { ...t, chips };
          });
          refreshTrace();
          break;
        case "citations":
          setLive((t) => t && { ...t, citations: event.data });
          break;
        case "pending_action":
          setLiveCards((cards) => [
            ...cards.filter((c) => c.ma !== event.data.ma),
            event.data,
          ]);
          refreshTrace();
          break;
        case "error":
          // Lỗi trong luồng (vd mô hình ngôn ngữ quá tải / sai khóa API) -> cho thử lại nếu hợp lý
          setError({
            text: event.data.detail,
            retryText: isRetryable(event.data.code)
              ? (lastTextRef.current ?? undefined)
              : undefined,
          });
          break;
        case "done":
          refreshTrace();
          break;
      }
    },
    [refreshTrace],
  );

  /** Chạy một luồng SSE rồi tải lại tin nhắn đã lưu ở server. */
  const runStream = useCallback(
    async (convId: number, path: string, body: unknown, userText: string) => {
      const controller = new AbortController();
      abortRef.current = controller;
      setError(null);
      setLive({
        userText,
        text: "",
        chips: [],
        citations: null,
        breakNext: false,
        finished: false,
      });
      try {
        await postSse(path, body, onEvent, controller.signal);
      } catch (err) {
        if (controller.signal.aborted) return;
        throw err;
      } finally {
        if (!controller.signal.aborted) {
          setLive((t) => t && { ...t, finished: true });
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ["messages", convId] }),
            queryClient.invalidateQueries({ queryKey: ["conversations"] }),
            refreshTrace(convId),
          ]);
          setLive(null);
          setLiveCards([]);
        }
      }
    },
    [onEvent, queryClient, refreshTrace],
  );

  async function send(text: string) {
    let convId = conversationId;
    lastTextRef.current = text;
    try {
      if (convId == null) {
        const created = await api<Conversation>("/api/conversations", {
          method: "POST",
          json: {},
        });
        convId = created.id;
        justCreatedRef.current = convId;
        navigate(`/chat/${convId}`, { replace: true });
      }
      await runStream(
        convId,
        `/api/conversations/${convId}/messages`,
        { noi_dung: text },
        text,
      );
    } catch (err) {
      const apiError = err instanceof ApiError ? err : null;
      setError({
        text: apiError?.message ?? "Không gửi được tin nhắn, vui lòng thử lại.",
        retryText:
          !apiError || isRetryable(apiError.code, apiError.status)
            ? text
            : undefined,
      });
    }
  }

  async function confirm(action: PendingAction) {
    if (conversationId == null) return;
    setOverrides((o) => ({ ...o, [action.ma]: { state: "an" } }));
    try {
      await runStream(
        conversationId,
        `/api/actions/${action.ma}/confirm`,
        undefined,
        CONFIRM_PREFIX + action.mo_ta,
      );
    } catch (err) {
      // Lỗi trước khi mở luồng: 409 đã xử lý / hết hạn, 403...
      const expired =
        err instanceof ApiError && err.code === "HANH_DONG_HET_HAN";
      setOverrides((o) => ({
        ...o,
        [action.ma]: {
          state: expired ? "het_han" : "loi",
          error:
            err instanceof ApiError
              ? err.message
              : "Không thực hiện được, vui lòng thử lại.",
        },
      }));
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] });
      refreshTrace();
    }
  }

  async function cancel(action: PendingAction) {
    if (conversationId == null) return;
    setOverrides((o) => ({ ...o, [action.ma]: { state: "dang_xu_ly" } }));
    try {
      await api(`/api/actions/${action.ma}/cancel`, { method: "POST" });
      setOverrides((o) => ({ ...o, [action.ma]: { state: "an" } }));
      setLiveCards((cards) => cards.filter((c) => c.ma !== action.ma));
    } catch (err) {
      setOverrides((o) => ({
        ...o,
        [action.ma]: {
          state: "loi",
          error:
            err instanceof ApiError
              ? err.message
              : "Không hủy được, vui lòng thử lại.",
        },
      }));
    }
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["messages", conversationId] }),
      refreshTrace(),
    ]);
  }

  // Thẻ hiển thị = thẻ còn hiệu lực từ server + thẻ vừa sinh trong luồng, trừ thẻ đã ẩn
  const cards = dedupe([
    ...(messages.data?.hanh_dong_cho_xac_nhan ?? []),
    ...liveCards,
  ]).filter((c) => overrides[c.ma]?.state !== "an");
  const history = messages.data?.tin_nhan ?? [];
  const empty =
    conversationId == null ||
    (messages.isSuccess && history.length === 0 && !live);

  if (messages.isError) {
    const notFound =
      messages.error instanceof ApiError && messages.error.status === 404;
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-slate-500">
        {notFound
          ? "Không tìm thấy cuộc trò chuyện."
          : "Không tải được tin nhắn, vui lòng thử lại."}
      </div>
    );
  }

  const presenterToolbar = presenting && (
    <div className="mb-2 flex flex-wrap gap-1.5" aria-label="Câu hỏi soạn sẵn">
      {DEMO_PROMPTS.map((p) => (
        <button
          key={p.label}
          type="button"
          disabled={busy}
          title={p.text}
          onClick={() =>
            setDraft((d) => ({ text: p.text, n: (d?.n ?? 0) + 1 }))
          }
          className="rounded-full border border-line bg-slate-50 px-3 py-1 text-xs hover:border-primary hover:text-primary disabled:opacity-50"
        >
          {p.label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      <StatusBanner />
      {presentationAllowed && (
        <PresenterBar
          on={presentationOn}
          onToggle={setPresentationOn}
          scale={fontScale}
          onScale={setFontScale}
        />
      )}
      <div className="flex min-h-0 flex-1 max-lg:flex-col">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-3xl px-3 py-6 sm:px-6">
              {empty && !live && <Welcome onPick={send} disabled={busy} />}

              {history.map((m) => (
                <MessageView key={m.id} message={m} />
              ))}

              {live && (
                <>
                  <UserBubble text={live.userText} />
                  <AssistantBubble>
                    <ToolChips chips={live.chips} />
                    {live.text ? (
                      <AnswerText text={live.text} citations={live.citations} />
                    ) : (
                      !live.finished && <TypingDots />
                    )}
                    <SourceList citations={live.citations} />
                  </AssistantBubble>
                </>
              )}

              {cards.map((action) => (
                <PendingActionCard
                  key={action.ma}
                  action={action}
                  state={
                    (overrides[action.ma]?.state as CardState | undefined) ??
                    "cho"
                  }
                  error={overrides[action.ma]?.error}
                  onConfirm={() => confirm(action)}
                  onCancel={() => cancel(action)}
                />
              ))}

              {error && (
                <div
                  role="alert"
                  className="my-3 flex items-start gap-2 rounded-xl bg-err-bg px-4 py-3 text-sm text-err"
                >
                  <CircleAlert size={18} className="mt-0.5 shrink-0" />
                  <span className="flex-1">{error.text}</span>
                  {error.retryText && (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => error.retryText && send(error.retryText)}
                      className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-err/30 bg-white px-2.5 py-1 font-medium hover:bg-err-bg disabled:opacity-50"
                    >
                      <RotateCcw size={14} /> Thử lại
                    </button>
                  )}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>
          <Composer
            disabled={busy}
            onSend={send}
            draft={draft}
            toolbar={presenterToolbar}
          />
        </div>
        {presenting && <TracePanel conversationId={conversationId} />}
      </div>
    </div>
  );
}

/** Công tắc chế độ trình bày + cỡ chữ (chỉ hiện khi backend bật CHE_DO_TRINH_BAY). */
function PresenterBar({
  on,
  onToggle,
  scale,
  onScale,
}: {
  on: boolean;
  onToggle: (on: boolean) => void;
  scale: FontScale;
  onScale: (s: FontScale) => void;
}) {
  return (
    <div className="flex items-center justify-end gap-3 border-b border-line bg-white px-4 py-1.5 text-sm">
      <label className="inline-flex cursor-pointer items-center gap-2 text-slate-600">
        <input
          type="checkbox"
          checked={on}
          onChange={(e) => onToggle(e.target.checked)}
          className="h-4 w-4 accent-primary"
        />
        <Presentation size={16} /> Chế độ trình bày
      </label>
      {on && <FontButtons scale={scale} onScale={onScale} />}
    </div>
  );
}

function dedupe(actions: PendingAction[]): PendingAction[] {
  const seen = new Set<string>();
  return actions.filter((a) =>
    seen.has(a.ma) ? false : (seen.add(a.ma), true),
  );
}

function MessageView({ message }: { message: Message }) {
  if (message.vai_tro === "user") return <UserBubble text={message.noi_dung} />;
  return (
    <AssistantBubble>
      <AnswerText text={message.noi_dung} citations={message.trich_dan} />
      <SourceList citations={message.trich_dan} />
      <Feedback messageId={message.id} initial={message.danh_gia} />
    </AssistantBubble>
  );
}

function UserBubble({ text }: { text: string }) {
  // Tin hệ thống lưu khi sinh viên bấm trên thẻ xác nhận -> hiển thị dạng trạng thái
  if (text.startsWith(CONFIRM_PREFIX) || text.startsWith(CANCEL_PREFIX)) {
    const confirmed = text.startsWith(CONFIRM_PREFIX);
    const detail = text.slice(
      (confirmed ? CONFIRM_PREFIX : CANCEL_PREFIX).length,
    );
    return (
      <div className="my-3 flex justify-end">
        <div
          className={`flex max-w-[85%] items-start gap-2 rounded-2xl border px-4 py-2.5 text-sm ${
            confirmed
              ? "border-ok/20 bg-ok-bg text-ok"
              : "border-line bg-white text-slate-500"
          }`}
        >
          {confirmed ? (
            <CircleCheck size={18} className="mt-0.5 shrink-0" />
          ) : (
            <XCircle size={18} className="mt-0.5 shrink-0" />
          )}
          <span>
            <span className="font-medium">
              {confirmed ? "Đã xác nhận: " : "Đã hủy: "}
            </span>
            {detail}
          </span>
        </div>
      </div>
    );
  }
  return (
    <div className="my-3 flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-white">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-3 flex gap-3">
      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-navy text-accent">
        <Sparkles size={16} />
      </div>
      <div className="min-w-0 max-w-[85%] flex-1 rounded-2xl rounded-tl-md border border-line bg-white px-4 py-3">
        {children}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 py-1" aria-label="Trợ lý đang trả lời">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-2 w-2 animate-bounce rounded-full bg-slate-300"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

function Welcome({
  onPick,
  disabled,
}: {
  onPick: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-col items-center py-10 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-navy text-accent">
        <GraduationCap size={28} />
      </div>
      <h1 className="mb-1 text-xl font-semibold text-navy">
        Chào em, mình có thể giúp gì?
      </h1>
      <p className="mb-6 max-w-md text-sm text-slate-500">
        Hỏi về quy chế đào tạo, điểm, lịch thi, học phí hoặc nhờ mình làm thủ
        tục học vụ.
      </p>
      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            disabled={disabled}
            onClick={() => onPick(s)}
            className="min-h-11 rounded-[10px] border border-line bg-white px-4 py-2 text-left text-sm hover:border-primary hover:text-primary disabled:opacity-50"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
