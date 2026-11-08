import { Component, input } from '@angular/core';
@Component({selector:'app-notice', template:`
  @if (error()) { <div class="alert error" role="alert">{{error()}}</div> }
  @if (notice()) { <div class="alert success" role="status">{{notice()}}</div> }
  @if (busy()) { <div class="loading-line" role="status"><span class="spinner"></span> Working…</div> }
`})
export class Notice { error = input(''); notice = input(''); busy = input(false); }
@Component({selector:'app-icon', template:`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path [attr.d]="paths[name()] || paths['mail']"/></svg>`, styles:[`:host{display:inline-flex;width:20px;height:20px;flex-shrink:0}svg{width:100%;height:100%}`]})
export class Icon {
  name = input('mail');
  paths: Record<string,string> = {
    mail:'M3 5h18v14H3z M3 6l9 7 9-7', overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    review:'M9 12l2 2 4-4 M5 3h14v18H5z', drafts:'M4 20l4-1 12-12-3-3L5 16z M14 7l3 3',
    rules:'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6', chart:'M4 3v17h17 M8 16v-5 M13 16V6 M18 16V9',
    link:'M10 14l4-4 M9 16l-2 2a4 4 0 01-5-5l4-4a4 4 0 015 0 M15 8l2-2a4 4 0 015 5l-4 4a4 4 0 01-5 0',
    arrow:'M5 12h14 M13 6l6 6-6 6', plus:'M12 5v14 M5 12h14', check:'M5 12l4 4L19 6', logout:'M9 3H4v18h5 M10 12h11 M17 8l4 4-4 4',
  };
}
