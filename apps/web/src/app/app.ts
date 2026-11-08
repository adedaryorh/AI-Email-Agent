import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Auth } from './core/auth';
import { Icon } from './core/ui';
import { errorMessage } from './core/api';

@Component({selector:'app-root', imports:[RouterOutlet], template:'<router-outlet />'})
export class App {}
@Component({imports:[RouterOutlet,RouterLink,RouterLinkActive,Icon], template:`
<a href="#main-content" class="skip-link">Skip to content</a><div class="app-layout">
  <aside class="sidebar">
    <a routerLink="/overview" class="brand"><span class="brand-mark"><app-icon name="mail"/></span><span>Email Agent<small>YOUR INBOX, CONSIDERED</small></span></a>
    <div class="workspace-label">WORKSPACE <span class="workspace-tag">Personal</span></div>
    <nav aria-label="Main navigation">
      @for (item of navigation; track item.path) {
        <a [routerLink]="item.path" routerLinkActive="active" ariaCurrentWhenActive="page"><app-icon [name]="item.icon"/><span>{{item.label}}</span></a>
      }
    </nav>
    <div class="sidebar-note"><span class="little-star">✦</span><strong>A little less inbox.</strong><p>Let AI sort the details.<br>You make the decisions.</p></div>
    <div class="account"><span class="avatar">{{auth.user()?.username?.slice(0,1)?.toUpperCase()}}</span><div><strong>{{auth.user()?.username}}</strong><small>Personal workspace</small></div><button class="icon-button" (click)="logout()" [disabled]="leaving()" aria-label="Sign out"><app-icon name="logout"/></button></div>
  </aside>
  <div class="workspace"><header class="topbar"><span>Workspace <span class="slash">/</span> Email management</span><span class="private-label"><span class="status-dot"></span> Human-approved sending</span><button class="mobile-signout" (click)="logout()" [disabled]="leaving()" aria-label="Sign out"><app-icon name="logout"/></button></header>
    <main id="main-content">@if (logoutError()) {<div role="alert" class="alert error">{{logoutError()}}</div>}<router-outlet/></main>
    <footer>Built for a calmer inbox.<span>Gmail · AI-assisted · Always in your control</span></footer>
  </div>
</div>`})
export class Shell {
  readonly auth = inject(Auth); readonly router = inject(Router);
  readonly leaving = signal(false); readonly logoutError = signal('');
  readonly navigation = [
    {path:'/overview',label:'Overview',icon:'overview'}, {path:'/messages',label:'Messages',icon:'mail'},
    {path:'/review',label:'Review queue',icon:'review'}, {path:'/drafts',label:'Draft replies',icon:'drafts'},
    {path:'/rules',label:'Rules',icon:'rules'}, {path:'/analytics',label:'Analytics',icon:'chart'},
    {path:'/knowledge',label:'Knowledge',icon:'rules'}, {path:'/preferences',label:'Preferences',icon:'review'},
    {path:'/agent',label:'Agent activity',icon:'chart'},
    {path:'/mailboxes',label:'Mailboxes',icon:'link'},
  ];
  async logout() { this.leaving.set(true); try { await this.auth.logout(); await this.router.navigateByUrl('/login'); } catch(e) {this.logoutError.set(errorMessage(e));} finally {this.leaving.set(false);} }
}
