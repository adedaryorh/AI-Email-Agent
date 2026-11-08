import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Api } from '../core/api';
import { Message, MessageDetail } from '../core/models';
import { Page } from '../core/page';
import { Notice } from '../core/ui';
@Component({imports:[DatePipe,JsonPipe,FormsModule,Notice],template:`
<div class="page-heading"><div><span class="eyebrow">THE BIG PICTURE</span><h1>Messages</h1><p>Your synced mail, its classifications and a record of every action.</p></div><button (click)="load()" [disabled]="busy()">Refresh messages</button></div>
<app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
<div class="toolbar"><label class="search-label">Filter this page<input aria-label="Filter this page by sender or subject" placeholder="Find a sender or subject…" [ngModel]="query()" (ngModelChange)="query.set($event)"></label><label>Status<select [(ngModel)]="status" (ngModelChange)="offset=0;load()" [disabled]="busy()"><option value="">All statuses</option>@for (s of statuses; track s) {<option [value]="s">{{s.replaceAll('_',' ')}}</option>}</select></label></div>
<div class="panel table-wrap"><table><thead><tr><th>Message</th><th>Status</th><th>Received</th><th><span class="sr-only">Details</span></th></tr></thead><tbody>@for (message of filtered(); track message.id) {<tr><td><strong>{{message.subject || '(No subject)'}}</strong><small>{{message.sender}}</small></td><td><span class="badge" [attr.data-status]="message.status">{{message.status.replaceAll('_',' ')}}</span></td><td>{{message.received_at | date:'MMM d, HH:mm'}}</td><td><button (click)="open(message.id)" [disabled]="busy()" [attr.aria-label]="'Open '+message.subject">Open →</button></td></tr>} @empty {<tr><td colspan="4" class="empty-cell">{{busy()?'Loading messages…':error()?'Messages could not be loaded. Try refreshing.':'No messages match this view.'}}</td></tr>}</tbody></table></div>
<div class="pagination"><span>Showing {{rows().length ? offset+1 : 0}}–{{offset+rows().length}} of the loaded result</span><button (click)="offset=offset-25;load()" [disabled]="busy() || offset===0">Previous</button><button (click)="offset=offset+25;load()" [disabled]="busy() || rows().length<25">Next</button></div>
@if (selected(); as mail) {<section class="panel detail-panel"><div class="panel-heading"><div><span class="eyebrow">MESSAGE #{{mail.id}}</span><h2>{{mail.subject || '(No subject)'}}</h2></div><button (click)="selected.set(null)" [disabled]="busy()">Close</button></div><p class="muted">{{mail.sender}} · {{mail.received_at | date:'medium'}}</p><div class="email-body">{{mail.body_text || 'No body content available.'}}</div><div class="action-row">@if (mail.status==='failed' || mail.status==='processing') {<button (click)="retry(mail.id)" [disabled]="busy()">Retry processing</button>}<button class="primary" (click)="generate(mail.id)" [disabled]="busy() || !mail.body_text">Create reply draft</button></div><div class="detail-grid"><div><h3>Classifications</h3>@for (c of mail.classifications; track c.id) {<p><span class="badge">{{c.category}}</span> {{c.priority}} · {{(c.confidence*100).toFixed(0)}}% confidence</p><p>{{c.reason}} <small>({{c.source}})</small>}</div><div><h3>Extracted information</h3><pre>{{mail.entities | json}}</pre></div></div><h3>Activity</h3><ol class="activity-list">@for (event of mail.actions; track event.id) {<li><strong>{{event.action.replaceAll('_',' ')}}</strong><small>{{event.created_at | date:'medium'}} · {{event.actor}}</small></li>} @empty {<li>No actions recorded.</li>}</ol></section>}
`})
export class Messages extends Page {
  private readonly api=inject(Api);private readonly router=inject(Router);private readonly route=inject(ActivatedRoute);
  readonly rows=signal<Message[]>([]);readonly selected=signal<MessageDetail|null>(null);readonly query=signal('');
  readonly statuses=['new','processing','needs_review','done','failed'];status='';offset=0;
  readonly filtered=computed(()=>this.rows().filter(m=>(m.sender+' '+m.subject).toLowerCase().includes(this.query().toLowerCase())));
  constructor(){super();void this.run(async()=>{this.rows.set(await this.api.messages());const id=Number(this.route.snapshot.queryParamMap.get('id'));if(id>0)this.selected.set(await this.api.message(id));});}
  load(){void this.run(async()=>{this.rows.set(await this.api.messages(this.status,this.offset));});}
  open(id:number){void this.run(async()=>{this.selected.set(await this.api.message(id));});}
  retry(id:number){void this.run(async()=>{const result=await this.api.retry(id);this.selected.set(await this.api.message(id));this.rows.set(await this.api.messages(this.status,this.offset));this.notice.set(`Processing status: ${result.status.replaceAll('_',' ')}`);});}
  generate(id:number){void this.run(async()=>{const draft=await this.api.generate(id);await this.router.navigate(['/drafts'],{queryParams:{id:draft.id}});});}
}
