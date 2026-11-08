import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AgentRun, KnowledgeDocument, Preferences, Analytics, Category, Draft, Mailbox, Message, MessageDetail, Priority, Review, Rule, User } from './models';

@Injectable({providedIn: 'root'})
export class Api {
  private readonly http = inject(HttpClient);
  private get<T>(path: string) { return firstValueFrom(this.http.get<T>('/api/v1' + path)); }
  private post<T>(path: string, body: unknown = {}) { return firstValueFrom(this.http.post<T>('/api/v1' + path, body)); }
  knowledge() { return this.get<KnowledgeDocument[]>("/knowledge"); }
  saveKnowledge(doc: Omit<KnowledgeDocument,"id">, id?:number) { return id ? firstValueFrom(this.http.put<KnowledgeDocument>(`/api/v1/knowledge/${id}`,doc)) : this.post<KnowledgeDocument>("/knowledge",doc); }
  deleteKnowledge(doc:KnowledgeDocument) { return firstValueFrom(this.http.delete<void>(`/api/v1/knowledge/${doc.id}?version=${doc.version}`)); }
  preferences() { return this.get<Preferences>("/preferences"); }
  savePreferences(data:Preferences) { return firstValueFrom(this.http.put<Preferences>("/api/v1/preferences",data)); }
  agentRuns(offset=0) { return this.get<AgentRun[]>(`/agent/runs?offset=${offset}`); }
  agentRun(id:number) { return this.get<AgentRun>(`/agent/runs/${id}`); }
  session() { return this.get<User>('/auth/session'); }
  login(username: string, password: string) { return firstValueFrom(this.http.post<User>('/api/v1/auth/login', {username,password}, {headers:{'X-Requested-With':'EmailAgent'}})); }
  logout() { return this.post<void>('/auth/logout'); }
  mailboxes() { return this.get<Mailbox[]>('/mailboxes'); }
  connect() { return this.get<{auth_url: string}>('/mailboxes/connect/gmail'); }
  sync(id: number) { return this.post<{new_messages: number}>(`/mailboxes/${id}/sync`); }
  analytics() { return this.get<Analytics>('/analytics'); }
  messages(status = '', offset = 0) { return this.get<Message[]>(`/messages?limit=25&offset=${offset}${status ? '&status='+encodeURIComponent(status):''}`); }
  message(id: number) { return this.get<MessageDetail>(`/messages/${id}`); }
  retry(id: number) { return this.post<Message>(`/messages/${id}/retry`); }
  reviews(offset=0) { return this.get<Review[]>(`/review?limit=25&offset=${offset}`); }
  resolve(id: number, category: Category, priority: Priority) { return this.post<Message>(`/review/${id}/resolve`, {category,priority}); }
  drafts(status = '', offset = 0) { return this.get<Draft[]>(`/drafts?limit=25&offset=${offset}${status?'&status='+encodeURIComponent(status):''}`); }
  draft(id: number) { return this.get<Draft>(`/drafts/${id}`); }
  generate(id: number) { return this.post<Draft>(`/drafts/for-message/${id}`); }
  edit(draft: Draft, body: string) { return firstValueFrom(this.http.patch<Draft>(`/api/v1/drafts/${draft.id}`, {version:draft.version,body})); }
  draftAction(draft: Draft, action: 'approve'|'reject'|'regenerate'|'send') { return this.post<Draft>(`/drafts/${draft.id}/${action}`, {version:draft.version}); }
  reconcile(draft: Draft, remoteId: string) {
    const sending = ['sending','send_unknown'].includes(draft.status);
    return this.post<Draft>(`/drafts/${draft.id}/reconcile`, {version:draft.version,[sending?'gmail_message_id':'gmail_draft_id']:remoteId});
  }
  rules() { return this.get<Rule[]>('/rules'); }
  saveRule(rule: Omit<Rule,'id'>, id?: number) { return id ? firstValueFrom(this.http.put<Rule>(`/api/v1/rules/${id}`, rule)) : this.post<Rule>('/rules',rule); }
  deleteRule(id: number) { return firstValueFrom(this.http.delete<void>(`/api/v1/rules/${id}`)); }
  testRule(id: number, messageId: number) { return this.post<{matched: boolean; actions: unknown[]}>(`/rules/${id}/test`, {message_id:messageId}); }
}

export function errorMessage(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    if (error.status === 0) return 'Cannot reach the server. Check your connection and try again.';
    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item: {loc?: string[]; msg?: string}) => `${item.loc?.slice(1).join('.') || 'Input'}: ${item.msg || 'Invalid value'}`).join(' · ');
    return `Request failed (${error.status}). Please try again.`;
  }
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}
