import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient, withInterceptors, withXsrfConfiguration } from '@angular/common/http';
import { provideRouter, Routes } from '@angular/router';
import { provideZonelessChangeDetection } from '@angular/core';
import { App, Shell } from './app/app';
import { authenticated, sessionErrors, unsavedEdits } from './app/core/auth';
const routes: Routes = [
  {path:'login',loadComponent:()=>import('./app/pages/login').then(m=>m.Login)},
  {path:'',component:Shell,canActivate:[authenticated],children:[
    {path:'',pathMatch:'full',redirectTo:'overview'},
    {path:'overview',loadComponent:()=>import('./app/pages/overview').then(m=>m.Overview)},
    {path:'mailboxes',loadComponent:()=>import('./app/pages/mailboxes').then(m=>m.Mailboxes)},
    {path:'messages',loadComponent:()=>import('./app/pages/messages').then(m=>m.Messages)},
    {path:'review',loadComponent:()=>import('./app/pages/review').then(m=>m.Reviews)},
    {path:'drafts',canDeactivate:[unsavedEdits],loadComponent:()=>import('./app/pages/drafts').then(m=>m.Drafts)},
    {path:'rules',canDeactivate:[unsavedEdits],loadComponent:()=>import('./app/pages/rules').then(m=>m.Rules)},
    {path:'knowledge',canDeactivate:[unsavedEdits],loadComponent:()=>import('./app/pages/knowledge').then(m=>m.Knowledge)},
    {path:'preferences',canDeactivate:[unsavedEdits],loadComponent:()=>import('./app/pages/preferences').then(m=>m.PreferencesPage)},
    {path:'agent',loadComponent:()=>import('./app/pages/agent').then(m=>m.AgentPage)},
    {path:'analytics',loadComponent:()=>import('./app/pages/analytics').then(m=>m.AnalyticsPage)},
  ]},
  {path:'**',redirectTo:'overview'},
];
bootstrapApplication(App,{providers:[provideZonelessChangeDetection(),provideRouter(routes),provideHttpClient(withXsrfConfiguration({cookieName:'XSRF-TOKEN',headerName:'X-XSRF-TOKEN'}),withInterceptors([sessionErrors]))]}).catch(console.error);
