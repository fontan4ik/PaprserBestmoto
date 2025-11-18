export type UserRole = "USER" | "ADMIN";

export interface ApiUser {
  telegram_id: number;
  username?: string | null;
  first_name?: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_seen_at?: string | null;
}

export type TaskStatus = "pending" | "processing" | "completed" | "failed" | "cancelled";

export interface ApiTask {
  id: string;
  task_type: string;
  status: TaskStatus;
  progress_percentage: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  priority: number;
  result_data?: Record<string, unknown>;
  error_message?: string | null;
}

export interface TaskProgress {
  status: TaskStatus;
  progress: number;
  payload?: Record<string, unknown>;
}

export interface ApiFile {
  id: string;
  filename: string;
  file_size: number;
  upload_date: string;
}

export interface OverviewStats {
  active_users: number;
  total_tasks: number;
  completed_tasks: number;
  avg_duration_seconds: number;
  storage_usage_mb: number;
}

export interface UserStatsPoint {
  date: string;
  new_users: number;
  active_users: number;
}

export interface TaskLogEntry {
  id: number;
  task_id: string;
  user_id?: number | null;
  message: string;
  level: string;
  task_type?: string | null;
  task_status?: string | null;
  created_at: string;
}

