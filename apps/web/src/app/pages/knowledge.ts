import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Api } from '../core/api';
import { KnowledgeDocument } from '../core/models';
import { Page } from '../core/page';
import { Notice } from '../core/ui';
@Component({imports:[FormsModule,Notice],template:`
<div class="page-heading"><div><h1>Knowledge base</h1><p>Add trusted policies, FAQs and product information for grounded replies.</p></div><button (click)="select(null)" [disabled]="busy()">New document</button></div>
<app-notice [error]="error()" [notice]="notice()" [busy]="busy()"/>
<div class="split-view"><section class="panel list-panel">@for(doc of rows();track doc.id){<button class="list-item" (click)="select(doc)" [disabled]="busy()"><strong>{{doc.title}}</strong><small>Version {{doc.version}}</small></button>}@empty{<p class="empty">No documents yet. Paste a policy to get started.</p>}</section>
<section class="panel detail-panel"><h2>{{selected()?'Edit document':'New document'}}</h2><label>Title<input [(ngModel)]="title" maxlength="200" [disabled]="busy()"></label><label>Content<textarea class="reply-editor" [(ngModel)]="content" maxlength="50000" [disabled]="busy()"></textarea></label><p>Changes invalidate drafts that reference the previous version. Text is searched locally; relevant excerpts may be sent to your configured AI provider.</p><div class="action-row"><button class="primary" (click)="save()" [disabled]="busy() || !title.trim() || !content.trim()">Save document</button>@if(selected()){<button class="danger-link" (click)="remove()" [disabled]="busy()">Delete document</button>}</div></section></div>`})
export class Knowledge extends Page {
  private readonly api=inject(Api);readonly rows=signal<KnowledgeDocument[]>([]);readonly selected=signal<KnowledgeDocument|null>(null);title='';content='';
  constructor(){super();void this.run(async()=>this.rows.set(await this.api.knowledge()));}
  dirty(){return this.title!==(this.selected()?.title??'') || this.content!==(this.selected()?.content??'');}
  select(doc:KnowledgeDocument|null){if(this.dirty()&&!window.confirm('Discard unsaved changes?'))return;this.assign(doc);}
  private assign(doc:KnowledgeDocument|null){this.selected.set(doc);this.title=doc?.title??'';this.content=doc?.content??'';}
  save(){void this.run(async()=>{const doc=await this.api.saveKnowledge({title:this.title,content:this.content,version:this.selected()?.version??1},this.selected()?.id);this.assign(doc);this.rows.set(await this.api.knowledge());this.notice.set('Knowledge saved.');});}
  remove(){const doc=this.selected();if(!doc||!window.confirm('Delete this document? Referencing drafts will need regeneration.'))return;void this.run(async()=>{await this.api.deleteKnowledge(doc);this.assign(null);this.rows.set(await this.api.knowledge());});}
}
