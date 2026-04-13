/*
  NeuroLearn API Client
  Drop-in TypeScript client for the current FastAPI endpoints in api_main.py.
*/

export type UserRole = "student" | "teacher" | "admin";

export interface User {
  user_id: string;
  email: string;
  role: UserRole;
  name: string;
  student_id?: string | null;
  cohort_id?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: User;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface LogoutResponse {
  message: string;
}

export interface Source {
  source: string;
  page: number;
  chunk_id: string;
  excerpt: string;
  distance?: number | null;
  similarity_score?: number | null;
}

export interface TutorQuestionRequest {
  student_id: string;
  conversation_id: string;
  question: string;
  context?: Record<string, unknown> | null;
}

export interface TutorQuestionResponse {
  conversation_id: string;
  turn_id: string;
  answer: string;
  check_question?: string | null;
  check_answer_hint?: string | null;
  sources: Source[];
  status: "waiting_for_answer" | "answered" | "error" | string;
  generated_at: string;
}

export interface TutorAnswerRequest {
  student_id: string;
  conversation_id: string;
  turn_id: string;
  student_answer: string;
  check_answer_hint?: string | null;
}

export interface TutorAnswerResponse {
  conversation_id: string;
  turn_id: string;
  is_correct: boolean;
  feedback: string;
  misconception?: string | null;
  confidence: number;
  mastery_event_id: string;
  remediation?: string | null;
  status: "evaluated" | string;
  generated_at: string;
}

export interface ConversationTurn {
  turn_id: string;
  type: "question" | "answer" | "remediation" | string;
  question?: string | null;
  answer?: string | null;
  check_question?: string | null;
  check_answer_hint?: string | null;
  sources?: Source[] | null;
  student_answer?: string | null;
  is_correct?: boolean | null;
  feedback?: string | null;
  misconception?: string | null;
  confidence?: number | null;
  mastery_event_id?: string | null;
  remediation?: string | null;
  generated_at: string;
}

export interface ConversationResponse {
  conversation_id: string;
  student_id: string;
  created_at: string;
  updated_at: string;
  turns: ConversationTurn[];
  learning_goal?: string | null;
}

export interface StudentProfile {
  student_id: string;
  name: string;
  learning_style: string;
  reading_age: number;
  interests: string[];
  neuro_profile: string[];
  created_at: string;
  updated_at: string;
}

export interface StudentProfileRequest {
  name: string;
  learning_style: string;
  reading_age: number;
  interests: string[];
  neuro_profile: string[];
}

export interface MasteryEvent {
  id: string;
  student_id: string;
  concept_key: string;
  is_correct: boolean;
  confidence: number;
  misconception?: string | null;
  source_doc?: string | null;
  source_page?: number | null;
  source_chunk_id?: number | null;
  created_at: string;
}

export interface MasteryHistoryResponse {
  total: number;
  events: MasteryEvent[];
  limit: number;
  offset: number;
}

export interface LearningGoal {
  goal_id: string;
  goal_text: string;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface LearningGoalsResponse {
  active: LearningGoal[];
  archived: LearningGoal[];
}

export interface LearningGoalRequest {
  goal_text: string;
}

export interface RetrieverConfig {
  candidate_k: number;
  min_similarity: number;
  dedup_max_per_source_page: number;
  rerank_enabled: boolean;
  hybrid_enabled: boolean;
  top_k: number;
  notes?: string | null;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy" | string;
  timestamp: string;
  services: Record<string, string>;
}

export interface RootResponse {
  name: string;
  version: string;
  docs: string;
}

export interface DeleteConversationResponse {
  deleted: boolean;
}

export interface ApiClientOptions {
  baseUrl?: string;
  getAccessToken?: () => string | null;
  onAuthFailure?: (status: number) => void;
}

export class NeuroLearnApiError extends Error {
  status: number;
  details: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = "NeuroLearnApiError";
    this.status = status;
    this.details = details;
  }
}

export class NeuroLearnApiClient {
  private readonly baseUrl: string;
  private readonly getAccessToken?: () => string | null;
  private readonly onAuthFailure?: (status: number) => void;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? "http://localhost:8000";
    this.getAccessToken = options.getAccessToken;
    this.onAuthFailure = options.onAuthFailure;
  }

  private buildUrl(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    authRequired = true,
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});

    if (!headers.has("Content-Type") && init.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }

    if (authRequired) {
      const token = this.getAccessToken?.();
      if (!token) {
        throw new NeuroLearnApiError(401, "Missing access token");
      }
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(this.buildUrl(path), {
      ...init,
      headers,
    });

    let payload: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }

    if (!response.ok) {
      if ((response.status === 401 || response.status === 403) && this.onAuthFailure) {
        this.onAuthFailure(response.status);
      }

      const message =
        typeof payload === "object" && payload !== null && "detail" in payload
          ? String((payload as { detail?: unknown }).detail)
          : response.statusText || "API request failed";

      throw new NeuroLearnApiError(response.status, message, payload);
    }

    return payload as T;
  }

  // Meta
  root(): Promise<RootResponse> {
    return this.request<RootResponse>("/", { method: "GET" }, false);
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/api/health", { method: "GET" }, false);
  }

  // Authentication
  login(payload: LoginRequest): Promise<LoginResponse> {
    return this.request<LoginResponse>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    );
  }

  refreshToken(payload: RefreshRequest): Promise<LoginResponse> {
    return this.request<LoginResponse>(
      "/api/auth/refresh",
      { method: "POST", body: JSON.stringify(payload) },
      false,
    );
  }

  logout(): Promise<LogoutResponse> {
    return this.request<LogoutResponse>("/api/auth/logout", { method: "POST" }, true);
  }

  // Tutor
  tutorQuestion(payload: TutorQuestionRequest): Promise<TutorQuestionResponse> {
    return this.request<TutorQuestionResponse>(
      "/api/tutor/question",
      { method: "POST", body: JSON.stringify(payload) },
      true,
    );
  }

  tutorAnswer(payload: TutorAnswerRequest): Promise<TutorAnswerResponse> {
    return this.request<TutorAnswerResponse>(
      "/api/tutor/answer",
      { method: "POST", body: JSON.stringify(payload) },
      true,
    );
  }

  // Conversations
  getConversationHistory(studentId: string, limit = 10): Promise<ConversationResponse> {
    const q = new URLSearchParams({ limit: String(limit) }).toString();
    return this.request<ConversationResponse>(`/api/conversations/${encodeURIComponent(studentId)}?${q}`, {
      method: "GET",
    });
  }

  getConversationById(studentId: string, conversationId: string): Promise<ConversationResponse> {
    return this.request<ConversationResponse>(
      `/api/conversations/${encodeURIComponent(studentId)}/${encodeURIComponent(conversationId)}`,
      { method: "GET" },
    );
  }

  clearConversation(conversationId: string): Promise<DeleteConversationResponse> {
    return this.request<DeleteConversationResponse>(
      `/api/conversations/${encodeURIComponent(conversationId)}`,
      { method: "DELETE" },
    );
  }

  // Students
  getStudent(studentId: string): Promise<StudentProfile> {
    return this.request<StudentProfile>(`/api/students/${encodeURIComponent(studentId)}`, { method: "GET" });
  }

  updateStudent(studentId: string, payload: StudentProfileRequest): Promise<StudentProfile> {
    return this.request<StudentProfile>(
      `/api/students/${encodeURIComponent(studentId)}`,
      { method: "PUT", body: JSON.stringify(payload) },
    );
  }

  // Mastery
  getMasteryHistory(params: {
    studentId: string;
    limit?: number;
    offset?: number;
    conceptKey?: string;
  }): Promise<MasteryHistoryResponse> {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    if (params.conceptKey) query.set("concept_key", params.conceptKey);

    const suffix = query.toString() ? `?${query.toString()}` : "";
    return this.request<MasteryHistoryResponse>(
      `/api/students/${encodeURIComponent(params.studentId)}/mastery${suffix}`,
      { method: "GET" },
    );
  }

  getMasteryStats(studentId: string, recentDays = 7): Promise<Record<string, unknown>> {
    const q = new URLSearchParams({ recent_days: String(recentDays) }).toString();
    return this.request<Record<string, unknown>>(
      `/api/students/${encodeURIComponent(studentId)}/mastery/stats?${q}`,
      { method: "GET" },
    );
  }

  // Goals
  getLearningGoals(studentId: string): Promise<LearningGoalsResponse> {
    return this.request<LearningGoalsResponse>(
      `/api/students/${encodeURIComponent(studentId)}/goals`,
      { method: "GET" },
    );
  }

  createLearningGoal(studentId: string, payload: LearningGoalRequest): Promise<LearningGoal> {
    return this.request<LearningGoal>(
      `/api/students/${encodeURIComponent(studentId)}/goals`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }

  // Admin
  getRetrieverConfig(): Promise<RetrieverConfig> {
    return this.request<RetrieverConfig>("/api/admin/retriever/config", { method: "GET" });
  }

  updateRetrieverConfig(payload: RetrieverConfig): Promise<RetrieverConfig> {
    return this.request<RetrieverConfig>(
      "/api/admin/retriever/config",
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  }

  getSystemStats(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("/api/admin/system/stats", { method: "GET" });
  }
}

/*
Example:

const authStore = {
  accessToken: "",
};

const api = new NeuroLearnApiClient({
  baseUrl: "http://localhost:8000",
  getAccessToken: () => authStore.accessToken,
  onAuthFailure: () => {
    authStore.accessToken = "";
  },
});

const session = await api.login({
  email: "student@neurolearn.local",
  password: "student123",
  role: "student",
});
authStore.accessToken = session.access_token;

const result = await api.tutorQuestion({
  student_id: "s100",
  conversation_id: "conv-1",
  question: "കൈകഴുകൽ എന്തുകൊണ്ട് പ്രധാനമാണ്?",
  context: { top_k: 5 },
});
*/
