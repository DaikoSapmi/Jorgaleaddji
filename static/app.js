// Jorgaleaddji & Divvun Studio – Client Application

import { UI_STRINGS } from './ui-strings.js';

const STORAGE_KEYS = {
  apiKey: 'sami_gemini_key',
  model: 'sami_gemini_model',
  thinking: 'sami_thinking_level',
  lang: 'sami_source_lang',
  autoDivvun: 'sami_auto_divvun',
  useLlm: 'sami_use_llm',
  glossary: 'sami_glossary',
};

const LANG_UI = {
  nor: {
    subtitle: 'Norsk → Nordsamisk',
    docTitle: 'Jorgaleaddji – Norsk → Nordsamisk',
    htmlLang: 'nb',
    sourcePlaceholder: 'Skriv eller lim inn norsk tekst her...',
    example:
      'Statsforvalteren har gitt fellingstillatelse på bjørn. Saken ble behandlet av kommunestyret i går, men jeg vet ikke om fem personer kommer i morgen eller på fredag.',
  },
  swe: {
    subtitle: 'Svenska → Nordsamiska',
    docTitle: 'Jorgaleaddji – Svenska → Nordsamiska',
    htmlLang: 'sv',
    sourcePlaceholder: 'Skriv eller klistra in svensk text här...',
    example:
      'Länsstyrelsen har gett tillstånd för björnjakt. Ärendet behandlades av kommunfullmäktige i går, men jag vet inte om fem personer kommer i morgon eller på fredag.',
  },
  fin: {
    subtitle: 'Suomi → Pohjoissaame',
    docTitle: 'Jorgaleaddji – Suomi → Pohjoissaame',
    htmlLang: 'fi',
    sourcePlaceholder: 'Kirjoita tai liitä suomenkielinen teksti tähän...',
    example:
      'Aluehallintovirasto on myöntänyt karhun kaatoluvan. Kunnanvaltuusto käsitteli asiaa eilen, mutta en tiedä, tuleeko viisi henkilöä huomenna vai perjantaina.',
  },
  eng: {
    subtitle: 'English → Northern Sámi',
    docTitle: 'Jorgaleaddji – English → Northern Sámi',
    htmlLang: 'en',
    sourcePlaceholder: 'Type or paste English text here...',
    example:
      'The County Governor has granted a license to cull a bear. The municipal council discussed the matter yesterday, but I do not know if five people will arrive tomorrow or on Friday.',
  },
  sme: {
    subtitle: 'Davvisámegiella – Gielladikšun ja divvun',
    docTitle: 'Jorgaleaddji – Davvisámegiel gielladikšun ja divvun',
    htmlLang: 'se',
    sourcePlaceholder: 'Čále dahje liibme davvisámegiel teavstta dása (gielladikšun ja divvun)...',
    example:
      'Ášši meannuduvvui suohkanstivrras ikte, muhto in dieđe jos 5 olbmot bohtet ihttin dahje bearjadaga. Mii eat sáhte váldit badjelasamet lasi barggu 25%.',
  },
};

const STARTER_GLOSSARY = {
  nor: 'Statsforvalteren = Stáhtahálddašeaddji\nSametinget = Sámediggi\nkommunestyret = suohkanstivra\nformannskapet = suohkanráđđi\nsaksbehandler = áššemeannudeaddji\nkunstig intelligens = dáhkkon jierbmi',
  swe: 'Sametinget = Sámediggi\nkommunfullmäktige = suohkanstivra\nhandläggare = áššemeannudeaddji\nartificiell intelligens = dáhkkon jierbmi',
  fin: 'Saamelaiskäräjät = Sámediggi\nkunnanvaltuusto = suohkanstivra\nkäsittelijä = áššemeannudeaddji\ntekoäly = dáhkkon jierbmi',
  eng: 'Sámi Parliament = Sámediggi\nmunicipal council = suohkanstivra\ncase officer = áššemeannudeaddji\nartificial intelligence = dáhkkon jierbmi',
  sme: 'Sámediggi = Sámediggi\nsuohkanstivra = suohkanstivra\náššemeannudeaddji = áššemeannudeaddji',
};

const TARGET_PLACEHOLDERS = {
  nor: 'Den ferdige nordsamiske teksten vises her...',
  swe: 'Den färdiga nordsamiska texten visas här...',
  fin: 'Valmis pohjoissaamenkielinen teksti näkyy tässä...',
  eng: 'The completed Northern Sámi text appears here...',
  sme: 'Dás oidno gárves davvisámegiel teaksta...',
};
const TARGET_LABELS = {
  nor: 'Nordsamisk',
  swe: 'Nordsamiska',
  fin: 'Pohjoissaame',
  eng: 'Northern Sámi',
  sme: 'Davvisámegiella',
};

const MODEL_DESCRIPTIONS = {
  nor: ['Rask og gratisnivå', 'Presis og effektiv', 'Dypest resonnering', 'Lynrask lettvekter'],
  swe: ['Snabb och gratisnivå', 'Precis och effektiv', 'Djupast resonemang', 'Blixtsnabb lättviktsmodell'],
  fin: ['Nopea ja maksuton taso', 'Tarkka ja tehokas', 'Syvällisin päättely', 'Salamannopea kevyt malli'],
  eng: ['Fast and free tier', 'Precise and efficient', 'Deepest reasoning', 'Lightning-fast lightweight model'],
  sme: ['Jođánis ja nuvttádássi', 'Dárkilis ja beaktilis', 'Čiekŋaleamos jurddašeapmi', 'Hui jođánis geahppis modealla'],
};
const MODEL_IDS = ['gemini-4-hydrogen', 'gemini-4-argon', 'gemini-4-carbon', 'gemini-3.5-flash-lite'];

const sourceEl = document.getElementById('sourceText');
const targetEl = document.getElementById('targetText');
const targetInteractiveEl = document.getElementById('targetInteractiveView');
const toggleTargetViewBtn = document.getElementById('toggleTargetViewBtn');
const spellPopoverEl = document.getElementById('spellPopover');
const statusText = document.getElementById('statusText');
const keyInput = document.getElementById('geminiKeyInput');
const modelSelect = document.getElementById('geminiModel');
const thinkingSelect = document.getElementById('thinkingLevel');
const autoDivvunCheckbox = document.getElementById('autoApplyDivvun');
const useLlmCheckbox = document.getElementById('useLlm');
const glossaryInput = document.getElementById('glossaryInput');
const badgeEl = document.getElementById('pipelineBadge');
const headerModelBadge = document.getElementById('headerModelBadge');
const headerModelLabel = document.getElementById('headerModelLabel');
const headerSubtitle = document.getElementById('headerSubtitle');
const clearBtn = document.getElementById('clearBtn');
const targetCount = document.getElementById('targetCount');
const satniInput = document.getElementById('satniQueryInput');
const cancelBtn = document.getElementById('cancelBtn');

let timerInterval = null;
let startTime = 0;
let currentSourceLang = 'nor';
let activeAbortController = null;
let lastFocusedEditor = sourceEl;
let lastDiffBaselineText = '';
let currentTargetErrors = [];
let isTargetEditMode = true;
let lastTips = [];
let lastImprovements = [];
let lastImprovementTranslations = {};
let lastErrors = [];
let divvunCheckIncomplete = false;
let lastResult = null;
let lastProgress = null;
let lastEndProgress = null;
let lastStatus = { key: 'ready', params: {}, suffix: '' };

function tr(key, params = {}) {
  const text = UI_STRINGS[currentSourceLang][key];
  if (text === undefined) throw new Error(`Missing UI translation: ${currentSourceLang}.${key}`);
  return text.replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`));
}

function setStatus(key, params = {}, suffix = '') {
  lastStatus = { key, params, suffix };
  statusText.textContent = `${tr(key, params)}${suffix}`;
}

function translateStaticUI() {
  const texts = {
    '#toggleSettingsBtn span': 'settings',
    'label[for="geminiModel"]': 'model',
    '#refreshModelsBtn': 'refresh',
    'label[for="thinkingLevel"]': 'thinking',
    '#thinkingLevel option[value="low"]': 'low',
    '#thinkingLevel option[value="medium"]': 'medium',
    '#thinkingLevel option[value="high"]': 'high',
    'label[for="geminiKeyInput"]': 'apiKey',
    '#autoApplyDivvun + span': 'autoDivvun',
    '#useLlm + span': 'useGemini',
    'label[for="glossaryInput"]': 'glossary',
    '#starterGlossaryBtn': 'starter',
    '#cancelBtn': 'cancel',
    '#stepPill4': 'finalCheck',
    '.toolbar-caption': 'characters',
    'label[for="satniQueryInput"]': 'search',
    '#exampleBtn': 'example',
    '#clearBtn': 'clear',
    'label[for="sourceText"]': 'sourceText',
    'label[for="targetText"]': 'targetText',
    '#recheckDivvunBtn': 'recheck',
    '#copyBtn span': 'copy',
    '#tabBtnImprovements span:first-child': 'tipsTab',
    '#tabBtnDivvun span:first-child': 'divvunTab',
    '#tabBtnDiff span:first-child': 'diffTab',
    '.guidelines-details summary span': 'guidelines',
  };
  for (const [selector, key] of Object.entries(texts)) {
    document.querySelector(selector).textContent = tr(key);
  }
  const attributes = [
    ['#homeLink', 'title', 'reloadPage'],
    ['#toggleSettingsBtn', 'title', 'settingsTitle'],
    ['#geminiKeyInput', 'placeholder', keyInput.dataset.envKey === 'true' ? 'keyEnv' : 'keyPlaceholder'],
    ['#progressSpinner', 'aria-label', 'working'],
    ['.sami-toolbar', 'aria-label', 'toolbar'],
    ['[data-char="”"]', 'title', 'quote'],
    ['[data-char="–"]', 'title', 'dash'],
    ['#satniQueryInput', 'placeholder', 'searchPlaceholder'],
    ['#satniLookupBtn', 'title', 'lookup'],
    ['.lang-switcher', 'aria-label', 'sourceLanguage'],
    ['.kbd-hint', 'title', 'shortcut'],
    ['#pipelineDetails', 'aria-label', 'insights'],
    ['#insightsTablist', 'aria-label', 'details'],
  ];
  for (const [selector, attribute, key] of attributes) {
    document.querySelector(selector).setAttribute(attribute, tr(key));
  }
  glossaryInput.placeholder = STARTER_GLOSSARY[currentSourceLang].split('\n').slice(0, 2).join('\n');
  for (const option of modelSelect.options) {
    const index = MODEL_IDS.indexOf(option.value);
    option.textContent = index < 0 ? option.value : `${option.value} — ${MODEL_DESCRIPTIONS[currentSourceLang][index]}`;
  }
  document.querySelector('#btnLang_sme .tag-vask').textContent = tr('proofread');
  document.getElementById('btnLang_sme').title = tr('proofread');
  document.querySelectorAll('.guideline-item').forEach((item, index) => {
    item.querySelector('.guideline-head').textContent = tr(`guide${index + 1}title`);
    item.querySelector('p:not(.guideline-head)').textContent = tr(`guide${index + 1}`);
  });
}

function updateRawLabels(sourceLang) {
  const isSami = sourceLang === 'sme';
  document.getElementById('tabBtnTartuLabel').textContent = isSami
    ? tr('originalText') : `${tr('rawDraft')} (TartuNLP ${sourceLang}→sme)`;
  document.getElementById('rawTabCaption').textContent = tr(isSami ? 'originalCaption' : 'rawCaption');
  if (lastResult?.step1_raw_translations?.[currentSourceLang]) {
    document.getElementById('tartuRawBox').textContent = lastResult.step1_raw_translations[currentSourceLang];
    document.getElementById('tartuRawBox').lang = LANG_UI[currentSourceLang].htmlLang;
  } else {
    document.getElementById('tartuRawBox').lang = 'se';
  }
}

// --- Focusgroup & Scrollability Progressive Enhancement (per modern-web-guidance: tabs) ---
async function initTabsEnhancements() {
  let polyfillLoaded = false;
  if (!Object.hasOwn(HTMLElement.prototype, 'focusGroup')) {
    try {
      const { polyfill } = await import('https://esm.sh/@microsoft/focusgroup-polyfill');
      if (typeof polyfill === 'function') {
        polyfill();
        polyfillLoaded = true;
      }
    } catch {
      // Offline / LAN fallback: simple Left/Right/Home/End keyboard roving for tablist
      polyfillLoaded = false;
    }
  } else {
    polyfillLoaded = true;
  }

  const tablist = document.getElementById('insightsTablist');
  if (!tablist) return;
  const tabs = Array.from(tablist.querySelectorAll('.tab-btn'));

  if (!polyfillLoaded) {
    tablist.setAttribute('role', 'tablist');
    tabs.forEach((btn, idx) => {
      btn.setAttribute('role', 'tab');
      btn.tabIndex = idx === 0 ? 0 : -1;
    });
    tablist.addEventListener('keydown', (e) => {
      const idx = tabs.indexOf(document.activeElement);
      if (idx === -1) return;
      let nextIdx = -1;
      if (e.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') nextIdx = 0;
      else if (e.key === 'End') nextIdx = tabs.length - 1;
      if (nextIdx !== -1) {
        e.preventDefault();
        tabs[nextIdx].focus();
      }
    });
  }

  tabs.forEach((btn) => {
    const tabKey = btn.dataset.tab;
    btn.addEventListener('click', () => switchTab(tabKey));
    btn.addEventListener('focus', () => switchTab(tabKey));
  });

  // Sync tab state when browser Find-in-Page reveals a hidden="until-found" panel
  document.querySelectorAll('[role="tabpanel"]').forEach((panel) => {
    panel.addEventListener('beforematch', () => {
      const tabKey = panel.dataset.panel;
      if (tabKey) switchTab(tabKey);
    });
  });

  // Fallback for scroll-driven edge fades when animation-timeline: scroll() is unsupported
  if (!CSS.supports('animation-timeline', 'scroll()') && tabs.length >= 2) {
    const first = tabs[0];
    const last = tabs[tabs.length - 1];
    const observer = new IntersectionObserver(
      (entries) => {
        for (const { target, intersectionRatio } of entries) {
          tablist.classList.toggle(target === first ? 'more-start' : 'more-end', intersectionRatio < 1);
        }
      },
      { root: tablist, threshold: 1, rootMargin: '1px' }
    );
    observer.observe(first);
    observer.observe(last);
  }
}

// --- Copy Button with Invoker Commands + Accessible Status Bubble (per modern-web-guidance: copy-button) ---
const copyTimers = new WeakMap();
let lastCopyMessage = '';

function legacyCopy(text) {
  const field = Object.assign(document.createElement('textarea'), { value: text });
  field.setAttribute('readonly', '');
  field.style.cssText = 'position:fixed;inset-block-start:0;opacity:0';
  document.body.append(field);
  field.select();
  try {
    return document.execCommand('copy');
  } finally {
    field.remove();
  }
}

function reportCopy(button, ok) {
  const tip = button.nextElementSibling;
  clearTimeout(copyTimers.get(button));
  button.removeAttribute('data-copied');
  button.removeAttribute('data-failed');

  let message = tr(ok ? 'copyOk' : 'copyFail');
  if (message === lastCopyMessage) message += '\u00A0';
  lastCopyMessage = message;

  if (tip) tip.textContent = '';
  void button.offsetWidth;
  button.setAttribute(ok ? 'data-copied' : 'data-failed', '');
  if (tip) {
    requestAnimationFrame(() => {
      tip.textContent = message;
    });
  }
  setStatus(ok ? 'copyOkStatus' : 'copyFailStatus');

  copyTimers.set(
    button,
    setTimeout(() => {
      button.removeAttribute('data-copied');
      button.removeAttribute('data-failed');
      if (tip) tip.textContent = '';
    }, 2000)
  );
}

async function performCopy(button, target) {
  if (!target) return;
  const text = target.matches('input, textarea') ? target.value : target.innerText.trim();
  if (!text) return;
  try {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      if (!legacyCopy(text)) throw new Error('Copy failed');
    }
    reportCopy(button, true);
  } catch {
    reportCopy(button, false);
  }
}

if ('CommandEvent' in window) {
  document.addEventListener(
    'command',
    (event) => {
      if (event.command && event.command.startsWith('--copy')) {
        performCopy(event.source, event.target);
      }
    },
    true
  );
} else {
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button[command^="--copy"]');
    if (!button) return;
    const target = document.getElementById(button.getAttribute('commandfor'));
    if (target) performCopy(button, target);
  });
}

// --- Language & Settings State ---
function setSourceLang(lang, persist = true) {
  const cfg = LANG_UI[lang] ? LANG_UI[lang] : LANG_UI.nor;
  currentSourceLang = LANG_UI[lang] ? lang : 'nor';

  if (persist) {
    localStorage.setItem(STORAGE_KEYS.lang, currentSourceLang);
  }

  Object.keys(LANG_UI).forEach((l) => {
    const btn = document.getElementById('btnLang_' + l);
    if (btn) {
      btn.setAttribute('aria-pressed', String(l === currentSourceLang));
    }
  });

  document.title = cfg.docTitle;
  document.documentElement.lang = cfg.htmlLang;
  translateStaticUI();
  if (headerSubtitle) headerSubtitle.textContent = cfg.subtitle;
  sourceEl.lang = cfg.htmlLang;
  sourceEl.placeholder = cfg.sourcePlaceholder;
  targetEl.placeholder = TARGET_PLACEHOLDERS[currentSourceLang];

  const translateBtnLabel = document.getElementById('translateBtnLabel');
  if (translateBtnLabel && !activeAbortController) {
    translateBtnLabel.textContent = tr(lang === 'sme' ? 'proofread' : 'translate');
  } else if (translateBtnLabel) {
    translateBtnLabel.textContent = tr(lang === 'sme' ? 'proofreadRunning' : 'translateRunning');
  }

  const targetHeaderLabel = document.getElementById('targetHeaderLabel');
  if (targetHeaderLabel) targetHeaderLabel.textContent = lang === 'sme' ? tr('targetWashed') : TARGET_LABELS[currentSourceLang];

  updateRawLabels(lastResult?.source_lang || currentSourceLang);

  const stepPill1 = document.getElementById('stepPill1');
  if (stepPill1) stepPill1.textContent = lang === 'sme' ? tr('preparation') : `1. TartuNLP (${lang})`;
  updateCounts();
  setTargetViewMode(isTargetEditMode);
  if (!document.getElementById('pipelineDetails').hidden) {
    renderErrors(lastErrors);
    const editMode = isTargetEditMode;
    renderTargetInteractiveView(targetEl.value, lastErrors);
    setTargetViewMode(editMode);
    renderTips(lastImprovements, lastTips);
    renderDiff(lastDiffBaselineText, targetEl.value);
    if (lastResult) {
      document.getElementById('usedModelLabel').textContent = lastResult.used_model
        ? `${tr('modelLabel')} ${lastResult.used_model}` : '';
      badgeEl.textContent = lastResult.llm_active
        ? `${lastResult.source_lang === 'sme' ? `${tr('washed')} ` : ''}${lastResult.used_model} + Divvun`
        : lastResult.source_lang === 'sme' ? tr('onlyDivvun') : 'TartuNLP + Divvun';
    }
  }
  if (lastStatus) setStatus(lastStatus.key, lastStatus.params, lastStatus.suffix);
  if (lastProgress?.translations) {
    const translated = lastProgress.translations[currentSourceLang];
    updateProgressUI(lastProgress.step, lastProgress.percent, translated.title, translated.detail);
    if (activeAbortController) statusText.textContent = translated.title;
  } else if (lastEndProgress) {
    updateProgressUI(
      lastEndProgress.step, lastEndProgress.percent,
      tr(lastEndProgress.title, lastEndProgress.params),
      lastEndProgress.detailKey ? tr(lastEndProgress.detailKey) : lastEndProgress.detail,
      lastEndProgress.state,
    );
  }
}

function toggleSettings() {
  const panel = document.getElementById('settingsPanel');
  const btn = document.getElementById('toggleSettingsBtn');
  const willShow = panel.hidden;
  panel.hidden = !willShow;
  btn.setAttribute('aria-expanded', String(willShow));
}

function countWords(str) {
  const trimmed = str.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

function updateCounts() {
  const sVal = sourceEl.value;
  const sWords = countWords(sVal);
  document.getElementById('charCount').textContent = `${sWords} ${tr('words')} \u2022 ${sVal.length} ${tr('chars')}`;
  clearBtn.hidden = sVal.length === 0;

  const tVal = targetEl.value;
  const tWords = countWords(tVal);
  targetCount.textContent = `${tWords} ${tr('words')} \u2022 ${tVal.length} ${tr('chars')}`;
}

function clearSource() {
  sourceEl.value = '';
  updateCounts();
  sourceEl.focus();
}

function loadExample() {
  const cfg = LANG_UI[currentSourceLang] || LANG_UI.nor;
  sourceEl.value = cfg.example;
  updateCounts();
  sourceEl.focus();
}

function insertStarterGlossary() {
  const existing = glossaryInput.value.trim();
  const starter = STARTER_GLOSSARY[currentSourceLang];
  glossaryInput.value = existing ? `${existing}\n${starter}` : starter;
  localStorage.setItem(STORAGE_KEYS.glossary, glossaryInput.value);
}

// --- Sámi Special Character Insertion & Sátni.org Quick Lookup ---
function insertSamiChar(ch) {
  const editor = lastFocusedEditor === targetEl ? targetEl : sourceEl;
  const start = editor.selectionStart ?? editor.value.length;
  const end = editor.selectionEnd ?? editor.value.length;
  editor.setRangeText(ch, start, end, 'end');
  editor.focus();
  updateCounts();
  if (editor === targetEl && lastDiffBaselineText) {
    renderDiff(lastDiffBaselineText, targetEl.value);
  }
}

function getSelectedEditorWord() {
  for (const el of [targetEl, sourceEl]) {
    if (el.selectionStart !== el.selectionEnd) {
      const sel = el.value.slice(el.selectionStart, el.selectionEnd).trim();
      if (sel && sel.length <= 80) return sel;
    }
  }
  return '';
}

function openSatniLookup() {
  const term = satniInput.value.trim() || getSelectedEditorWord();
  const url = term
    ? `https://satni.org/${encodeURIComponent(term)}`
    : 'https://satni.org';
  window.open(url, '_blank', 'noopener,noreferrer');
}

// --- Tabs Switching ---
function switchTab(tabKey) {
  const tablist = document.getElementById('insightsTablist');
  if (!tablist) return;
  const tabs = Array.from(tablist.querySelectorAll('.tab-btn'));

  for (const tab of tabs) {
    const isSelected = tab.dataset.tab === tabKey;
    tab.setAttribute('aria-selected', String(isSelected));
    tab.toggleAttribute('focusgroupstart', isSelected);
    if (tab.hasAttribute('role')) {
      tab.tabIndex = isSelected ? 0 : -1;
    }
    if (isSelected) {
      try {
        tab.scrollIntoView({ block: 'nearest', inline: 'nearest', container: 'nearest' });
      } catch {
        tab.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
    }
  }

  document.querySelectorAll('[role="tabpanel"]').forEach((panel) => {
    const isSelected = panel.dataset.panel === tabKey;
    if (isSelected) {
      panel.hidden = false;
      const hasFocusable = panel.querySelector('button, a, input, textarea, select, [tabindex]');
      if (hasFocusable) {
        panel.removeAttribute('tabindex');
      } else {
        panel.tabIndex = 0;
      }
    } else {
      panel.hidden = 'until-found';
      panel.removeAttribute('tabindex');
    }
  });
}

// --- Model Loading (API key sent via header, NEVER in URL query string) ---
function populateModelOptions(models, preferredId) {
  modelSelect.replaceChildren();
  for (const m of models) {
    const opt = document.createElement('option');
    opt.value = m.id;
    const index = MODEL_IDS.indexOf(m.id);
    opt.textContent = index < 0 ? m.id : `${m.id} — ${MODEL_DESCRIPTIONS[currentSourceLang][index]}`;
    modelSelect.appendChild(opt);
  }
  const ids = models.map((m) => m.id);
  if (preferredId && ids.includes(preferredId)) {
    modelSelect.value = preferredId;
  } else if (ids.includes('gemini-4-hydrogen')) {
    modelSelect.value = 'gemini-4-hydrogen';
  }
  headerModelLabel.textContent = modelSelect.value;
  headerModelBadge.classList.add('is-ready');
}

async function loadAvailableModels() {
  const key = keyInput.value.trim();
  const headers = {};
  if (key) {
    headers['X-Gemini-Api-Key'] = key;
  }

  try {
    const resp = await fetch('/api/config', { headers });
    if (!resp.ok) return;
    const cfg = await resp.json();

    if (cfg.has_env_key) {
      keyInput.dataset.envKey = 'true';
      keyInput.placeholder = tr('keyEnv');
    }

    const savedModel = localStorage.getItem(STORAGE_KEYS.model);
    const models =
      cfg.available_models && cfg.available_models.length > 0
        ? cfg.available_models
        : cfg.default_models || [];

    if (models.length > 0) {
      populateModelOptions(models, savedModel || cfg.env_model || 'gemini-4-hydrogen');
      setStatus('ready', {}, ` (${modelSelect.value})`);
    }
  } catch (err) {
    console.warn('Kunne ikke hente konfigurasjon:', err);
  }
}

// --- Progress UI ---
function updateProgressUI(step, percent, title, detail, state = 'running') {
  const container = document.getElementById('progressContainer');
  const bar = document.getElementById('progressBar');
  const titleEl = document.getElementById('progressTitle');
  const detailEl = document.getElementById('progressDetail');
  const pctEl = document.getElementById('progressPercent');
  const spinner = document.getElementById('progressSpinner');

  container.hidden = false;
  bar.value = percent;
  pctEl.textContent = `${percent}%`;
  if (title) titleEl.textContent = title;
  if (detail !== undefined) detailEl.textContent = detail;

  bar.classList.toggle('is-done', state === 'done');
  bar.classList.toggle('is-error', state === 'error');
  spinner.hidden = state !== 'running';
  cancelBtn.hidden = state !== 'running';

  for (let i = 1; i <= 4; i++) {
    const pill = document.getElementById(`stepPill${i}`);
    if (!pill) continue;
    pill.classList.remove('is-done', 'is-active');
    if (state === 'done' || (state === 'running' && i < step)) {
      pill.classList.add('is-done');
    } else if (state === 'running' && i === step) {
      pill.classList.add('is-active');
    }
  }
}

// --- Position-Safe Divvun Suggestion Application ---
function applyDivvunSuggestion(errObj, replacement) {
  const current = targetEl.value;
  const errWord = errObj.error_text || '';
  const start = errObj.start_index;
  const end = errObj.end_index;

  if (
    typeof start === 'number' &&
    typeof end === 'number' &&
    start >= 0 &&
    end <= current.length &&
    (!errWord || current.slice(start, end) === errWord)
  ) {
    targetEl.value = current.slice(0, start) + replacement + current.slice(end);
  } else if (errWord) {
    // Fallback dersom brukeren har redigert teksten før de trykket på knappen: finn nærmeste treff til start_index
    const anchor = typeof start === 'number' ? start : 0;
    let bestIdx = -1;
    let bestDist = Infinity;
    let searchFrom = 0;
    while (searchFrom <= current.length) {
      const idx = current.indexOf(errWord, searchFrom);
      if (idx === -1) break;
      const dist = Math.abs(idx - anchor);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = idx;
      }
      searchFrom = idx + 1;
    }
    if (bestIdx !== -1) {
      targetEl.value =
        current.slice(0, bestIdx) + replacement + current.slice(bestIdx + errWord.length);
    }
  }

  updateCounts();
  if (lastDiffBaselineText) {
    renderDiff(lastDiffBaselineText, targetEl.value);
  }
  recheckDivvun();
}

// --- XSS-Safe Rendering of Errors, Tips & Word-Level Diff ---
function renderErrors(errs) {
  lastErrors = Array.isArray(errs) ? errs : [];
  const box = document.getElementById('divvunErrorsBox');
  const badgeCount = document.getElementById('badgeDivvunCount');
  const list = Array.isArray(errs) ? errs : [];
  badgeCount.textContent = String(list.length);
  box.replaceChildren();

  badgeCount.classList.remove('is-emerald', 'is-amber');
  if (divvunCheckIncomplete) {
    const warning = document.createElement('div');
    warning.className = 'note-card is-divvun';
    warning.textContent = tr('checkIncomplete');
    box.appendChild(warning);
  }
  if (list.length === 0) {
    badgeCount.classList.add(divvunCheckIncomplete ? 'is-amber' : 'is-emerald');
    if (divvunCheckIncomplete) return;
    const okEl = document.createElement('div');
    okEl.className = 'note-card is-ok';
    okEl.textContent = tr('noErrors');
    box.appendChild(okEl);
    return;
  }

  badgeCount.classList.add('is-amber');
  for (const e of list) {
    const translated = e.translations?.[currentSourceLang] || e;
    const card = document.createElement('div');
    card.className = 'note-card is-divvun';

    const title = document.createElement('div');
    title.className = 'note-title';
    title.textContent = `”${e.error_text || ''}” — ${translated.title || e.error_code || tr('note')}`;
    card.appendChild(title);

    if (translated.description) {
      const desc = document.createElement('div');
      desc.textContent = translated.description;
      card.appendChild(desc);
    }

    const suggestions = Array.isArray(e.suggestions) ? e.suggestions : [];
    if (suggestions.length > 0) {
      const row = document.createElement('div');
      row.className = 'sugg-row';
      for (const s of suggestions) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'sugg-btn';
        btn.textContent = s;
        btn.addEventListener('click', () => applyDivvunSuggestion(e, s));
        row.appendChild(btn);
      }
      card.appendChild(row);
    }

    box.appendChild(card);
  }
}

// --- Interactive Red-Underlined Spellcheck View & Popover Dropdown ---
function closeSpellPopover() {
  if (!spellPopoverEl) return;
  try {
    if (spellPopoverEl.matches(':popover-open') || spellPopoverEl.classList.contains(':popover-open')) {
      spellPopoverEl.hidePopover();
    }
  } catch {
    spellPopoverEl.removeAttribute('open');
  }
}

function positionPopoverFallback(triggerBtn) {
  if (CSS.supports('position-area: block-end')) {
    spellPopoverEl.style.left = '';
    spellPopoverEl.style.top = '';
    return;
  }
  const rect = triggerBtn.getBoundingClientRect();
  const popRect = spellPopoverEl.getBoundingClientRect();
  const margin = 8;
  let left = rect.left;
  let top = rect.bottom + 6;
  if (left + popRect.width > window.innerWidth - margin) {
    left = Math.max(margin, window.innerWidth - popRect.width - margin);
  }
  if (top + popRect.height > window.innerHeight - margin) {
    top = Math.max(margin, rect.top - popRect.height - 6);
  }
  spellPopoverEl.style.left = `${Math.max(margin, left)}px`;
  spellPopoverEl.style.top = `${Math.max(margin, top)}px`;
}

function openSpellPopover(triggerBtn, errObj) {
  if (!spellPopoverEl) return;
  spellPopoverEl.replaceChildren();

  const head = document.createElement('div');
  head.className = 'spell-popover-head';

  const wordEl = document.createElement('div');
  wordEl.className = 'spell-popover-word';
  wordEl.textContent = errObj.error_text || '';
  head.appendChild(wordEl);

  const metaEl = document.createElement('div');
  metaEl.className = 'spell-popover-meta';
  const translated = errObj.translations?.[currentSourceLang] || errObj;
  metaEl.textContent = [translated.title, translated.description].filter(Boolean).join(' – ');
  if (metaEl.textContent) head.appendChild(metaEl);

  spellPopoverEl.appendChild(head);

  const suggestions = Array.isArray(errObj.suggestions) ? errObj.suggestions : [];
  if (suggestions.length > 0) {
    const list = document.createElement('div');
    list.className = 'spell-popover-list';
    for (const s of suggestions) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'spell-sugg-btn';
      btn.textContent = s;
      btn.addEventListener('click', () => {
        closeSpellPopover();
        applyDivvunSuggestion(errObj, s);
      });
      list.appendChild(btn);
    }
    spellPopoverEl.appendChild(list);
  } else {
    const empty = document.createElement('div');
    empty.className = 'spell-popover-empty';
    empty.textContent = tr('noSuggestions');
    spellPopoverEl.appendChild(empty);
  }

  const actions = document.createElement('div');
  actions.className = 'spell-popover-actions';

  const editBtn = document.createElement('button');
  editBtn.type = 'button';
  editBtn.className = 'spell-action-btn';
  editBtn.textContent = tr('editManually');
  editBtn.addEventListener('click', () => {
    closeSpellPopover();
    setTargetViewMode(true);
    targetEl.focus();
    if (typeof errObj.start_index === 'number' && typeof errObj.end_index === 'number') {
      targetEl.setSelectionRange(errObj.start_index, errObj.end_index);
    }
  });
  actions.appendChild(editBtn);

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'spell-action-btn';
  closeBtn.textContent = tr('close');
  closeBtn.addEventListener('click', closeSpellPopover);
  actions.appendChild(closeBtn);

  spellPopoverEl.appendChild(actions);

  try {
    spellPopoverEl.showPopover({ source: triggerBtn });
  } catch {
    spellPopoverEl.showPopover();
  }
  requestAnimationFrame(() => positionPopoverFallback(triggerBtn));
}

function setTargetViewMode(editMode) {
  closeSpellPopover();
  isTargetEditMode = editMode;
  const hasErrors = currentTargetErrors.length > 0 && targetEl.value.trim().length > 0;
  if (!hasErrors || editMode) {
    targetEl.hidden = false;
    targetInteractiveEl.hidden = true;
    toggleTargetViewBtn.hidden = !hasErrors;
    toggleTargetViewBtn.textContent = tr('showMarks');
  } else {
    targetEl.hidden = true;
    targetInteractiveEl.hidden = false;
    toggleTargetViewBtn.hidden = false;
    toggleTargetViewBtn.textContent = tr('editText');
  }
}

function renderTargetInteractiveView(text, errs) {
  closeSpellPopover();
  const list = Array.isArray(errs) ? errs : [];
  const validErrs = list
    .filter(
      (e) =>
        e &&
        typeof e.start_index === 'number' &&
        typeof e.end_index === 'number' &&
        e.start_index >= 0 &&
        e.end_index > e.start_index &&
        e.end_index <= text.length
    )
    .sort((a, b) => a.start_index - b.start_index);

  currentTargetErrors = validErrs;
  targetInteractiveEl.replaceChildren();

  if (validErrs.length === 0 || !text) {
    setTargetViewMode(true);
    return;
  }

  let cursor = 0;
  for (const err of validErrs) {
    if (err.start_index < cursor) continue;
    if (err.start_index > cursor) {
      targetInteractiveEl.appendChild(
        document.createTextNode(text.slice(cursor, err.start_index))
      );
    }
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'spell-mark';
    trigger.textContent = text.slice(err.start_index, err.end_index);
    trigger.title = err.translations?.[currentSourceLang]?.title || err.title || tr('clickSuggestion');
    trigger.addEventListener('click', () => openSpellPopover(trigger, err));
    targetInteractiveEl.appendChild(trigger);
    cursor = err.end_index;
  }
  if (cursor < text.length) {
    targetInteractiveEl.appendChild(document.createTextNode(text.slice(cursor)));
  }

  setTargetViewMode(false);
}

function renderTips(improvements, tips) {
  lastImprovements = improvements;
  lastTips = tips;
  const box = document.getElementById('languageTipsBox');
  const badgeCount = document.getElementById('badgeImprovementsCount');
  box.replaceChildren();

  const impList = Array.isArray(improvements) ? improvements : [];
  const tipList = Array.isArray(tips) ? tips : [];
  const totalCount = impList.length + tipList.length;
  badgeCount.textContent = String(totalCount);

  for (const imp of impList) {
    const card = document.createElement('div');
    card.className = 'note-card is-improvement';
    const strong = document.createElement('strong');
    strong.textContent = `${tr('proofreading')} `;
    card.appendChild(strong);
    card.appendChild(document.createTextNode(lastImprovementTranslations[imp]?.[currentSourceLang] || imp));
    box.appendChild(card);
  }

  for (const t of tipList) {
    const translatedTip = t.translations?.[currentSourceLang] || t;
    const card = document.createElement('div');
    card.className = 'note-card is-tip';

    const title = document.createElement('div');
    title.className = 'note-title';
    title.textContent = `${translatedTip.rule || tr('languageTip')} `;
    if (translatedTip.reference) {
      const ref = document.createElement('span');
      ref.className = 'note-ref';
      ref.textContent = `(${translatedTip.reference})`;
      title.appendChild(ref);
    }
    card.appendChild(title);

    const msg = document.createElement('div');
    msg.textContent = translatedTip.message || '';
    card.appendChild(msg);

    box.appendChild(card);
  }

  if (totalCount === 0) {
    const okEl = document.createElement('div');
    okEl.className = 'note-card is-ok';
    okEl.textContent = tr('noTips');
    box.appendChild(okEl);
  }
}

function diffTokensLCS(oldTokens, newTokens) {
  const m = oldTokens.length;
  const n = newTokens.length;
  // Hvis avsnittet er ekstremt langt, del på setninger så matrisen alltid forblir liten og lynrask
  if (m * n > 90000) {
    const ops = [];
    if (oldTokens.join('') === newTokens.join('')) {
      return [{ type: 'eq', text: oldTokens.join('') }];
    }
    if (m > 0) ops.push({ type: 'del', text: oldTokens.join('') });
    if (n > 0) ops.push({ type: 'ins', text: newTokens.join('') });
    return ops;
  }

  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldTokens[i] === newTokens[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = dp[i + 1][j] >= dp[i][j + 1] ? dp[i + 1][j] : dp[i][j + 1];
      }
    }
  }

  const ops = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (oldTokens[i] === newTokens[j]) {
      ops.push({ type: 'eq', text: oldTokens[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: 'del', text: oldTokens[i] });
      i++;
    } else {
      ops.push({ type: 'ins', text: newTokens[j] });
      j++;
    }
  }
  while (i < m) ops.push({ type: 'del', text: oldTokens[i++] });
  while (j < n) ops.push({ type: 'ins', text: newTokens[j++] });
  return ops;
}

function renderDiff(beforeText, afterText) {
  const diffBox = document.getElementById('diffBox');
  const diffCaption = document.getElementById('diffCaption');
  const badgeDiff = document.getElementById('badgeDiffCount');
  if (!diffBox) return;

  diffBox.replaceChildren();

  if (!beforeText || !afterText || beforeText.startsWith('[')) {
    badgeDiff.textContent = '0';
    diffCaption.textContent = tr('noDiff');
    diffBox.textContent = afterText || '';
    return;
  }

  diffCaption.textContent = tr((lastResult?.source_lang || currentSourceLang) === 'sme' ? 'diffSami' : 'diffTartu');

  const oldParas = beforeText.split('\n');
  const newParas = afterText.split('\n');
  const maxLen = Math.max(oldParas.length, newParas.length);
  let changeCount = 0;

  for (let p = 0; p < maxLen; p++) {
    const oLine = oldParas[p] ?? '';
    const nLine = newParas[p] ?? '';
    const oTokens = oLine ? oLine.split(/(\s+)/).filter(Boolean) : [];
    const nTokens = nLine ? nLine.split(/(\s+)/).filter(Boolean) : [];
    const ops = diffTokensLCS(oTokens, nTokens);

    for (const op of ops) {
      if (op.type === 'eq') {
        diffBox.appendChild(document.createTextNode(op.text));
      } else if (op.type === 'del') {
        if (op.text.trim()) changeCount++;
        const del = document.createElement('del');
        del.className = 'diff-del';
        del.textContent = op.text;
        diffBox.appendChild(del);
      } else if (op.type === 'ins') {
        if (op.text.trim()) changeCount++;
        const ins = document.createElement('ins');
        ins.className = 'diff-ins';
        ins.textContent = op.text;
        diffBox.appendChild(ins);
      }
    }
    if (p < maxLen - 1) {
      diffBox.appendChild(document.createTextNode('\n'));
    }
  }

  badgeDiff.textContent = String(changeCount);
}

// --- Display Pipeline Output ---
function displayFinalData(data) {
  lastResult = data;
  lastImprovementTranslations = data.improvement_translations || {};
  const finalOut = data.step3_final_text || '';
  targetEl.value = finalOut;
  updateCounts();

  const rawText = data.step1_tartu_raw || '';
  document.getElementById('tartuRawBox').textContent = rawText;
  document.getElementById('pipelineDetails').hidden = false;
  updateRawLabels(data.source_lang);

  lastDiffBaselineText = data.source_lang === 'sme' ? data.source_text || '' : rawText;
  renderDiff(lastDiffBaselineText, finalOut);

  badgeEl.hidden = false;
  badgeEl.classList.remove('is-llm', 'is-basic');
  const isSami = data.source_lang === 'sme';

  if (data.llm_active) {
    badgeEl.textContent = isSami
      ? `${tr('washed')} ${data.used_model} + Divvun`
      : `${data.used_model} + Divvun`;
    badgeEl.classList.add('is-llm');
  } else {
    badgeEl.textContent = isSami ? tr('onlyDivvun') : 'TartuNLP + Divvun';
    badgeEl.classList.add('is-basic');
  }

  document.getElementById('usedModelLabel').textContent = data.used_model ? `${tr('modelLabel')} ${data.used_model}` : '';
  if (data.used_model) {
    headerModelLabel.textContent = data.used_model;
    headerModelBadge.classList.add('is-ready');
  }

  const finalErrs = data.final_divvun_errors || [];
  divvunCheckIncomplete = Boolean(data.divvun_check_incomplete);
  renderErrors(finalErrs);
  renderTargetInteractiveView(finalOut, finalErrs);
  renderTips(data.step3_improvements || [], data.language_tips || []);

  if (data.result_incomplete || data.divvun_check_incomplete) {
    setStatus('resultIncomplete');
  } else if (data.llm_active) {
    setStatus('finishedWith', { model: data.used_model });
  } else {
    setStatus('finishedWithout');
  }

  switchTab('improvements');
}

// --- Run & Cancel Pipeline ---
function cancelTranslation() {
  if (activeAbortController) {
    activeAbortController.abort();
  }
}

async function runPipeline() {
  const text = sourceEl.value.trim();
  if (!text || activeAbortController) return;
  lastProgress = null;
  lastEndProgress = null;

  renderTargetInteractiveView('', []);
  const btn = document.getElementById('translateBtn');
  const btnLabel = document.getElementById('translateBtnLabel');
  btn.disabled = true;
  btnLabel.textContent = tr(currentSourceLang === 'sme' ? 'proofreadRunning' : 'translateRunning');

  activeAbortController = new AbortController();
  startTime = Date.now();
  const timerEl = document.getElementById('progressTimer');
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    timerEl.textContent = `${elapsed}s`;
  }, 100);

  const isSami = currentSourceLang === 'sme';
  updateProgressUI(
    1,
    5,
    tr(isSami ? 'startingProofread' : 'startingTranslation'),
    tr('sending'),
    'running'
  );

  const key = keyInput.value.trim();
  const headers = { 'Content-Type': 'application/json' };
  if (key) {
    headers['X-Gemini-Api-Key'] = key;
  }

  try {
    const resp = await fetch('/api/translate-stream', {
      method: 'POST',
      headers,
      signal: activeAbortController.signal,
      body: JSON.stringify({
        text,
        source_lang: currentSourceLang,
        use_llm: useLlmCheckbox.checked,
        auto_apply_divvun: autoDivvunCheckbox.checked,
        model: modelSelect.value,
        thinking_level: thinkingSelect.value,
        glossary: glossaryInput.value.trim() || null,
      }),
    });

    if (!resp.ok) {
      let errDetail = `HTTP ${resp.status}`;
      try {
        const errJson = await resp.json();
        if (errJson.detail) {
          if (typeof errJson.detail === 'string') {
            errDetail = errJson.detail;
          } else if (Array.isArray(errJson.detail)) {
            const tooLong = errJson.detail.some(
              (error) => error.type === 'string_too_long' && error.loc?.includes('text')
            );
            errDetail = tr(tooLong ? 'inputTooLong' : 'invalidRequest');
          } else {
            errDetail = tr('invalidRequest');
          }
        }
      } catch {
        // behold HTTP-status
      }
      throw new Error(errDetail);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let receivedResult = false;

    const handleLine = (line) => {
      if (!line.trim()) return;
      const msg = JSON.parse(line);
      if (msg.type === 'progress') {
        lastProgress = msg;
        const translated = msg.translations?.[currentSourceLang] || msg;
        updateProgressUI(msg.step, msg.percent, translated.title, translated.detail, 'running');
        lastStatus = null;
        statusText.textContent = translated.title;
      } else if (msg.type === 'result') {
        lastProgress = null;
        receivedResult = true;
        const totalSec = ((Date.now() - startTime) / 1000).toFixed(1);
        const incomplete = msg.data.result_incomplete || msg.data.divvun_check_incomplete;
        lastEndProgress = incomplete
          ? { step: 4, percent: 100, title: 'resultIncomplete', detailKey: 'resultIncomplete', state: 'error' }
          : { step: 4, percent: 100, title: 'doneIn', params: { seconds: totalSec }, detailKey: 'allDone', state: 'done' };
        updateProgressUI(4, 100, tr(lastEndProgress.title, lastEndProgress.params), tr(lastEndProgress.detailKey), lastEndProgress.state);
        displayFinalData(msg.data);
      } else if (msg.type === 'error') {
        throw new Error(msg.message || tr('streamError'));
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        handleLine(line);
      }
    }
    if (buffer.trim()) {
      handleLine(buffer);
    }
    if (!receivedResult) {
      throw new Error(tr('connectionClosed'));
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      lastEndProgress = { step: 1, percent: 0, title: 'cancelled', detailKey: 'cancelDetail', state: 'error' };
      setStatus('cancelled');
      updateProgressUI(1, 0, tr('cancelled'), tr('cancelDetail'), 'error');
    } else {
      lastEndProgress = { step: 1, percent: 100, title: 'runError', detail: err.message, state: 'error' };
      setStatus('error', {}, ` ${err.message}`);
      updateProgressUI(1, 100, tr('runError'), err.message, 'error');
    }
  } finally {
    if (timerInterval) clearInterval(timerInterval);
    activeAbortController = null;
    lastProgress = null;
    btn.disabled = false;
    btnLabel.textContent = tr(currentSourceLang === 'sme' ? 'proofread' : 'translate');
  }
}

async function recheckDivvun() {
  const text = targetEl.value.trim();
  if (!text) return;
  setStatus('checkingDivvun');
  try {
    const resp = await fetch('/api/proofread', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, source_lang: currentSourceLang }),
    });
    if (!resp.ok) {
      if (resp.status === 422) {
        const body = await resp.json();
        const tooLong = Array.isArray(body.detail) && body.detail.some(
          (error) => error.type === 'string_too_long' && error.loc?.includes('text')
        );
        setStatus(tooLong ? 'inputTooLong' : 'invalidRequest');
        return;
      }
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();
    document.getElementById('pipelineDetails').hidden = false;
    const errs = data.errs || [];
    divvunCheckIncomplete = Boolean(data.divvun_check_incomplete);
    renderErrors(errs);
    renderTargetInteractiveView(targetEl.value, errs);
    lastImprovementTranslations = data.improvement_translations || {};
    renderTips(data.warnings || [], data.language_tips || []);
    if (lastDiffBaselineText) {
      renderDiff(lastDiffBaselineText, targetEl.value);
    }
    switchTab('divvun');
    if (divvunCheckIncomplete) {
      setStatus('checkIncomplete');
    } else {
      setStatus('divvunDone', { count: (data.errs || []).length });
    }
  } catch {
    setStatus('divvunError');
  }
}

// --- Wire Up Events & Restore Persisted Settings ---
function initApp() {
  if (localStorage.getItem(STORAGE_KEYS.apiKey)) {
    keyInput.value = localStorage.getItem(STORAGE_KEYS.apiKey);
  }
  if (localStorage.getItem(STORAGE_KEYS.thinking)) {
    thinkingSelect.value = localStorage.getItem(STORAGE_KEYS.thinking);
  }
  if (localStorage.getItem(STORAGE_KEYS.autoDivvun) !== null) {
    autoDivvunCheckbox.checked = localStorage.getItem(STORAGE_KEYS.autoDivvun) === 'true';
  }
  if (localStorage.getItem(STORAGE_KEYS.useLlm) !== null) {
    useLlmCheckbox.checked = localStorage.getItem(STORAGE_KEYS.useLlm) === 'true';
  }
  if (localStorage.getItem(STORAGE_KEYS.glossary)) {
    glossaryInput.value = localStorage.getItem(STORAGE_KEYS.glossary);
  }

  const savedLang = localStorage.getItem(STORAGE_KEYS.lang) || 'nor';
  setSourceLang(savedLang, false);

  keyInput.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEYS.apiKey, keyInput.value.trim());
    loadAvailableModels();
  });

  modelSelect.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEYS.model, modelSelect.value);
    headerModelLabel.textContent = modelSelect.value;
  });

  thinkingSelect.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEYS.thinking, thinkingSelect.value);
  });

  autoDivvunCheckbox.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEYS.autoDivvun, String(autoDivvunCheckbox.checked));
  });

  useLlmCheckbox.addEventListener('change', () => {
    localStorage.setItem(STORAGE_KEYS.useLlm, String(useLlmCheckbox.checked));
  });

  glossaryInput.addEventListener('input', () => {
    localStorage.setItem(STORAGE_KEYS.glossary, glossaryInput.value);
  });

  sourceEl.addEventListener('focus', () => {
    lastFocusedEditor = sourceEl;
  });
  targetEl.addEventListener('focus', () => {
    lastFocusedEditor = targetEl;
  });

  sourceEl.addEventListener('input', updateCounts);
  targetEl.addEventListener('input', () => {
    updateCounts();
    if (lastDiffBaselineText) {
      renderDiff(lastDiffBaselineText, targetEl.value);
    }
  });

  sourceEl.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      runPipeline();
    }
  });

  // IME-safe Enter handler on Sátni.org quick lookup input (per modern-web-guidance: ime-safe-enter-submit)
  satniInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      if (event.isComposing || event.keyCode === 229) {
        return;
      }
      openSatniLookup();
    }
  });

  document.getElementById('satniLookupBtn').addEventListener('click', openSatniLookup);
  document.getElementById('toggleSettingsBtn').addEventListener('click', toggleSettings);
  document.getElementById('refreshModelsBtn').addEventListener('click', loadAvailableModels);
  document.getElementById('starterGlossaryBtn').addEventListener('click', insertStarterGlossary);
  document.getElementById('exampleBtn').addEventListener('click', loadExample);
  clearBtn.addEventListener('click', clearSource);
  document.getElementById('translateBtn').addEventListener('click', runPipeline);
  document.getElementById('recheckDivvunBtn').addEventListener('click', recheckDivvun);
  toggleTargetViewBtn.addEventListener('click', () => setTargetViewMode(!isTargetEditMode));
  targetInteractiveEl.addEventListener('dblclick', (event) => {
    if (!event.target.closest('.spell-mark')) {
      setTargetViewMode(true);
      targetEl.focus();
    }
  });
  cancelBtn.addEventListener('click', cancelTranslation);

  if (!Object.hasOwn(HTMLElement.prototype, 'popover')) {
    import('https://unpkg.com/@oddbird/popover-polyfill@latest/dist/popover.min.js').catch(() => {});
  }

  Object.keys(LANG_UI).forEach((lang) => {
    const btn = document.getElementById('btnLang_' + lang);
    if (btn) btn.addEventListener('click', () => setSourceLang(lang));
  });

  document.querySelectorAll('.char-btn').forEach((btn) => {
    btn.addEventListener('mousedown', (e) => e.preventDefault());
    btn.addEventListener('click', () => insertSamiChar(btn.dataset.char));
  });

  updateCounts();
  initTabsEnhancements();
  loadAvailableModels();
}

initApp();
