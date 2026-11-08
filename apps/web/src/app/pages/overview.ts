import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Api } from '../core/api';
import { Analytics, Mailbox, Message } from '../core/models';
import { Page } from '../core/page';
import { Icon, Notice } from '../core/ui';
@Component({imports:[DatePipe,RouterLink,Icon,Notice],template:`
<div class="page-heading"><div><span class="eyebrow">YOUR WORKSPACE AT A GLANCE</span><h1>A calmer inbox starts here.</h1><p>Keep an eye on what’s new. Give the important things your attention.</p></div><button (click)="load()" [disabled]="busy()">Refresh overview</button></div>
<app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
@if (data(); as stats) {
<div class="stats-grid"><article class="stat"><span>Messages synced<app-icon name="mail"/></span><strong>{{total(stats.messages_by_status)}}</strong><small>Across your connected mailboxes</small></article><article class="stat warm"><span>Need your review<app-icon name="review"/></span><strong>{{stats.messages_by_status['needs_review'] || 0}}</strong><a routerLink="/review">Open review queue ↗</a></article><article class="stat"><span>Drafts awaiting approval<app-icon name="drafts"/></span><strong>{{stats.drafts_by_status['pending'] || 0}}</strong><a routerLink="/drafts">Review your replies ↗</a></article><article class="stat"><span>Messages processed<app-icon name="check"/></span><strong>{{stats.messages_by_status['done'] || 0}}</strong><small>Sorting workflow completed</small></article></div>
<section class="focus-banner"><div><span class="eyebrow">A SECOND PAIR OF EYES</span><h2>Your agent sorts. You stay in control.</h2><p>Review uncertain classifications and approve replies before anything sends.</p></div><a routerLink="/review" class="button primary">Go to review queue<app-icon name="arrow"/></a></section>
<div class="overview-grid"><section class="panel"><div class="panel-heading"><h2>Recent messages</h2><a routerLink="/messages">View all →</a></div>@for (message of recent(); track message.id) {<a routerLink="/messages" [queryParams]="{id:message.id}" class="message-preview"><span class="avatar subtle">{{message.sender.slice(0,1).toUpperCase()}}</span><div><strong>{{message.subject || '(No subject)'}}</strong><small>{{message.sender}}</small></div><span class="badge" [attr.data-status]="message.status">{{message.status.replaceAll('_',' ')}}</span></a>} @empty {<div class="empty"><app-icon name="mail"/><h3>Make room for a clearer inbox</h3><p>Connect Gmail and sync to see your messages here.</p><a routerLink="/mailboxes" class="button">Connect a mailbox</a></div>}</section>
<section class="panel"><div class="panel-heading"><h2>Connected mailboxes</h2><app-icon name="link"/></div>@for (box of boxes(); track box.id) {<div class="mailbox-preview"><span class="mailbox-logo">G</span><strong>{{box.email}}</strong><small>Last sync: {{box.last_synced_at ? (box.last_synced_at | date:'MMM d, HH:mm') : 'Not synced yet'}}</small></div>} @empty {<div class="empty small"><h3>No mailbox connected</h3><p>Bring your Gmail inbox into one place.</p></div>}<a routerLink="/mailboxes" class="panel-link">Manage mailboxes<app-icon name="arrow"/></a></section></div>
}`})
export class Overview extends Page {
  private readonly api=inject(Api);readonly data=signal<Analytics|null>(null);readonly recent=signal<Message[]>([]);readonly boxes=signal<Mailbox[]>([]);
  constructor(){super();this.load();}
  total(record:Record<string,number>){return Object.values(record).reduce((sum,n)=>sum+n,0);}
  load(){void this.run(async()=>{const [stats,messages,boxes]=await Promise.all([this.api.analytics(),this.api.messages(),this.api.mailboxes()]);this.data.set(stats);this.recent.set(messages.slice(0,5));this.boxes.set(boxes);});}
}
