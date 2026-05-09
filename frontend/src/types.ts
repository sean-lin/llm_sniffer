export interface Session {
  id: string;
  name: string;
  created_at: string;
  last_active: string;
  request_count: number;
}

export interface RequestSummary {
  id: number;
  timestamp: string;
  client_type: 'openai' | 'anthropic';
  model: string;
  request_body: RequestBody | null;
  response_body: ResponseBody | null;
  status_code: number;
  duration_ms: number;
  stream: boolean;
  error: string | null;
}

export interface RequestDetail extends RequestSummary {
  session_id: string;
  media: MediaFile[];
}

export interface MediaFile {
  id: number;
  role: 'request' | 'response';
  media_type: 'image' | 'audio';
  mime_type: string;
  file_path: string;
  message_index: number;
}

export interface Message {
  role: string;
  content: string | ContentBlock[];
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ContentBlock {
  type: string;
  text?: string;
  image_url?: { url: string };
  [key: string]: unknown;
}

export interface ToolCall {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
}

export interface RequestBody {
  model?: string;
  messages?: Message[];
  stream?: boolean;
  tools?: unknown[];
  [key: string]: unknown;
}

export interface ResponseBody {
  choices?: Array<{
    message?: Message;
    finish_reason?: string;
  }>;
  content?: ContentBlock[];
  [key: string]: unknown;
}
