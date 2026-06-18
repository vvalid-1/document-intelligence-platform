export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed';

export interface DocumentResponse {
  id: string;
  title: string;
  original_name: string;
  file_path: string;
  file_size_bytes: number;
  mime_type: string;
  status: DocumentStatus;
  page_count: number | null;
  chunk_count: number;
  is_deleted: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface Source {
  document_id: string;
  chunk_id: string;
  page_number: number | null;
  excerpt: string;
  similarity: number;
}

export interface ChatMessageResponse {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: Source[];
  created_at: string;
}

export interface ChatSessionResponse {
  id: string;
  user_id: string;
  session_name: string | null;
  document_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReviewIssue {
  type: string;
  severity: 'low' | 'medium' | 'high';
  description: string;
  location: string | null;
  suggestion: string | null;
}

export interface ReviewResponse {
  id: string;
  document_id: string;
  version_id: string | null;
  version_number: number;
  task_id: string | null;
  review_summary: string;
  issue_count: number;
  clarity_score: number | null;
  consistency_score: number | null;
  completeness_score: number | null;
  issues: ReviewIssue[];
  created_at: string;
}

export interface EditResponse {
  id: string;
  document_id: string;
  version_number: number;
  task_id: string | null;
  change_summary: string;
  text_preview: string;
  txt_path: string;
  pdf_path: string;
  created_at: string;
}

export type SignatureType = 'typed' | 'drawn';

export interface SignatureResponse {
  id: string;
  document_id: string;
  signed_by: string;
  version_id: string | null;
  version_number: number | null;
  signature_type: SignatureType;
  field_name: string | null;
  page_number: number;
  position_data: Record<string, number>;
  signature_image_path: string | null;
  signed_at: string;
}

export interface SignatureListResponse {
  items: SignatureResponse[];
  total: number;
}

export interface ApiError {
  detail: string;
}
