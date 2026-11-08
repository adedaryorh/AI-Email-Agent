import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../core/api';
import { Mailbox } from '../core/models';
import { Page } from '../core/page';
import { Icon, Notice } from '../core/ui';
@Component({imports:[DatePipe,Icon,Notice],template:`
<div class="page-heading"><div><span class="eyebrow">CONNECTIONS</span><h1>Your mailboxes</h1><p>Connect Gmail to start sorting and reviewing in one place.</p></div><button class="primary" (click)="connect()" [disabled]="busy()"><app-icon name="plus"/>Connect Gmail</button></div>
<app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
<div class="info-note">Connecting grants access to read messages, manage labels, create drafts and send replies you explicitly approve.</div>
<div class="mailbox-grid">@for (box of boxes(); track box.id) {<article class="panel mailbox-card"><div class="panel-heading"><span class="mailbox-logo">G</span><span class="badge" data-status="done">Connected</span></div><h2>{{box.email}}</h2><p>Gmail · Personal mailbox</p><dl><dt>Last successful sync</dt><dd>{{box.last_synced_at ? (box.last_synced_at | date:'medium') : 'Not synced yet'}}</dd></dl><button (click)="sync(box)" [disabled]="busy()">Sync now</button></article>} @empty { @if (!busy() && !error()) {<div class="panel empty"><app-icon name="link"/><h2>Your inbox belongs here</h2><p>Connect your Gmail account to get started.<br>Your agent will never send a reply without approval.</p><button class="primary" (click)="connect()">Connect Gmail</button></div>} }</div>
<button class="text-button" (click)="load()" [disabled]="busy()">Refresh connections</button>
@if (authUrl()) {<div class="panel connect-callout"><h2>Continue with Google</h2><p>Finish connecting in a new tab, then return here and refresh your connections.</p><a class="button primary" [href]="authUrl()" target="_blank" rel="noopener noreferrer">Open Google sign-in ↗</a></div>}
`})
export class Mailboxes extends Page {
  private readonly api=inject(Api);readonly boxes=signal<Mailbox[]>([]);readonly authUrl=signal('');
  constructor(){super();this.load();}
  load(){void this.run(async()=>{this.boxes.set(await this.api.mailboxes());});}
  connect(){void this.run(async()=>{const result=await this.api.connect();const url=new URL(result.auth_url);if(url.origin!=='https://accounts.google.com')throw new Error('Unexpected Google sign-in address');this.authUrl.set(url.toString());});}
  sync(box:Mailbox){void this.run(async()=>{const result=await this.api.sync(box.id);this.boxes.set(await this.api.mailboxes());this.notice.set(`${result.new_messages} new messages queued. Processing continues in the background; refresh Messages to see progress.`);});}
}
