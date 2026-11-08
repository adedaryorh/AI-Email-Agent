export const categories = ['support', 'billing', 'sales', 'newsletter', 'personal', 'spam', 'other'] as const;
export const priorities = ['low', 'normal', 'high', 'urgent'] as const;
export type Category = typeof categories[number];
export type Priority = typeof priorities[number];
export interface User { username: string }
export interface Mailbox { id: number; email: string; provider: string; last_synced_at: string | null }
export interface Message { id: number; mailbox_id: number; gmail_id: string; thread_id: string; sender: string; subject: string; status: string; received_at: string }
export interface Classification { id: number; category: Category; priority: Priority; confidence: number; reason: string; source: string; model: string; prompt_version: string; created_at: string }
export interface Audit { id: number; action: string; detail: Record<string, unknown>; actor: string; created_at: string }
export interface MessageDetail extends Message { body_text: string; entities: Record<string, unknown> | null; action_plan: Record<string, unknown> | null; attempts: number; classifications: Classification[]; actions: Audit[] }
export interface Review { message: Message; suggestion: Classification | null }
export interface Draft {
  sources?: {id:string;title:string;excerpt:string}[]; verification?: {passed:boolean; findings:string[]}; agent_run_id?:number|null; id: number; message_id: number; recipient: string; subject: string; body: string; status: string; version: number; gmail_draft_id: string | null; gmail_message_id: string | null; created_at: string }
export interface Definition { conditions: { field: string; op: string; value?: string }[]; actions: { type: string; value?: string }[] }
export interface Rule { id: number; name: string; enabled: boolean; position: number; definition: Definition }
export interface Analytics { messages_by_status: Record<string, number>; drafts_by_status: Record<string, number>; categories: Record<string, number> }

export interface KnowledgeDocument {id:number; title:string; content:string; version:number;}
export interface Preferences {instructions:string; version:number;}
export interface AgentRun {id:number;message_id:number;status:string;elapsed_ms:number;input_chars:number;created_at:string;events?:{tool:string;summary:string;elapsed_ms:number;estimated_cost_usd?:number|null;usage?:{input_tokens?:number;output_tokens?:number;total_tokens?:number}|null}[];}
