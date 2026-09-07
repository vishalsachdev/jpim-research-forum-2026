(() => {
  const PAGES_BASE = 'https://vishalsachdev.github.io/jpim-research-forum-2026/';
  const parallel = window.PROGRAM_DATA.papers;
  const special = window.PROGRAM_SPECIAL;

  const topicRules = [
    ['Artificial Intelligence', /\bAI\b|artificial intelligence|LLM|GenAI|large language|algorithm/i],
    ['Human–AI Collaboration', /human[–-]AI collaboration|human-LLM|AI-assisted|AI-augmented|AI-mediated/i],
    ['Innovation Strategy', /innovation strategy|new paradigms|firm-level|CEO|strategic/i],
    ['New Product & Service Development', /new product|product development|service development|NPD/i],
    ['Open Innovation & Ecosystems', /open innovation|innovation ecosystem|inbound open|platform/i],
    ['Consumer & User Innovation', /consumer|user innovation|user adoption|crowdfunding|usage/i],
    ['Responsible & Circular Innovation', /responsible|circular|sustainab|green innovation|climate/i],
    ['Future Making', /future-making|future making|uncertainty/i],
    ['Design & Creativity', /design thinking|creative|creativity|design practice|idea generation/i],
    ['Digital Innovation', /digital innovation|digital technology|Industry 4\.0|digital trust/i]
  ];

  const normalize = value => (value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const slugify = value => normalize(value).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 54);
  const sessionAnchor = item => item.type === 'Paper' && /^\d+$/.test(item.paperId || '')
    ? `paper-${item.paperId}`
    : `session-${item.date}-${item.start.replace(':','')}-${slugify(item.title)}`;
  const tagsFor = item => {
    const text = [item.track, item.title].filter(Boolean).join(' ');
    const tags = topicRules.filter(([, rule]) => rule.test(text)).map(([name]) => name);
    if (!tags.length && item.type === 'Paper') tags.push('General Innovation');
    if (item.type !== 'Paper') tags.push(item.type === 'Social' ? 'Networking & Social' : 'Forum Program');
    return [...new Set(tags)];
  };

  const sessions = [...parallel, ...special].map((item, index) => {
    const id = item.type === 'Paper' ? `paper-${item.paperId || item.slot}-${item.room}` : `event-${item.date}-${item.start}-${index}`;
    return { ...item, id, anchor: sessionAnchor(item), tags: tagsFor(item) };
  }).sort((a,b) => `${a.date}${a.start}${a.room || ''}`.localeCompare(`${b.date}${b.start}${b.room || ''}`));

  const state = { query:'', day:'all', topic:'all', presenter:'all', room:'all', type:'all', saved:new Set() };
  try { state.saved = new Set(JSON.parse(localStorage.getItem('jpim-rf-saved') || '[]')); } catch (_) {}

  const el = id => document.getElementById(id);
  const search = el('search');
  const topicFilter = el('topic-filter');
  const presenterFilter = el('presenter-filter');
  const roomFilter = el('room-filter');
  const typeFilter = el('type-filter');
  const schedule = el('schedule');
  const template = el('session-template');
  const empty = el('empty-state');
  const clear = el('clear-filters');

  const addOptions = (select, values) => values.filter(Boolean).sort((a,b)=>a.localeCompare(b)).forEach(value => {
    const option = document.createElement('option'); option.value = value; option.textContent = value; select.append(option);
  });
  addOptions(topicFilter, [...new Set(sessions.flatMap(s => s.tags))]);
  addOptions(presenterFilter, [...new Set(sessions.flatMap(s => [s.presenter, ...(s.participants || [])]).filter(Boolean))]);
  addOptions(roomFilter, [...new Set(sessions.filter(s=>s.room).map(s=>s.room))]);
  addOptions(typeFilter, [...new Set(sessions.map(s=>s.type))]);

  const formatTime = value => {
    const [h,m] = value.split(':').map(Number);
    const suffix = h >= 12 ? 'PM' : 'AM';
    return `${h % 12 || 12}:${String(m).padStart(2,'0')} ${suffix}`;
  };
  const pageUrl = item => `${PAGES_BASE}#session=${encodeURIComponent(item.anchor)}`;
  const utcStamp = (date,time) => new Date(`${date}T${time}:00-04:00`).toISOString().replace(/[-:]/g,'').replace(/\.000/,'');
  const localIso = (date,time) => `${date}T${time}:00-04:00`;
  const icsEscape = value => String(value || '').replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
  const calendarDescription = item => {
    const facts = [item.presenter && `Presenter: ${item.presenter}`, item.track && `Track: ${item.track}`, item.paperId && `Paper ID: ${item.paperId}`].filter(Boolean);
    return [...facts, `Session details: ${pageUrl(item)}`].join('\n');
  };
  const calendarLinks = item => {
    const title = item.title;
    const details = calendarDescription(item);
    const location = item.room || 'Courtland Grand Hotel, Atlanta, GA';
    const startUtc = utcStamp(item.date,item.start);
    const endUtc = utcStamp(item.date,item.end);
    const params = values => new URLSearchParams(values).toString();
    const ics = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//JPIM Research Forum//Program 2026//EN','CALSCALE:GREGORIAN','BEGIN:VEVENT',`UID:${item.anchor}@jpim-research-forum-2026`,`DTSTAMP:${new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'')}`,`DTSTART;TZID=America/New_York:${item.date.replace(/-/g,'')}T${item.start.replace(':','')}00`,`DTEND;TZID=America/New_York:${item.date.replace(/-/g,'')}T${item.end.replace(':','')}00`,`SUMMARY:${icsEscape(title)}`,`DESCRIPTION:${icsEscape(details)}`,`LOCATION:${icsEscape(location)}`,`URL:${pageUrl(item)}`,'END:VEVENT','END:VCALENDAR'].join('\r\n');
    return [
      ['Google Calendar', `https://calendar.google.com/calendar/render?${params({action:'TEMPLATE',text:title,dates:`${startUtc}/${endUtc}`,details,location})}`],
      ['Outlook.com', `https://outlook.live.com/calendar/0/action/compose?${params({rru:'addevent',subject:title,startdt:localIso(item.date,item.start),enddt:localIso(item.date,item.end),body:details,location})}`],
      ['Microsoft 365', `https://outlook.office.com/calendar/0/action/compose?${params({rru:'addevent',subject:title,startdt:localIso(item.date,item.start),enddt:localIso(item.date,item.end),body:details,location})}`],
      ['Yahoo Calendar', `https://calendar.yahoo.com/?${params({v:'60',view:'d',type:'20',title,st:startUtc,et:endUtc,desc:details,in_loc:location})}`],
      ['Apple / ICS download', `data:text/calendar;charset=utf-8,${encodeURIComponent(ics)}`, `${item.anchor}.ics`]
    ];
  };
  const addDetail = (dl, term, value) => {
    if (!value) return;
    const dt = document.createElement('dt'); dt.textContent = term;
    const dd = document.createElement('dd'); dd.textContent = Array.isArray(value) ? value.join(', ') : value;
    dl.append(dt, dd);
  };
  const scholarUrl = name => `https://scholar.google.com/citations?view_op=search_authors&mauthors=${encodeURIComponent(name)}`;
  const personLink = name => {
    const link = document.createElement('a');
    link.className = 'person-link'; link.href = scholarUrl(name); link.target = '_blank'; link.rel = 'noreferrer';
    link.textContent = name; link.title = `Find ${name} on Google Scholar`;
    return link;
  };
  const splitNames = value => (Array.isArray(value) ? value : String(value || '').replace(/\s+and\s+/gi, ', ').split(',')).map(v=>v.trim()).filter(Boolean);
  const addPeopleDetail = (dl, term, value) => {
    const names = splitNames(value); if (!names.length) return;
    const dt = document.createElement('dt'); dt.textContent = term;
    const dd = document.createElement('dd');
    names.forEach((name,index) => { if (index) dd.append(document.createTextNode(', ')); dd.append(personLink(name)); });
    dl.append(dt, dd);
  };
  const searchText = s => normalize([s.title,s.presenter,s.coauthors,s.discussant,s.chair,s.track,s.room,s.paperId,s.slot,...(s.participants||[]),...s.tags].join(' '));

  function filteredSessions() {
    return sessions.filter(s => {
      if (state.day === 'saved' && !state.saved.has(s.id)) return false;
      if (state.day !== 'all' && state.day !== 'saved' && s.day !== state.day) return false;
      if (state.topic !== 'all' && !s.tags.includes(state.topic)) return false;
      if (state.presenter !== 'all' && s.presenter !== state.presenter && !(s.participants || []).includes(state.presenter)) return false;
      if (state.room !== 'all' && s.room !== state.room) return false;
      if (state.type !== 'all' && s.type !== state.type) return false;
      if (state.query && !searchText(s).includes(normalize(state.query))) return false;
      return true;
    });
  }

  function sessionCard(item) {
    const card = template.content.firstElementChild.cloneNode(true);
    card.dataset.kind = item.type;
    card.id = item.anchor;
    card.querySelector('.session-type').textContent = item.type === 'Paper' ? (item.slot || 'Paper') : item.type;
    card.querySelector('.session-title').textContent = item.title;
    const presenterName = card.querySelector('.presenter-name');
    if (item.presenter) presenterName.append(item.type === 'Social' ? document.createTextNode(item.presenter) : personLink(item.presenter));
    card.querySelector('.room-line').textContent = item.room || 'Forum-wide';
    const sourceLink = card.querySelector('.github-session-link');
    sourceLink.href = pageUrl(item);
    const calendarOptions = card.querySelector('.calendar-options');
    calendarLinks(item).forEach(([label,href,download]) => {
      const link = document.createElement('a'); link.href = href; link.textContent = label;
      if (download) link.download = download; else { link.target = '_blank'; link.rel = 'noreferrer'; }
      calendarOptions.append(link);
    });
    const saveButton = card.querySelector('.save-button');
    const syncSave = () => {
      const saved = state.saved.has(item.id);
      saveButton.classList.toggle('saved', saved);
      saveButton.setAttribute('aria-label', saved ? 'Remove saved session' : 'Save session');
      saveButton.firstElementChild.textContent = saved ? '★' : '☆';
    };
    syncSave();
    saveButton.addEventListener('click', () => {
      state.saved.has(item.id) ? state.saved.delete(item.id) : state.saved.add(item.id);
      localStorage.setItem('jpim-rf-saved', JSON.stringify([...state.saved]));
      syncSave(); render();
    });
    const dl = card.querySelector('.session-details');
    addDetail(dl, 'Time', `${formatTime(item.start)}–${formatTime(item.end)}`);
    addDetail(dl, 'Track', item.track);
    addPeopleDetail(dl, 'Chair', item.chair);
    if (item.type === 'Paper') addPeopleDetail(dl, 'Co-authors', item.coauthors);
    else if (item.coauthors) addDetail(dl, 'Details', item.coauthors);
    addPeopleDetail(dl, 'Also with', item.participants);
    addPeopleDetail(dl, 'Discussant', item.discussant);
    addDetail(dl, 'Paper ID', item.paperId);
    addDetail(dl, 'Topics', item.tags.join(', '));
    if (dl.children.length <= 2) card.querySelector('.detail-panel').remove();
    return card;
  }

  function render() {
    const visible = filteredSessions();
    schedule.replaceChildren();
    let lastDay = '';
    let lastTime = '';
    let grid = null;
    visible.forEach(item => {
      if (item.date !== lastDay) {
        const header = document.createElement('div'); header.className = 'day-heading';
        header.innerHTML = `<h2>${item.day}</h2><p>${item.day === 'Saturday' ? 'October 10' : 'October 11'}</p>`;
        schedule.append(header); lastDay = item.date; lastTime = '';
      }
      const groupKey = `${item.date}-${item.start}-${item.end}`;
      if (groupKey !== lastTime) {
        const group = document.createElement('div'); group.className = 'time-group';
        const label = document.createElement('div'); label.className = 'time-label';
        label.innerHTML = `<strong>${formatTime(item.start)}</strong><span>to ${formatTime(item.end)}</span>`;
        grid = document.createElement('div'); grid.className = 'session-grid';
        group.append(label, grid); schedule.append(group); lastTime = groupKey;
      }
      grid.append(sessionCard(item));
    });
    empty.hidden = visible.length > 0;
    el('result-count').textContent = `${visible.length} session${visible.length === 1 ? '' : 's'} shown`;
    el('saved-count').textContent = state.saved.size;
    const changed = state.query || state.day !== 'all' || [state.topic,state.presenter,state.room,state.type].some(v=>v !== 'all');
    clear.hidden = !changed;
  }

  function reset() {
    state.query=''; state.day='all'; state.topic='all'; state.presenter='all'; state.room='all'; state.type='all';
    search.value=''; topicFilter.value='all'; presenterFilter.value='all'; roomFilter.value='all'; typeFilter.value='all';
    document.querySelectorAll('.day-tab').forEach(b=>b.classList.toggle('active', b.dataset.day === 'all'));
    render();
  }

  search.addEventListener('input', e => { state.query=e.target.value; render(); });
  document.querySelectorAll('.day-tab').forEach(button => button.addEventListener('click', () => {
    state.day = button.dataset.day;
    document.querySelectorAll('.day-tab').forEach(b=>b.classList.toggle('active', b === button));
    render();
  }));
  [[topicFilter,'topic'],[presenterFilter,'presenter'],[roomFilter,'room'],[typeFilter,'type']].forEach(([node,key]) => node.addEventListener('change', e=>{ state[key]=e.target.value; render(); }));
  clear.addEventListener('click', reset);
  el('empty-clear').addEventListener('click', reset);
  document.addEventListener('keydown', e => { if (e.key === '/' && document.activeElement !== search) { e.preventDefault(); search.focus(); } });
  render();
  const linkedSession = location.hash.startsWith('#session=') ? decodeURIComponent(location.hash.slice(9)) : '';
  if (linkedSession) requestAnimationFrame(() => {
    const card = document.getElementById(linkedSession);
    if (!card) return;
    card.classList.add('linked-session');
    const details = card.querySelector('.detail-panel'); if (details) details.open = true;
    card.scrollIntoView({block:'center'});
  });
})();
