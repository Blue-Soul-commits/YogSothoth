export interface Repo {
  id: string;
  name: string;
  git_url: string;
  default_branch: string;
  local_path: string | null;
  indexed_at: string | null;
  summary: string | null;
}

export interface RepoGroup {
  id: string;
  name: string;
  description: string;
  repo_ids: string[];
  indexed_at: string | null;
}

export interface QAResponse {
  answer_text: string;
  references: {
    repo_id: string;
    file_path: string;
    start_line: number;
    end_line: number;
    score?: number;
  }[];
}

export interface OutlineResponse {
  repo_id: string;
  outline: string;
}
