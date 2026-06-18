/**
 * TypeScript types mirroring the backend Pydantic schemas.
 * Keep in sync with app/agents/writer/schemas.py and app/graph/state.py.
 */

// ---------------------------------------------------------------------------
// Report types
// ---------------------------------------------------------------------------

export interface BodySection {
  heading: string;
  body: string;
  citation_numbers: number[];
}

export interface PhDAnnotations {
  state_of_art_analysis: string;
  future_possibilities: string;
  topic_overlap_and_inform: string;
  novelty_assessment: string;
  current_researchers: string;
}

export interface ReportContent {
  body_sections: BodySection[];
  synthesis: string;
  conclusion: string;
  phd_annotations?: PhDAnnotations | null;
}

export interface ReportCitation {
  number: number;
  source_url: string;
  source_type: "rag" | "web";
}

/** Shape returned by GET /api/v1/reports/:id */
export interface WorkflowOutput {
  id: string;
  session_id: string;
  title: string;
  introduction: string;
  content: ReportContent;
  word_count: number;
  quality_score?: number;
  citations: ReportCitation[];
  created_at: string;
}

// ---------------------------------------------------------------------------
// Resource discovery types (drives the flowchart)
// ---------------------------------------------------------------------------

export interface ConsultedResource {
  id: string;
  url: string;
  title: string;
  source_type: "web" | "rag";
  status: "discovering" | "evaluating" | "accepted" | "rejected";
  relevance_score?: number;
}

export interface AgentLogEntry {
  id: string;
  agent: "researcher" | "writer" | "critic" | "system";
  message: string;
}

// ---------------------------------------------------------------------------
// Workflow / session types
// ---------------------------------------------------------------------------

export interface ResearchSession {
  session_id: string;
  query: string;
  status: "running" | "complete" | "failed";
  report_id?: string;
  error?: string | null;
  created_at: string;
  completed_at?: string;
}

// ---------------------------------------------------------------------------
// UI state
// ---------------------------------------------------------------------------

export type ResearchMode = "general" | "phd";

export type AgentStep = {
  name: string;
  label: string;
  status: "pending" | "running" | "complete" | "failed";
};

export type ResearchPhase =
  | { kind: "idle" }
  | {
      kind: "running";
      query: string;
      mode: ResearchMode;
      startedAt: number;
      steps: AgentStep[];
      resources: ConsultedResource[];
      agentLog: AgentLogEntry[];
    }
  | {
      kind: "complete";
      query: string;
      mode: ResearchMode;
      output: WorkflowOutput;
      steps: AgentStep[];
      resources: ConsultedResource[];
      agentLog: AgentLogEntry[];
    }
  | { kind: "error"; query: string; message: string };
