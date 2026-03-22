// ===== LEXI SPIRIT EVOLUTION SYSTEM =====
// Voodoo Mini App — Full product

const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); tg.setHeaderColor('#0d0d11'); tg.setBackgroundColor('#0d0d11'); }

// ===== AUDIO / TTS =====
var _synth = window.speechSynthesis;
var _ttsQueue = [];
var _ttsBusy = false;

function speakText(text, lang) {
  lang = lang || 'en-US';
  if (!_synth) return;
  _synth.cancel();
  var u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = lang.startsWith('en') ? 0.85 : 1.0;
  u.pitch = 1;
  // Prefer a native English voice
  var voices = _synth.getVoices();
  var best = voices.find(function(v) { return v.lang === lang && v.localService; })
           || voices.find(function(v) { return v.lang.startsWith(lang.split('-')[0]); });
  if (best) u.voice = best;
  _synth.speak(u);
  haptic('light');
}

function speakWord(word) { speakText(word, 'en-US'); }
function speakSentence(sentence) { speakText(sentence, 'en-US'); }
function speakUa(text) { speakText(text, 'uk-UA'); }

function audioBtn(text, label, lang) {
  lang = lang || 'en-US';
  var escaped = text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
  return '<button class="audio-btn" onclick="speakText(\'' + escaped + '\',\'' + lang + '\')" title="Послухати">' +
    '🔊 ' + (label || '') + '</button>';
}

// ===== HAPTIC FEEDBACK HELPER =====
function haptic(style) {
  try {
    var tgH = window.Telegram && window.Telegram.WebApp;
    if (tgH && tgH.HapticFeedback) {
      if (style === 'light' || style === 'medium' || style === 'heavy' || style === 'rigid' || style === 'soft') {
        tgH.HapticFeedback.impactOccurred(style);
      } else if (style === 'success' || style === 'warning' || style === 'error') {
        tgH.HapticFeedback.notificationOccurred(style);
      } else {
        tgH.HapticFeedback.selectionChanged();
      }
    }
  } catch(e) {}
}

const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  ? 'http://localhost:8000'
  : 'https://your-domain.com';

// ===== ADSGRAM REWARDED VIDEO =====
// blockId: register at https://adsgram.ai to get your block ID
const ADSGRAM_BLOCK_ID = 'YOUR_ADSGRAM_BLOCK_ID';
let adsgramController = null;

async function initAdsgram() {
  try {
    if (window.Adsgram && ADSGRAM_BLOCK_ID !== 'YOUR_ADSGRAM_BLOCK_ID') {
      adsgramController = window.Adsgram.init({ blockId: ADSGRAM_BLOCK_ID });
    }
  } catch (e) { /* AdsGram not loaded yet */ }
}

async function watchRewardedAd() {
  const btn = document.getElementById('adRewardBtn');
  // Check daily limit via localStorage
  const today = new Date().toISOString().slice(0, 10);
  const lastAdDay = localStorage.getItem('lastAdDay');
  if (lastAdDay === today) {
    showToast('Реклама вже переглянута сьогодні ✅', 'success');
    return;
  }
  if (!adsgramController) {
    await initAdsgram();
    if (!adsgramController) {
      showToast('Реклама недоступна зараз', 'error');
      return;
    }
  }
  if (btn) btn.disabled = true;
  try {
    await adsgramController.show();
    // Ad watched successfully — reward +15 XP
    localStorage.setItem('lastAdDay', today);
    const tgId = state.user?.tg_id;
    if (tgId) {
      await apiCall('/api/progress', {
        method: 'POST',
        body: JSON.stringify({ tg_id: tgId, xp_earned: 15, hp_change: 0, lesson_done: false }),
      }, null);
      state.xp = (state.xp || 0) + 15;
    }
    haptic('success');
    showToast('+15 XP за перегляд реклами! 📺', 'success');
    if (btn) { btn.textContent = '✅ Переглянуто сьогодні'; btn.disabled = true; }
  } catch (e) {
    // User skipped or error
    if (btn) btn.disabled = false;
    if (e && e.done === false) showToast('Реклама пропущена', 'error');
  }
}

// ===== PET ARCHETYPES =====
const PET_ARCHETYPES = {
  spirit: {
    name: 'Spirit', icon: '✨', desc: 'Магічний дух слів',
    stageEmojis: ['🥚', '🌱', '🌟', '🦋', '🔮', '⚡'],
  },
  beast: {
    name: 'Beast', icon: '🦊', desc: 'Дикий звірок',
    stageEmojis: ['🥚', '🐣', '🐱', '🦊', '🐺', '🐉'],
  },
  buddy: {
    name: 'Buddy', icon: '🤖', desc: 'Цифровий друг',
    stageEmojis: ['🥚', '🤖', '⚙️', '🦾', '🧬', '💫'],
  },
};

// ===== REACTION POOLS (20+ per archetype) =====
// Each entry: { w: weight, sp: speech[], fx: effect_type, args: [] }
// Higher weight = more common. rare=1-2, uncommon=3-5, common=7-10

const REACTION_POOLS = {
  spirit: [
    {w:10, sp:['😊','~hm~','✨'],              fx:'ring',      args:[55,'rgba(124,110,245,',2]},
    {w:10, sp:['...','~float~','☁️'],          fx:'bounce',    args:[1.07,0,0]},
    {w:10, sp:['👀','!','...'],                 fx:'blink',     args:[]},
    {w:10, sp:['✦','~glow~','💜'],             fx:'aura',      args:['#7c6ef5']},
    {w:9,  sp:['✦ ✧ ✦','*~*','⭐'],           fx:'particles', args:['#a89cff',7,0,360,35]},
    {w:9,  sp:['?','Hmm...','👀'],              fx:'tilt',      args:[8]},
    {w:8,  sp:['!','Ей!','boing'],              fx:'bounce',    args:[1.18,5,0]},
    {w:8,  sp:['?!','Цікаво!','~'],             fx:'tilt',      args:[-10]},
    {w:7,  sp:['~Ой~','✨','whirl'],           fx:'spin',      args:[360]},
    {w:6,  sp:['!','Бум!','💥'],               fx:'ring',      args:[70,'rgba(124,110,245,',3]},
    {w:5,  sp:['📖','word!','✨'],              fx:'word_orbit',args:[]},
    {w:5,  sp:['+XP ✨','grows!','💪'],         fx:'xp_pulse',  args:[]},
    {w:5,  sp:['❤️','~love~','💜'],            fx:'heart',     args:[]},
    {w:5,  sp:['♪~♪','~happy~','✓'],          fx:'spin',      args:[720]},
    {w:4,  sp:['BOOM!','💥','✦'],              fx:'letters',   args:[]},
    {w:4,  sp:['🎉','yay!','✨'],               fx:'confetti',  args:[]},
    {w:4,  sp:['📚','topic!','~'],              fx:'topic',     args:[]},
    {w:3,  sp:['~curious~','тихо...','🌙'],    fx:'tilt',      args:[5]},
    {w:3,  sp:['~sleepy~','zzz','😴'],         fx:'bounce',    args:[1.03,2,3]},
    {w:2,  sp:['"break a leg"','✦ rune ✦'],   fx:'runes',     args:[]},
    {w:2,  sp:['🔥 STREAK!','fire!'],           fx:'streak',    args:[]},
    {w:2,  sp:['✈️ Travel!','🗺️'],             fx:'trail',     args:['✈️']},
    {w:1,  sp:['⚡ LEGENDARY ⚡','✦✦✦'],       fx:'halo',      args:[]},
  ],
  beast: [
    {w:10, sp:['Гр!','GRR!','🐾'],             fx:'bounce',    args:[1.2,5,0]},
    {w:10, sp:['*хвіст*','~wag~','🦊'],        fx:'tilt',      args:[12]},
    {w:10, sp:['Ей!','!','*ear*'],              fx:'tilt',      args:[-8]},
    {w:9,  sp:['*growl*','🐾','*sniff*'],       fx:'bounce',    args:[1.28,-6,0]},
    {w:9,  sp:['*stomp*','💥','!'],             fx:'particles', args:['#ff7040',8,90,180,35]},
    {w:8,  sp:['RRRR!','BEAST!','🔥'],         fx:'bounce',    args:[1.25,8,0]},
    {w:8,  sp:['*scratch*','!','Ой!'],          fx:'spin',      args:[180]},
    {w:7,  sp:['*jump*','!','BOING!'],          fx:'bounce',    args:[1.35,0,0]},
    {w:7,  sp:['👀','*stare*','?'],             fx:'tilt',      args:[3]},
    {w:6,  sp:['*bite*','!','🔥'],              fx:'ring',      args:[60,'rgba(255,112,64,',2]},
    {w:5,  sp:['*roll*','whoosh!','!'],         fx:'spin',      args:[540]},
    {w:5,  sp:['ROAR!','BEAST MODE!','🔥'],    fx:'particles', args:['#ff4020',12,80,200,45]},
    {w:5,  sp:['*pounce*','!','🎯'],            fx:'bounce',    args:[1.4,-10,0]},
    {w:4,  sp:['🔥','burn!','HOT'],             fx:'trail',     args:['🔥']},
    {w:4,  sp:['*howl*','AWOO!','🐺'],         fx:'confetti',  args:[]},
    {w:4,  sp:['*dig*','💨','!'],               fx:'particles', args:['#f5c842',6,90,160,30]},
    {w:3,  sp:['*lick*','🐾','*nuzzle*'],      fx:'heart',     args:[]},
    {w:3,  sp:['💥 CRITICAL!','!'],             fx:'ring',      args:[80,'rgba(255,64,32,',4]},
    {w:2,  sp:['*mega stomp*','QUAKE!'],        fx:'particles', args:['#ff4020',16,70,220,50]},
    {w:2,  sp:['🔥🔥 ON FIRE','BEAST'],        fx:'runes',     args:[]},
    {w:1,  sp:['⚡ ALPHA BEAST ⚡','LEGENDARY'],fx:'halo',      args:[]},
  ],
  buddy: [
    {w:10, sp:['BEEP!','🤖','OK'],              fx:'ring',      args:[48,'rgba(94,231,176,',2]},
    {w:10, sp:['PING!','~','ACK'],              fx:'bounce',    args:[1.1,0,0]},
    {w:10, sp:['ERROR ♥','!','FAULT'],         fx:'tilt',      args:[7]},
    {w:9,  sp:['SCAN...','📡','LOAD'],          fx:'blink',     args:[]},
    {w:9,  sp:['DATA+','++','✓OK'],            fx:'particles', args:['#5ee7b0',7,0,360,30]},
    {w:8,  sp:['COMPUTE!','🖥️','CALC'],        fx:'spin',      args:[360]},
    {w:8,  sp:['ALERT!','!','SIGNAL'],         fx:'ring',      args:[60,'rgba(94,231,176,',3]},
    {w:7,  sp:['REBOOT!','⚡','SYS'],          fx:'bounce',    args:[1.2,-5,0]},
    {w:7,  sp:['ACCESS+','OK','✓'],            fx:'tilt',      args:[-7]},
    {w:6,  sp:['UPGRADE!','🦾','VER+'],        fx:'ring',      args:[70,'rgba(64,200,240,',2]},
    {w:5,  sp:['WORD_PROC','📊','data+'],      fx:'word_orbit',args:[]},
    {w:5,  sp:['XP_BOOST!','⚡+XP'],           fx:'xp_pulse',  args:[]},
    {w:5,  sp:['EMOJI_SYS','👾','GG'],         fx:'confetti',  args:[]},
    {w:4,  sp:['LINK!','⚡','NETW+'],          fx:'particles', args:['#40c8f0',8,0,360,28]},
    {w:4,  sp:['WIFI_OK','📶','SYNC'],         fx:'trail',     args:['📡']},
    {w:4,  sp:['CMD_RUN','>>','EXEC'],         fx:'letters',   args:[]},
    {w:3,  sp:['LOVE.exe','❤️','♥_SYS'],      fx:'heart',     args:[]},
    {w:3,  sp:['TURBO!','🚀','MAX'],           fx:'spin',      args:[720]},
    {w:2,  sp:['OVERCLOCK!','🔥CPU'],          fx:'ring',      args:[90,'rgba(94,231,176,',5]},
    {w:2,  sp:['MEGA_UPGRADE!','ULTRA'],       fx:'runes',     args:[]},
    {w:1,  sp:['⚡ SYSTEM PEAK ⚡','LEGENDARY'],fx:'halo',     args:[]},
  ],
};

function weightedRandom(pool) {
  const total = pool.reduce(function(s,e) { return s + e.w; }, 0);
  let r = Math.random() * total;
  for (let i = 0; i < pool.length; i++) { r -= pool[i].w; if (r <= 0) return pool[i]; }
  return pool[0];
}

function executeReaction(entry, art, cx, cy) {
  const fx = entry.fx, a = entry.args || [];
  if (fx === 'ring') {
    const base = a[0]||55, col = a[1]||'rgba(124,110,245,', cnt = a[2]||2;
    for (let i = 0; i < cnt; i++) {
      const r = document.createElement('div'); r.className = 'fx-ring';
      r.style.cssText = 'width:'+(base+i*28)+'px;height:'+(base+i*28)+'px;border:2px solid '+col+(0.75-i*0.2)+');left:'+cx+'px;top:'+cy+'px;animation-delay:'+(i*0.08)+'s;animation-duration:'+(0.42+i*0.09)+'s';
      document.body.appendChild(r); setTimeout(function() { r.remove(); }, 700);
    }
  } else if (fx === 'bounce') {
    const sc=a[0]||1.15, rx=a[1]||0;
    art.style.transition='transform 0.18s cubic-bezier(0.3,0,0.7,1)';
    art.style.transform='scale('+sc+') rotate('+rx+'deg)';
    setTimeout(function() { art.style.transform=''; setTimeout(function() { art.style.transition=''; },200); },200);
  } else if (fx === 'spin') {
    const deg=a[0]||360, dur=(deg/360*0.5);
    art.style.transition='transform '+dur+'s cubic-bezier(0.4,0,0.6,1)';
    art.style.transform='rotate('+deg+'deg)';
    setTimeout(function() { art.style.transform='rotate(0deg)'; art.style.transition='transform 0.3s ease'; setTimeout(function() { art.style.transition=''; },300); }, dur*1000+100);
  } else if (fx === 'tilt') {
    art.style.transition='transform 0.2s ease';
    art.style.transform='rotate('+(a[0]||8)+'deg) scale(1.05)';
    setTimeout(function() { art.style.transition='transform 0.3s ease'; art.style.transform=''; setTimeout(function() { art.style.transition=''; },300); },360);
  } else if (fx === 'particles') {
    const col=a[0]||'#7c6ef5', cnt=a[1]||8, startA=a[2]||0, spread=a[3]||360, dist=a[4]||35;
    for (let i=0; i<cnt; i++) {
      const p=document.createElement('div'); p.className='fx-particle';
      const sz=3+Math.random()*5, ang=(startA+(i/cnt)*spread)*Math.PI/180, d=dist+Math.random()*20;
      p.style.cssText='width:'+sz+'px;height:'+sz+'px;background:'+col+';border-radius:50%;left:'+cx+'px;top:'+cy+'px;transform:translate(-50%,-50%)';
      document.body.appendChild(p); p.offsetHeight;
      p.style.transform='translate(calc(-50% + '+(Math.cos(ang)*d)+'px),calc(-50% + '+(Math.sin(ang)*d)+'px))'; p.style.opacity='0';
      setTimeout(function() { p.remove(); },650);
    }
  } else if (fx === 'word_orbit') {
    const words=state.wordsLearned.length>0?state.wordsLearned:['word'];
    const w=words[Math.floor(Math.random()*words.length)];
    const orb=document.createElement('div'); orb.className='fx-word-orbit'; orb.textContent=w;
    orb.style.cssText='left:'+cx+'px;top:'+cy+'px;'; document.body.appendChild(orb);
    setTimeout(function() { orb.remove(); },1400);
  } else if (fx === 'aura') {
    const glow=document.createElement('div'); glow.className='fx-aura-pulse';
    glow.style.cssText='left:'+cx+'px;top:'+cy+'px;background:radial-gradient(circle,'+(a[0]||'#7c6ef5')+'44,transparent 70%)';
    document.body.appendChild(glow); setTimeout(function() { glow.remove(); },800);
  } else if (fx === 'letters') {
    const src=(state.lesson&&state.lesson.words&&state.lesson.words[0]?state.lesson.words[0].word:'MAGIC').toUpperCase();
    src.split('').forEach(function(letter,i) {
      const el=document.createElement('div'); el.className='fx-xp';
      el.textContent=letter; el.style.cssText='left:'+(cx-src.length*6+i*14)+'px;top:'+(cy-10)+'px;font-size:16px;font-weight:900;color:#a89cff;';
      document.body.appendChild(el); setTimeout(function() { el.remove(); },900);
    });
  } else if (fx === 'confetti') {
    const cols=['#7c6ef5','#5ee7b0','#f5c842','#ff5e7a','#a89cff'];
    for (let i=0; i<16; i++) {
      const c=document.createElement('div'); c.className='fx-confetti';
      c.style.cssText='background:'+cols[i%cols.length]+';left:'+(cx-60+Math.random()*120)+'px;top:'+(cy-30)+'px;--dur:'+(0.5+Math.random()*0.7)+'s;--delay:'+(Math.random()*0.3)+'s;border-radius:'+(Math.random()>0.5?'50%':'2px');
      document.body.appendChild(c); setTimeout(function() { c.remove(); },1200);
    }
  } else if (fx === 'heart') {
    const hearts=['❤️','💜','💙','💚','💛'];
    for (let i=0; i<5; i++) {
      const el=document.createElement('div'); el.className='fx-xp';
      el.textContent=hearts[i%hearts.length];
      el.style.cssText='left:'+(cx-40+Math.random()*80)+'px;top:'+(cy-10)+'px;font-size:18px;animation-duration:'+(0.7+Math.random()*0.5)+'s;';
      document.body.appendChild(el); setTimeout(function() { el.remove(); },1200);
    }
  } else if (fx === 'trail') {
    const icon=a[0]||'✨';
    for (let i=0; i<6; i++) {
      const el=document.createElement('div'); el.className='fx-xp';
      el.textContent=icon; el.style.cssText='left:'+(cx-60+i*24)+'px;top:'+(cy+20-i*8)+'px;font-size:16px;animation-delay:'+(i*0.08)+'s;';
      document.body.appendChild(el); setTimeout(function() { el.remove(); },1300);
    }
  } else if (fx === 'runes') {
    const runes=['✦','ᚱ','ᚢ','ᚾ','ᛖ','✧','⊕','∞'];
    for (let i=0; i<6; i++) {
      const el=document.createElement('div'); el.className='fx-xp';
      el.textContent=runes[i%runes.length];
      el.style.cssText='left:'+(cx-50+Math.random()*100)+'px;top:'+(cy-30+Math.random()*40)+'px;font-size:20px;color:#a89cff;animation-duration:1.2s;';
      document.body.appendChild(el); setTimeout(function() { el.remove(); },1400);
    }
  } else if (fx === 'halo') {
    for (let i=0; i<5; i++) {
      const r=document.createElement('div'); r.className='fx-ring';
      const sz=50+i*35, cols=['rgba(245,200,66,','rgba(255,180,50,','rgba(200,128,32,'];
      r.style.cssText='width:'+sz+'px;height:'+sz+'px;border:3px solid '+cols[i%3]+(0.85-i*0.15)+');left:'+cx+'px;top:'+cy+'px;animation-delay:'+(i*0.12)+'s;animation-duration:0.65s';
      document.body.appendChild(r); setTimeout(function() { r.remove(); },1000);
    }
    FX.xpFloat(cx, cy-50, '⚡ LEGENDARY ⚡');
    executeReaction({fx:'confetti',args:[]}, art, cx, cy);
  } else if (fx === 'topic') {
    const icons={travel:'✈️',work:'💼',emotions:'❤️',technology:'⚡',everyday:'💬',mixed:'🎲'};
    executeReaction({fx:'trail',args:[icons[state.topic]||'📚']}, art, cx, cy);
  } else if (fx === 'streak') {
    FX.streak(state.streak, cx, cy);
  } else if (fx === 'xp_pulse') {
    FX.xpFloat(cx, cy-30, '+XP ✨');
    executeReaction({fx:'ring',args:[60,'rgba(94,231,176,',3]}, art, cx, cy);
  } else if (fx === 'blink') {
    const eyes=art.querySelectorAll('.sp-eye,.b-eye-l,.b-eye-r,.bu-visor');
    eyes.forEach(function(e) { e.classList.add('blink-anim'); setTimeout(function() { e.classList.remove('blink-anim'); },400); });
  }
}

function fireReaction(arch, chainCount) {
  const pool = REACTION_POOLS[arch] || REACTION_POOLS.spirit;
  let entry;
  if (chainCount >= 4) {
    const uncommon = pool.filter(function(e) { return e.w <= 5; });
    entry = weightedRandom(uncommon.length > 0 ? uncommon : pool);
  } else {
    entry = weightedRandom(pool);
  }
  const art = document.getElementById('lexiArt');
  if (!art) return entry;
  const rect = art.getBoundingClientRect();
  const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
  executeReaction(entry, art, cx, cy);
  const sp = entry.sp[Math.floor(Math.random() * entry.sp.length)];
  updateLexiSpeech(sp);
  return entry;
}

// ===== LEXI EVOLUTION STAGES =====
const LEXI_STAGES = [
  {
    stage: 0, name: 'Яйце', emoji: '🥚',
    wordsNeeded: 0, lessonsNeeded: 0,
    description: 'Лексик ще не вилупився. Почни вчити слова!',
    unlocks: null,
    speech: ['Зроби перший урок, щоб я прокинувся! 🥚', 'Я тут... Просто чекаю... 🥚', 'Нагодуй мене першим словом!'],
    evoText: 'Яйце готове до вилуплення...',
  },
  {
    stage: 1, name: 'Малюк', emoji: '🐣',
    wordsNeeded: 0, lessonsNeeded: 1,
    description: 'Лексик вилупився! Перший урок пройдено.',
    unlocks: 'Відкрито: базові уроки',
    speech: ['Я прокинувся! Дай ще слова! 🐣', 'Вчи мене! Я хочу рости!', 'Кожне слово — крок до нової форми!'],
    evoText: '🐣 Вилупився!',
  },
  {
    stage: 2, name: 'Дух слів', emoji: '🌟',
    wordsNeeded: 10, lessonsNeeded: 3,
    description: 'Лексик став Духом Слів. Ти вже серйозний!',
    unlocks: 'Відкрито: детальні пояснення слів',
    speech: ['Дай мені idiom! Вони такі смачні ✨', 'Я відчуваю твій прогрес!', 'Ти вже на рівні вище середніх!', '"Ти вже сильний у daily English!"'],
    evoText: '🌟 Еволюція: Дух Слів!',
  },
  {
    stage: 3, name: 'Мудрець', emoji: '🦋',
    wordsNeeded: 30, lessonsNeeded: 7,
    description: 'Лексик став Мудрецем. Він пам\'ятає всі твої слова.',
    unlocks: 'Відкрито: Режим повторення + розширені quiz',
    speech: ['Я бачу твої слабкі місця... 🦋', 'Хочеш складніше? Спробуй B2!', '"Тобі добре заходять слова про роботу"', 'Ти вже на рівні вище середніх!'],
    evoText: '🦋 Еволюція: Мудрець!',
  },
  {
    stage: 4, name: 'Легенда', emoji: '🔮',
    wordsNeeded: 60, lessonsNeeded: 14,
    description: 'Лексик досяг рідкісної форми. Ти — Легенда!',
    unlocks: 'Відкрито: Challenge Mode + Rare Word Packs',
    speech: ['Я пишаюся тобою! 🔮✨', 'Ти — Легенда Voodoo!', 'Рідкісна форма розблокована!', 'Хочу ще складніших слів!'],
    evoText: '🔮 РІДКІСНА ЕВОЛЮЦІЯ!',
  },
  {
    stage: 5, name: 'Хаос', emoji: '⚡',
    wordsNeeded: 100, lessonsNeeded: 30,
    description: 'Лексик досяг фінальної форми. Ти — Майстер.',
    unlocks: 'Відкрито: все! Ти майстер мови.',
    speech: ['ФІНАЛЬНА ФОРМА! ⚡', 'Ти — Майстер Voodoo!', 'Нічого більше нема... Хіба що повчити ще?'],
    evoText: '⚡ ФІНАЛЬНА ЕВОЛЮЦІЯ!',
  },
];

// ===== SMART PHRASES based on user behavior =====
function getLexiSpeech(st) {
  const stage = LEXI_STAGES[st.lexiStage] || LEXI_STAGES[0];
  const pool = [...stage.speech];

  if (st.streak >= 7) pool.push('7 днів поспіль! Ти неймовірний! 🌟');
  if (st.streak >= 3) pool.push('Streak ' + st.streak + ' — продовжуй!');
  if (st.wordsLearned.length >= 10) pool.push('"Тобі добре даються нові слова!"');
  if (!st.lessonDoneToday) pool.push('Сьогодні ще не вчились... 😴');
  if (st.lessonDoneToday) pool.push('Урок пройдено! Молодець! ✅');

  const hour = new Date().getHours();
  if (hour < 9) pool.push('Рання пташка! Гарний старт! 🌅');
  if (hour >= 22) pool.push('Пізно, але навчання є навчання 🌙');

  return pool[Math.floor(Math.random() * pool.length)];
}

// ===== STATE =====
const state = {
  user: null,
  lesson: null,
  currentWordIdx: 0,
  quizState: null,
  gameState: null,
  currentTab: 'home',
  lexiStage: 0,
  lexiEvo: 0,
  lexiMood: 'idle',
  lessonDoneToday: false,
  feedableWords: [],
  fedWords: [],
  wordsLearned: [],
  streak: 0,
  xp: 0,
  level: 'A2',
  topic: 'everyday',
  petArchetype: null,     // legacy: spirit | beast | buddy
  petCharacter: null,     // new: lumix | kitsune | mochi | byte | ember | mist | marco | bruno | crash
  leaderXP: 0,            // cached from leaderboard
  companionName: null,
  activeSkin: 'base',
  isPremium: false,
  premiumExpires: null,
  petHp: 100,
};

// ===== LOCAL STORAGE =====
function saveLocal() {
  localStorage.setItem('twd_v2', JSON.stringify({
    lexiStage: state.lexiStage,
    lexiEvo: state.lexiEvo,
    wordsLearned: state.wordsLearned,
    streak: state.streak,
    xp: state.xp,
    level: state.level,
    topic: state.topic,
    lessonDoneToday: state.lessonDoneToday,
    petArchetype: state.petArchetype,
    petCharacter: state.petCharacter,
    companionName: state.companionName,
    activeSkin: state.activeSkin,
    lastSaveDate: new Date().toDateString(),
  }));
}

async function savePetToServer() {
  const tgId = state.user?.tg_id || 999999;
  const char = state.petCharacter || state.petArchetype || 'lumix';
  await apiCall('/api/user/pet/select', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ tg_id: tgId, pet_character: char, pet_name: state.companionName }),
  }, null);
}

function loadLocal() {
  try {
    const s = JSON.parse(localStorage.getItem('twd_v2') || '{}');
    if (s.lastSaveDate !== new Date().toDateString()) {
      s.lessonDoneToday = false;
      s.fedWords = [];
    }
    Object.assign(state, s);
  } catch(e) {}
}

// ===== LEXI EVOLUTION LOGIC =====
function getLexiEmoji(stageIdx) {
  const arch = PET_ARCHETYPES[state.petArchetype || 'spirit'];
  return arch.stageEmojis[stageIdx] || LEXI_STAGES[stageIdx]?.emoji || '🥚';
}

function computeLexiStage() {
  const words = state.wordsLearned.length;
  const serverLessons = state.user?.total_lessons || 0;
  // Count today's lesson immediately even before server confirms it
  const effectiveLessons = state.lessonDoneToday ? Math.max(serverLessons, 1) : serverLessons;
  let stage = 0;
  for (let i = LEXI_STAGES.length - 1; i >= 0; i--) {
    if (words >= LEXI_STAGES[i].wordsNeeded && effectiveLessons >= LEXI_STAGES[i].lessonsNeeded) {
      stage = i;
      break;
    }
  }
  return stage;
}

function computeEvoProgress() {
  const current = LEXI_STAGES[state.lexiStage];
  const next = LEXI_STAGES[state.lexiStage + 1];
  if (!next) return 100;
  const words = state.wordsLearned.length;
  const wordsNeeded = next.wordsNeeded - current.wordsNeeded;
  const wordsDone = words - current.wordsNeeded;
  return Math.min(100, Math.max(0, Math.round((wordsDone / wordsNeeded) * 100)));
}

async function checkEvolution() {
  const newStage = computeLexiStage();
  if (newStage > state.lexiStage) {
    state.lexiStage = newStage;
    saveLocal();
    await showEvoPopup(LEXI_STAGES[newStage]);
    return true;
  }
  state.lexiEvo = computeEvoProgress();
  return false;
}

// ===== API =====
async function apiCall(url, options, fallback) {
  if (fallback === undefined) fallback = null;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 4000);
    const res = await fetch(API + url, { ...options, signal: controller.signal });
    clearTimeout(timer);
    if (res.ok) return await res.json();
  } catch(e) {}
  return fallback;
}

async function initUser() {
  const tgUser = tg?.initDataUnsafe?.user;
  const body = {
    tg_init_data: tg?.initData || 'demo',
    user: tgUser || { id: 999999, first_name: 'Demo' },
  };
  const result = await apiCall('/api/user/init', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  }, null);

  if (result) {
    state.user = result;
    state.xp = result.xp || state.xp;
    state.streak = result.streak || state.streak;
    state.level = result.level || state.level;
    state.topic = result.topic || state.topic;
    if (result.words_learned && result.words_learned.length > state.wordsLearned.length) {
      state.wordsLearned = result.words_learned;
    }
    // Server is always source of truth for pet — overwrites localStorage
    if (result.pet_character) {
      state.petCharacter = result.pet_character;
      // keep archetype in sync for legacy code
      const charArchMap = {
        lumix:'spirit', mist:'spirit', nova:'spirit', marco:'buddy',
        byte:'buddy', biscuit:'buddy', apex:'buddy', astro:'buddy',
        kitsune:'beast', mochi:'beast', ember:'beast', bruno:'beast',
        crash:'beast', luna:'beast', rex:'beast', ronin:'beast', bolt:'beast',
        sunny:'spirit', kaito:'spirit', yuki:'spirit',
        vex:'beast', seraph:'spirit',
      };
      state.petArchetype = charArchMap[result.pet_character] || state.petArchetype || 'spirit';
      saveLocal();
    }
    if (result.pet_name) {
      state.companionName = result.pet_name;
      saveLocal();
    }
    state.isPremium = !!result.is_premium;
    state.premiumExpires = result.premium_expires || null;
    state.streakFreeze = result.streak_freeze || 0;
    // Notify user if freeze was auto-applied to protect streak
    if (result.freeze_applied) {
      setTimeout(function() {
        showToast('🧊 Заморозка захистила твою серію! Залишилось: ' + result.streak_freeze, 'success');
      }, 1500);
    }
    // Restore pet stage from server XP (don't let it go backwards)
    if (result.xp > 0) {
      const serverStage = computeLexiStage();
      if (serverStage > state.lexiStage) {
        state.lexiStage = serverStage;
        saveLocal();
      }
    }
  }
}

async function fetchLesson() {
  const tgId = state.user?.tg_id || 999999;
  return await apiCall('/api/lesson?tg_id=' + tgId, {}, MOCK_LESSON);
}

// ===== MOCK DATA =====
const MOCK_LESSON = {
  words: [
    {word:'resilient',transcription:'/rɪˈzɪliənt/',translation:'стійкий',example:"She's incredibly resilient under pressure.",example_ua:'Вона неймовірно стійка під тиском.'},
    {word:'ambitious',transcription:'/æmˈbɪʃəs/',translation:'амбітний',example:"He's ambitious about his goals.",example_ua:'Він амбітний щодо своїх цілей.'},
    {word:'persistent',transcription:'/pərˈsɪstənt/',translation:'наполегливий',example:'Persistent effort leads to success.',example_ua:'Наполеглива праця веде до успіху.'},
  ],
  idiom:{text:'break a leg',translation:'ні пуху ні пера',example:'Break a leg in your presentation!',example_ua:'Удачі на презентації!'},
  mini_story:'Alex was resilient and ambitious. Despite failures, he remained persistent.',
  mini_story_ua:'Алекс був стійким та амбітним. Незважаючи на невдачі, він залишався наполегливим.',
  quiz:[
    {question:"Що означає 'resilient'?",answers:['стійкий','слабкий','швидкий','тихий'],correct:0},
    {question:"Що означає 'ambitious'?",answers:['ледачий','амбітний','спокійний','сумний'],correct:1},
    {question:"Що означає 'persistent'?",answers:['повільний','хаотичний','наполегливий','байдужий'],correct:2},
  ],
};

// ===== RENDER FUNCTIONS =====

function updateHeader() {
  const el = document.getElementById('streakCount');
  if (el) el.textContent = state.streak;
}

// ===== HOME TAB: LEXI SPIRIT =====
// ── Daily Task Checklist ──────────────────────────────────────────────────────

var DAILY_TASKS = [
  { id: 'open',   icon: '📱', label: 'Відкрити Voodoo',       xp: 5 },
  { id: 'lesson', icon: '📚', label: 'Пройти урок дня',       xp: 15 },
  { id: 'game',   icon: '🎮', label: 'Зіграти в гру',         xp: 10 },
  { id: 'word',   icon: '📖', label: 'Вивчити 3 слова',       xp: 10 },
  { id: 'invite', icon: '👥', label: 'Поділитись посиланням', xp: 5  },
];

function getDailyProgress() {
  var today = new Date().toISOString().slice(0,10);
  var saved = JSON.parse(localStorage.getItem('voodoo_daily_tasks') || '{}');
  if (saved.date !== today) {
    saved = { date: today, done: { open: true } }; // 'open' auto-done on load
    localStorage.setItem('voodoo_daily_tasks', JSON.stringify(saved));
  }
  return saved;
}

function markTaskDone(taskId) {
  var prog = getDailyProgress();
  if (!prog.done[taskId]) {
    prog.done[taskId] = true;
    localStorage.setItem('voodoo_daily_tasks', JSON.stringify(prog));

    var task = DAILY_TASKS.find(function(t) { return t.id === taskId; });
    var allDone = DAILY_TASKS.every(function(t) { return prog.done[t.id]; });

    if (task) showXPFloat('+' + task.xp + ' XP за задачу!');
    if (allDone) {
      setTimeout(function() {
        showXPFloat('🎉 +25 XP — всі задачі виконано!');
        apiCall('/api/progress', { method:'POST', body: JSON.stringify({ tg_id: tgId, xp: 25 }) });
      }, 800);
    }
    if (apiCall && tgId) {
      apiCall('/api/progress', { method:'POST', body: JSON.stringify({ tg_id: tgId, xp: task ? task.xp : 0 }) });
    }
    // Re-render checklist in-place if home is active
    var el = document.getElementById('daily-checklist');
    if (el) el.outerHTML = buildDailyChecklist();
  }
}

function buildDailyChecklist() {
  var prog = getDailyProgress();
  var doneCnt = DAILY_TASKS.filter(function(t) { return prog.done[t.id]; }).length;
  var pct = Math.round(doneCnt / DAILY_TASKS.length * 100);

  var items = DAILY_TASKS.map(function(t) {
    var done = !!prog.done[t.id];
    return '<div class="task-row ' + (done ? 'task-done' : '') + '">' +
      '<span class="task-icon">' + (done ? '✅' : t.icon) + '</span>' +
      '<span class="task-label">' + t.label + '</span>' +
      '<span class="task-xp">+' + t.xp + ' XP</span>' +
    '</div>';
  }).join('');

  return '<div id="daily-checklist" class="daily-checklist">' +
    '<div class="section-title">✅ Щоденні задачі · ' + doneCnt + '/' + DAILY_TASKS.length + '</div>' +
    '<div class="task-progress-bar"><div class="task-progress-fill" style="width:' + pct + '%"></div></div>' +
    items +
    (pct === 100 ? '<div class="task-all-done">🎉 Всі задачі виконано! +25 XP бонус</div>' : '') +
  '</div>';
}

function getLeague(xp) {
  if (xp >= 5000) return { name: 'Diamond', icon: '💎', color: '#00e5ff' };
  if (xp >= 2000) return { name: 'Gold',    icon: '🥇', color: '#ffd700' };
  if (xp >= 800)  return { name: 'Silver',  icon: '🥈', color: '#c0c0c0' };
  return { name: 'Bronze', icon: '🥉', color: '#cd7f32' };
}

function getPassiveXP() {
  var key = 'voodoo_last_collect';
  var last = parseInt(localStorage.getItem(key) || '0');
  var now = Date.now();
  var hoursAway = Math.floor((now - last) / 3600000);
  return Math.min(hoursAway * 3, 50); // max 50 passive XP
}

function collectPassiveXP() {
  var earned = getPassiveXP();
  if (earned <= 0) { showToast('Пасивний XP накопичується — зайди пізніше!', 'info'); return; }
  localStorage.setItem('voodoo_last_collect', Date.now().toString());
  state.xp = (state.xp || 0) + earned;
  showXPFloat('+' + earned + ' XP поки ти спав 😴');
  haptic('success');
  if (tgId) apiCall('/api/progress', { method:'POST', body: JSON.stringify({ tg_id: tgId, xp: earned }) });
  setTimeout(renderHome, 500);
}

function renderHome() {
  const stage = LEXI_STAGES[state.lexiStage] || LEXI_STAGES[0];
  const nextStage = LEXI_STAGES[state.lexiStage + 1];
  const evoProgress = computeEvoProgress();
  const speech = getLexiSpeech(state);
  const today = new Date();
  const league = getLeague(state.xp || 0);
  const passiveXP = getPassiveXP();
  const lives = Math.max(0, Math.min(5, state.lives !== undefined ? state.lives : 5));
  const heartsHTML = '❤️'.repeat(lives) + '🖤'.repeat(5 - lives);

  // Streak calendar (7 days)
  const days = ['Нд','Пн','Вт','Ср','Чт','Пт','Сб'];
  const calHTML = Array.from({length:7}, function(_,i) {
    const d = new Date(today);
    d.setDate(today.getDate() - (6 - i));
    const isToday = i === 6;
    const isActive = (i > (7 - state.streak) && !isToday) || (isToday && state.lessonDoneToday);
    return '<div class="day-circle ' + (isActive ? 'active' : '') + ' ' + (isToday ? 'today' : '') + '">' + days[d.getDay()] + '</div>';
  }).join('');

  // Social proof (pseudo-real: base + seeded random by day)
  const seed = today.getFullYear() * 10000 + (today.getMonth()+1) * 100 + today.getDate();
  const activeUsers = 1200 + (seed % 800);

  // Passive XP button
  const passiveBtn = passiveXP > 0
    ? '<button class="passive-xp-btn" onclick="collectPassiveXP()">💤 Зібрати +' + passiveXP + ' XP</button>'
    : '';

  const feedBtn = state.lessonDoneToday
    ? '<button class="lexi-action-btn" onclick="triggerFeed()"><span class="icon">🍎</span><span class="label">Нагодуй</span></button>'
    : '<button class="lexi-action-btn dimmed" onclick="switchTab(\'lesson\')"><span class="icon">📚</span><span class="label">Урок</span></button>';

  document.getElementById('main').innerHTML =
    // ── TOP STATS BAR ──
    '<div class="home-stats-bar fade-in">' +
      '<div class="hstat">' +
        '<div class="hstat-val">' + (state.xp || 0) + '</div>' +
        '<div class="hstat-lbl">XP</div>' +
      '</div>' +
      '<div class="hstat league-badge" style="color:' + league.color + '">' +
        '<div class="hstat-val">' + league.icon + '</div>' +
        '<div class="hstat-lbl">' + league.name + '</div>' +
      '</div>' +
      '<div class="hstat">' +
        '<div class="hstat-val">🔥 ' + (state.streak || 0) + '</div>' +
        '<div class="hstat-lbl">серія</div>' +
      '</div>' +
      '<div class="hstat">' +
        '<div class="hstat-val">' + heartsHTML + '</div>' +
        '<div class="hstat-lbl">life</div>' +
      '</div>' +
    '</div>' +

    // ── PASSIVE XP COLLECT ──
    (passiveBtn ? '<div class="passive-xp-wrap fade-in">' + passiveBtn + '</div>' : '') +

    // ── PET CARD ──
    '<div class="lexi-card fade-in">' +
      '<div class="lexi-stage-label">' + stage.name.toUpperCase() + ' · ' + (state.totalWords || 0) + ' слів</div>' +
      '<div class="lexi-name" onclick="startRenameCompanion()">' + (state.companionName || 'ЛЕКСИК').toUpperCase() + ' <span class="lexi-rename-hint">✏️</span></div>' +
      '<div class="lexi-speech" id="lexiSpeech">' + speech + '</div>' +
      '<div class="lexi-visual" id="lexiVisual" onclick="onCompanionTap()" style="cursor:pointer">' +
        '<div class="lexi-art" id="lexiArt">' + buildCompanionHTML(state.lexiStage, state.petArchetype) + '</div>' +
        '<div class="lexi-glow pulse"></div>' +
        '<div class="tap-hint">натисни ▼</div>' +
      '</div>' +
      '<div class="evo-bar-wrap">' +
        '<div class="evo-label">' +
          '<span>Еволюція ' + Math.round(evoProgress) + '%</span>' +
          '<span>' + (nextStage ? nextStage.name + ' — ' + nextStage.wordsNeeded + ' слів' : '⭐ MAX!') + '</span>' +
        '</div>' +
        '<div class="evo-bar"><div class="evo-fill" style="width:' + evoProgress + '%"></div></div>' +
      '</div>' +
      '<div class="lexi-actions">' +
        feedBtn +
        '<button class="lexi-action-btn" onclick="switchTab(\'games\')"><span class="icon">🎮</span><span class="label">Ігри</span></button>' +
        '<button class="lexi-action-btn" onclick="triggerTalk()"><span class="icon">💬</span><span class="label">Говори</span></button>' +
      '</div>' +
    '</div>' +

    // ── QUICK ACTIONS ──
    '<div class="quick-actions fade-in">' +
      '<button class="quick-btn primary" onclick="switchTab(\'lesson\')">' +
        '<div class="qb-icon">📚</div>' +
        '<div class="qb-label">' + (state.lessonDoneToday ? '✅ Урок виконано' : 'Урок дня') + '</div>' +
        '<div class="qb-xp">+30 XP</div>' +
      '</button>' +
      '<button class="quick-btn" onclick="switchTab(\'games\')">' +
        '<div class="qb-icon">🎮</div>' +
        '<div class="qb-label">Ігри</div>' +
        '<div class="qb-xp">+35–60 XP</div>' +
      '</button>' +
      '<button class="quick-btn" onclick="switchTab(\'leaderboard\')">' +
        '<div class="qb-icon">🏆</div>' +
        '<div class="qb-label">Рейтинг</div>' +
        '<div class="qb-xp">Топ ' + (state.rank ? '#' + state.rank : '') + '</div>' +
      '</button>' +
    '</div>' +

    // ── SOCIAL PROOF ──
    '<div class="social-proof fade-in">' +
      '👥 <b>' + activeUsers.toLocaleString('uk-UA') + '</b> людей вчаться разом з тобою сьогодні' +
    '</div>' +

    // ── STREAK CALENDAR ──
    '<div class="section-title">🔥 Streak цього тижня</div>' +
    '<div class="streak-cal">' + calHTML + '</div>' +

    // ── DAILY TASKS ──
    buildDailyChecklist() +

    // ── AD REWARD ──
    (ADSGRAM_BLOCK_ID !== 'YOUR_ADSGRAM_BLOCK_ID'
      ? '<div class="ad-reward-block">' +
          '<button class="btn-ad-reward" onclick="watchRewardedAd()" id="adRewardBtn">' +
            '📺 Дивись рекламу → +15 XP' +
          '</button>' +
          '<div style="font-size:10px;color:var(--text2);text-align:center;margin-top:4px">1 раз на день безкоштовно</div>' +
        '</div>'
      : '') +

    // ── MONTH COMPETITION ──
    '<div class="premium-comp">' +
      '<div class="premi-head">' +
        '<div class="premi-icon-big">' + league.icon + '</div>' +
        '<div class="premi-head-info">' +
          '<div class="premi-head-title">' + league.name + ' League · Місячний змагання</div>' +
          '<div class="premi-head-sub">🏆 Top 10 = Telegram Premium</div>' +
        '</div>' +
      '</div>' +
      '<div class="premi-stats-row">' +
        '<div class="premi-stat-box"><div class="premi-stat-n">' + (state.xp||0) + '</div><div class="premi-stat-l">Твій XP</div></div>' +
        '<div class="premi-stat-box highlight"><div class="premi-stat-n">' + (state.leaderXP || '?') + '</div><div class="premi-stat-l">Лідер</div></div>' +
        '<div class="premi-stat-box"><div class="premi-stat-n">' + Math.max(0, 500 - (state.xp||0)) + '</div><div class="premi-stat-l">До Top10</div></div>' +
      '</div>' +
      '<button class="premi-cta" onclick="switchTab(\'lesson\')">' +
        (state.lessonDoneToday ? '🎮 Грати в ігри → більше XP' : '📚 Почати урок → +30 XP') +
      '</button>' +
    '</div>';

  setTimeout(startIdleAnimation, 800);

  // ===== PET SICK STATE =====
  var petEl = document.getElementById('lexiArt');
  if (petEl) {
    petEl.classList.remove('pet-sick', 'pet-critical');
    if (state.petHp < 10) {
      petEl.classList.add('pet-critical');
    } else if (state.petHp < 30) {
      petEl.classList.add('pet-sick');
    }
  }
}

// ===== LEXI INTERACTIONS =====
var tapChain = { count: 0, timer: null };

function onCompanionTap() {
  const art = document.getElementById('lexiArt');
  if (!art) return;

  if (tapChain.timer) clearTimeout(tapChain.timer);
  tapChain.count++;
  tapChain.timer = setTimeout(function() { tapChain.count = 0; }, 1400);

  art.classList.remove('tap-react');
  art.offsetHeight;
  art.classList.add('tap-react');
  setTimeout(function() { art.classList.remove('tap-react'); }, 400);

  const arch = state.petArchetype || 'spirit';
  fireReaction(arch, tapChain.count);

  const haptic = tapChain.count >= 4 ? 'heavy' : tapChain.count >= 2 ? 'medium' : 'light';
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred(haptic);
}

// ===== IDLE BEHAVIOR SYSTEM (Crash-style CSS class cycling) =====
const BEHAVIORS = [
  { cls:'idle-look',    dur:2400 },
  { cls:'idle-stretch', dur:2200 },
  { cls:'idle-bounce',  dur:1700 },
  { cls:'idle-proud',   dur:2400 },
  { cls:'idle-wobble',  dur:2000 },
  { cls:'idle-glance',  dur:2800 },
  { cls:'idle-shake',   dur:1800 },
];
const COMBAT_BEHAVIORS = [
  { cls:'idle-surge',   dur:2200 },
  { cls:'idle-intim',   dur:2800 },
  { cls:'idle-look',    dur:2400 },
  { cls:'idle-wobble',  dur:2000 },
];
var _cssIdleGen = 0;

function runCycle(el, seq, offset) {
  var myGen = ++_cssIdleGen;
  var current = '';
  var lastIdx = -1;
  function tick() {
    if (_cssIdleGen !== myGen) return;
    if (current) el.classList.remove(current);
    // Pick random animation, avoid repeating same twice in a row
    var idx;
    do { idx = Math.floor(Math.random() * seq.length); } while (idx === lastIdx && seq.length > 1);
    lastIdx = idx;
    var s = seq[idx];
    current = s.cls;
    el.classList.add(s.cls);
    // Gap: 120–280ms between animations — always alive, never static
    var gap = 120 + Math.floor(Math.random() * 160);
    setTimeout(tick, s.dur + gap);
  }
  setTimeout(tick, offset ? (offset * 500) : 0);
}

// ===== IDLE ANIMATION LOOP =====
var idleLoop = null;
const IDLE_REACTIONS = {
  spirit: [
    {fx:'aura',    args:['#7c6ef5'],  sp:['~...~','✦','...']},
    {fx:'blink',   args:[],           sp:['...','👀','~']},
    {fx:'tilt',    args:[4],          sp:['...','hmm','~']},
    {fx:'bounce',  args:[1.04,0,0],   sp:['...','~float~','☁️']},
    {fx:'particles',args:['#7c6ef5',3,0,360,22], sp:['✦','~','...']},
  ],
  beast: [
    {fx:'tilt',    args:[5],          sp:['...','*sniff*','~']},
    {fx:'bounce',  args:[1.05,3,0],   sp:['...','*twitch*','~']},
    {fx:'tilt',    args:[-4],         sp:['*ear*','~','...']},
  ],
  buddy: [
    {fx:'blink',   args:[],           sp:['STANDBY','...','~']},
    {fx:'tilt',    args:[3],          sp:['IDLE','...','~']},
    {fx:'bounce',  args:[1.03,0,0],   sp:['...','READY','~']},
  ],
};

function startIdleAnimation() {
  stopIdleAnimation();
  // JS effect loop (existing system)
  function scheduleNext() {
    var delay = 5000 + Math.random() * 5000;
    idleLoop = setTimeout(function() {
      var art = document.getElementById('lexiArt');
      if (!art) { return; }
      var arch = state.petArchetype || 'spirit';
      var pool = IDLE_REACTIONS[arch] || IDLE_REACTIONS.spirit;
      var entry = pool[Math.floor(Math.random() * pool.length)];
      var rect = art.getBoundingClientRect();
      executeReaction(entry, art, rect.left + rect.width/2, rect.top + rect.height/2);
      if (Math.random() < 0.35) updateLexiSpeech(entry.sp[Math.floor(Math.random()*entry.sp.length)]);
      scheduleNext();
    }, delay);
  }
  scheduleNext();
  // CSS class cycling (preview6 idle personality system)
  var art = document.getElementById('lexiArt');
  if (art) {
    var wrap = art.querySelector('[class*="-wrap"]');
    if (wrap) {
      var charId = state.petCharacter || '';
      var combatChars = ['vex', 'seraph', 'ronin'];
      var humanChars  = ['kaito', 'yuki'];
      var seq;
      if (combatChars.indexOf(charId) >= 0) {
        seq = COMBAT_BEHAVIORS;
      } else if (humanChars.indexOf(charId) >= 0) {
        seq = [BEHAVIORS[0], BEHAVIORS[3], BEHAVIORS[5], BEHAVIORS[6], BEHAVIORS[1]];
      } else {
        seq = BEHAVIORS;
      }
      runCycle(wrap, seq, 0);
    }
  }
}

function stopIdleAnimation() {
  if (idleLoop) { clearTimeout(idleLoop); idleLoop = null; }
  _cssIdleGen++; // invalidate any running CSS cycle
}

function animateLexi(anim) {
  const art = document.getElementById('lexiArt');
  if (!art) return;
  if (anim === 'eat' || anim === 'bounce') {
    art.style.transition = 'transform 0.2s';
    art.style.transform = anim === 'eat' ? 'scale(1.2)' : 'scale(1.15) rotate(8deg)';
    setTimeout(function() {
      art.style.transform = '';
      setTimeout(function() { art.style.transition = ''; }, 200);
    }, 220);
  }
  if (anim === 'eat') {
    FX.tap(art);
  }
}

function updateLexiSpeech(text) {
  const el = document.getElementById('lexiSpeech');
  if (el) {
    el.style.opacity = '0';
    setTimeout(function() { el.textContent = text; el.style.opacity = '1'; }, 200);
  }
}

async function triggerFeed() {
  haptic('medium');
  if (!state.lessonDoneToday) { showToast('Спочатку пройди урок!', 'fail'); return; }
  if (state.feedableWords.length === 0) { showToast('Немає слів для годування! Пройди урок.', 'fail'); return; }
  switchTab('lesson');
  showToast('Перетягни слова на Лексика! 🍎', 'success');
}

async function triggerPlay() {
  haptic('medium');
  if (!state.lesson) {
    showToast('Спочатку завантаж урок!', 'fail');
    switchTab('lesson');
    return;
  }
  switchTab('lesson');
  setTimeout(function() { startQuiz(); }, 300);
  animateLexi('bounce');
  updateLexiSpeech('Грати! Дай мені питання! 🎮');
}

async function triggerTalk() {
  haptic('medium');
  await apiCall('/api/interact/pet', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ tg_id: state.user?.tg_id || 999999, action: 'talk' }),
  }, null);

  animateLexi('bounce');
  const phrases = [
    'Привіт! Як справи? 💬',
    'Ти знаєш слово "serendipity"? 😏',
    '"To be or not to be" — це вже не для тебе, ти вище! 🌟',
    'Сьогодні вчимо щось нове? 📚',
    'Я скучив за тобою!',
  ];
  updateLexiSpeech(phrases[Math.floor(Math.random() * phrases.length)]);
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// ===== FEED WORD =====
async function feedWordToLexi(word) {
  if (state.fedWords.includes(word)) {
    showToast('"' + word + '" вже нагодовано!', 'fail');
    return;
  }

  state.fedWords.push(word);
  if (!state.wordsLearned.includes(word)) state.wordsLearned.push(word);
  state.xp += 5;
  saveLocal();

  const artEl = document.getElementById('lexiArt');
  FX.feed(word, artEl, state.topic);
  animateLexi('eat');
  const topicPhrases = {
    travel:     ['"' + word + '" — до нової пригоди! ✈️', 'Слово мандрівника! 🗺️'],
    work:       ['"' + word + '" — продуктивне слово! 💼', 'Корпоративний словник +1 💻'],
    emotions:   ['"' + word + '" — відчуваю це! ❤️', 'Слова почуттів найсмачніші! 🌈'],
    technology: ['"' + word + '" — завантажено! 🤖', 'Tech-upgrade: +5 XP! ⚡'],
    everyday:   ['"' + word + '" засвоєно! Я росту! 🌱'],
    mixed:      ['"' + word + '"! Рідкісне слово, +5 XP! ⭐'],
  };
  const basePool = ['Мммм! "' + word + '" — смачне слово! 😋', 'Хм, "' + word + '"... Цікаво! Давай ще!'];
  const topicPool = topicPhrases[state.topic] || [];
  const allPool = basePool.concat(topicPool);
  updateLexiSpeech(allPool[Math.floor(Math.random() * allPool.length)]);

  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
  showToast('"' + word + '" → Лексик з\'їв! +5 XP ✨', 'success');
  updateHeader();
  // Track words learned today for daily task
  var wToday = JSON.parse(localStorage.getItem('voodoo_words_today') || '{"date":"","count":0}');
  var today = new Date().toISOString().slice(0,10);
  if (wToday.date !== today) wToday = { date: today, count: 0 };
  wToday.count++;
  localStorage.setItem('voodoo_words_today', JSON.stringify(wToday));
  if (wToday.count >= 3) markTaskDone('word');

  await checkEvolution();

  apiCall('/api/progress', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tg_id: state.user?.tg_id || 999999,
      event_type: 'feed',
      xp_earned: 5,
      words_learned: [word],
    }),
  });
}

// ===== LESSON TAB =====
async function renderLesson() {
  document.getElementById('main').innerHTML = '<div class="loading-screen"><div class="spinner"></div><p>Завантажую урок...</p></div>';

  if (!state.lesson) state.lesson = await fetchLesson();

  renderLessonContent();
}

function renderLessonContent() {
  const lesson = state.lesson;
  if (!lesson) return;

  state.feedableWords = lesson.words.map(function(w) { return w.word; });

  const wordsHTML = lesson.words.map(function(w, i) {
    return '<div class="word-card-new fade-in" style="animation-delay:' + (i * 0.1) + 's">' +
      '<div class="word-header">' +
        '<span class="word-en">' + w.word + '</span>' +
        '<span class="word-num">' + (i+1) + '/3</span>' +
      '</div>' +
      '<div class="word-audio-row">' +
        audioBtn(w.word, 'Слово', 'en-US') +
        audioBtn(w.example, 'Речення', 'en-US') +
      '</div>' +
      '<div class="word-transcription">' + w.transcription + '</div>' +
      '<div class="word-translation">' + w.translation + '</div>' +
      '<div class="word-example" onclick="speakSentence(\'' + w.example.replace(/'/g,"\\'") + '\')" style="cursor:pointer">🔊 "' + w.example + '"</div>' +
      '<div class="word-example-ua">' + w.example_ua + '</div>' +
    '</div>';
  }).join('');

  const idiom = lesson.idiom;
  const idiomHTML =
    '<div class="idiom-card-new fade-in">' +
      '<div class="idiom-quote" onclick="speakText(\'' + idiom.text.replace(/'/g,"\\'") + '\',\'en-US\')" style="cursor:pointer">🔊 "' + idiom.text + '"</div>' +
      '<div class="word-audio-row">' +
        audioBtn(idiom.text, 'Ідіому', 'en-US') +
        audioBtn(idiom.example, 'Приклад', 'en-US') +
      '</div>' +
      '<div class="idiom-ua">🇺🇦 ' + idiom.translation + '</div>' +
      '<div class="idiom-example">"' + idiom.example + '"</div>' +
      '<div class="idiom-example-ua">' + idiom.example_ua + '</div>' +
    '</div>';

  const storyHTML =
    '<div class="word-card-new fade-in" style="background: linear-gradient(135deg, rgba(124,110,245,0.08), rgba(30,30,40,1))">' +
      '<div class="section-title" style="margin-top:0">📖 Mini Story</div>' +
      '<div style="font-size:14px;line-height:1.6;font-style:italic;color:var(--text2)">"' + lesson.mini_story + '"</div>' +
      '<div style="font-size:12px;margin-top:8px;color:var(--text2);opacity:0.7">' + lesson.mini_story_ua + '</div>' +
    '</div>';

  const dragWordsHTML = lesson.words.map(function(w) {
    return '<div class="draggable-word"' +
      ' draggable="true"' +
      ' data-word="' + w.word + '"' +
      ' ontouchstart="touchStart(event,this)"' +
      ' ontouchmove="touchMove(event)"' +
      ' ontouchend="touchEnd(event,this)"' +
      ' ondragstart="dragStart(event,this)"' +
      ' onclick="tapFeedWord(\'' + w.word + '\')">' +
      w.word + ' <span style="color:var(--text2);font-size:12px">' + w.translation + '</span>' +
    '</div>';
  }).join('');

  const feedZoneHTML =
    '<div class="section-title">🍎 Нагодуй Лексика</div>' +
    '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px">' + dragWordsHTML + '</div>' +
    '<div class="feed-zone" id="feedZone"' +
      ' ondragover="event.preventDefault();this.classList.add(\'drag-over\')"' +
      ' ondragleave="this.classList.remove(\'drag-over\')"' +
      ' ondrop="dropOnLexi(event)">' +
      '<div class="feed-zone-icon">🥚</div>' +
      '<div class="feed-zone-text">Перетягни слово на Лексика</div>' +
      '<div class="feed-zone-sub">або просто натисни на слово</div>' +
    '</div>';

  const actionButtons = state.lessonDoneToday
    ? '<button class="btn-secondary" onclick="startQuiz()">🧠 Пройти тест ще раз</button>'
    : '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="startQuiz()">🧠 Тест</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="markAllLearned()">✅ Вивчив</button>' +
      '</div>';

  document.getElementById('main').innerHTML =
    '<div class="section-title">📚 Слова дня</div>' +
    wordsHTML +
    '<div class="section-title">💬 Idiom дня</div>' +
    idiomHTML +
    storyHTML +
    feedZoneHTML +
    '<div style="margin-top:16px">' + actionButtons + '</div>';
}

// ===== DRAG & DROP =====
var draggedWord = null;

function dragStart(event, el) {
  draggedWord = el.dataset.word;
  event.dataTransfer.effectAllowed = 'move';
}

function dropOnLexi(event) {
  event.preventDefault();
  var fz = document.getElementById('feedZone');
  if (fz) fz.classList.remove('drag-over');
  if (draggedWord) {
    feedWordToLexi(draggedWord);
    draggedWord = null;
  }
}

var touchStartEl = null;
function touchStart(event, el) { touchStartEl = el; }
function touchMove(event) { event.preventDefault(); }
function touchEnd(event, el) {
  var word = el && el.dataset && el.dataset.word;
  if (word) tapFeedWord(word);
}

function tapFeedWord(word) {
  feedWordToLexi(word);
}

// ===== QUIZ =====
function startQuiz() {
  const lesson = state.lesson;
  if (!lesson || !lesson.quiz) { showToast('Завантаж урок спочатку!', 'fail'); return; }

  state.quizState = {
    questions: lesson.quiz,
    index: 0,
    score: 0,
  };
  renderQuizQuestion();
}

function renderQuizQuestion() {
  const qs = state.quizState;
  if (!qs || qs.index >= qs.questions.length) {
    renderQuizResult();
    return;
  }

  const q = qs.questions[qs.index];
  const optionsHTML = q.answers.map(function(a, i) {
    return '<button class="quiz-option" onclick="answerQuiz(' + i + ')">' + a + '</button>';
  }).join('');

  // Auto-speak the question word if it's a "What does X mean?" type
  const qWordMatch = q.question.match(/^(?:Що означає|What does) ["«»]?([a-zA-Z\s]+)["«»]?/i);

  document.getElementById('main').innerHTML =
    '<div class="quiz-progress">' + (qs.index + 1) + ' / ' + qs.questions.length + '</div>' +
    '<div class="quiz-card-new fade-in">' +
      '<div class="quiz-q">' + q.question +
        (qWordMatch ? ' ' + audioBtn(qWordMatch[1].trim(), '', 'en-US') : '') +
      '</div>' +
      '<div class="quiz-options">' + optionsHTML + '</div>' +
    '</div>';

  if (qWordMatch) setTimeout(function() { speakWord(qWordMatch[1].trim()); }, 400);
}

function answerQuiz(idx) {
  const qs = state.quizState;
  if (!qs || qs._answered) return;  // prevent double-tap
  qs._answered = true;

  const q = qs.questions[qs.index];
  const correct = q.correct;

  // Validate correct index is in range
  const btns = document.querySelectorAll('.quiz-option');
  if (correct < 0 || correct >= btns.length) { qs._answered = false; return; }

  btns.forEach(function(b) { b.onclick = null; b.disabled = true; });
  btns[correct].classList.add('correct');
  if (idx !== correct) {
    if (idx >= 0 && idx < btns.length) btns[idx].classList.add('wrong');
  }

  const isCorrect = idx === correct;
  if (isCorrect) {
    qs.score++;
    haptic('success');
  } else {
    haptic('error');
  }

  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn-primary';
  nextBtn.style.marginTop = '16px';
  nextBtn.textContent = qs.index + 1 < qs.questions.length ? '➡️ Далі' : '🏁 Результат';
  nextBtn.onclick = function() {
    nextBtn.disabled = true;  // prevent double-click
    qs.index++;
    qs._answered = false;
    renderQuizQuestion();
  };
  var card = document.querySelector('.quiz-card-new');
  if (card) card.appendChild(nextBtn);
}

function renderQuizResult() {
  const qs = state.quizState;
  if (!qs) return;
  const score = qs.score;
  const total = qs.questions.length;
  const xpEarned = score * 15;
  state.xp += xpEarned;
  state.lessonDoneToday = true;
  saveLocal();
  updateHeader();
  markTaskDone('lesson');

  const stars = '⭐'.repeat(score) + '☆'.repeat(total - score);
  const msgs = {3:'Ідеально! 🎉', 2:'Добре! 💪', 1:'Майже! Ще раз?', 0:'Не засмучуйся, спробуй ще!'};

  animateLexi(score === total ? 'bounce' : 'idle');
  updateLexiSpeech(score === total ? 'Ідеальний тест! Ти крутий! 🌟' : 'Продовжуй практикуватись!');

  document.getElementById('main').innerHTML =
    '<div class="word-card-new fade-in" style="text-align:center;padding:32px">' +
      '<div style="font-size:48px;margin-bottom:12px">' + (score === total ? '🏆' : score >= 2 ? '💪' : '📚') + '</div>' +
      '<div style="font-size:32px;margin-bottom:8px">' + stars + '</div>' +
      '<div style="font-size:22px;font-weight:800;margin-bottom:4px">' + score + '/' + total + '</div>' +
      '<div style="color:var(--text2);margin-bottom:16px">' + (msgs[score] || 'Добре!') + '</div>' +
      '<div style="color:var(--accent2);font-size:18px;font-weight:700;margin-bottom:24px">+' + xpEarned + ' XP</div>' +
      '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="renderLessonContent()">📚 Урок</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="switchTab(\'home\')">🏠 Дім</button>' +
      '</div>' +
    '</div>';

  apiCall('/api/progress', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tg_id: state.user?.tg_id || 999999,
      event_type: 'quiz',
      xp_earned: xpEarned,
      words_learned: state.lesson ? state.lesson.words.map(function(w) { return w.word; }) : [],
      data: { correct_count: score, all_correct: score === total },
    }),
  });

  checkEvolution();
  maybePromptHomeScreen();
}

async function markAllLearned() {
  const words = state.lesson ? state.lesson.words.map(function(w) { return w.word; }) : [];
  words.forEach(function(w) { if (!state.wordsLearned.includes(w)) state.wordsLearned.push(w); });
  state.xp += 20;
  state.lessonDoneToday = true;
  state.feedableWords = words;
  saveLocal();
  updateHeader();
  showToast('✅ Слова збережено! +20 XP', 'success');
  animateLexi('bounce');

  apiCall('/api/progress', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      tg_id: state.user?.tg_id || 999999,
      event_type: 'lesson',
      xp_earned: 20,
      words_learned: words,
    }),
  });

  await checkEvolution();
  maybePromptHomeScreen();
  renderLessonContent();
}

// ===== REVIEW TAB =====
async function renderReview() {
  if (state.wordsLearned.length < 3) {
    document.getElementById('main').innerHTML =
      '<div class="word-card-new" style="text-align:center;padding:32px">' +
        '<div style="font-size:48px;margin-bottom:12px">📚</div>' +
        '<div style="font-size:18px;font-weight:700;margin-bottom:8px">Ще замало слів</div>' +
        '<div style="color:var(--text2);margin-bottom:20px">Вивчи мінімум 3 слова для повторення.<br>Зараз: ' + state.wordsLearned.length + ' слів.</div>' +
        '<button class="btn-primary" onclick="switchTab(\'lesson\')">📚 Перейти до уроку</button>' +
      '</div>';
    return;
  }

  const pool = [...state.wordsLearned].sort(function() { return 0.5 - Math.random(); }).slice(0, 5);
  const wrongPool = ['time','place','mind','heart','power','dream','light','money','skill','hope'];

  // Use lesson words for translations if available
  const wordTranslations = {};
  if (state.lesson && state.lesson.words) {
    state.lesson.words.forEach(function(w) { wordTranslations[w.word] = w.translation; });
  }

  const questions = pool.map(function(word) {
    const wrongs = wrongPool.filter(function(w) { return w !== word; }).sort(function() { return 0.5 - Math.random(); }).slice(0, 3);
    const answers = [word].concat(wrongs).sort(function() { return 0.5 - Math.random(); });
    const transl = wordTranslations[word] || '?';
    return {
      question: 'Яке англійське слово означає "' + transl + '"?',
      wordHint: word,
      answers: answers,
      correct: answers.indexOf(word),
    };
  });

  state.quizState = { questions: questions, index: 0, score: 0 };
  renderQuizQuestion();
}

// ===== LEADERBOARD TAB =====
let lbMode = 'all'; // 'all' | 'weekly'

async function renderLeaderboard(mode) {
  if (mode) lbMode = mode;
  document.getElementById('main').innerHTML = '<div class="loading-screen"><div class="spinner"></div></div>';
  const tgId = state.user?.tg_id || 999999;

  const medals = {1:'🥇',2:'🥈',3:'🥉'};

  let list, myXpLabel, subtitle;
  if (lbMode === 'weekly') {
    const resp = await apiCall('/api/leaderboard/weekly?tg_id=' + tgId, {}, {board:[], my_weekly_xp:0});
    const board = (resp && resp.board) || [];
    const myWeekly = (resp && resp.my_weekly_xp) || 0;
    list = board.length ? board.map(function(u, i) {
      return {rank: i+1, first_name: u.first_name, xp: u.weekly_xp, streak: u.streak, is_me: u.tg_id === tgId};
    }) : [{rank:1, first_name:'Будь першим!', xp:0, streak:0, is_me:false}];
    myXpLabel = 'Твій XP цього тижня: ' + myWeekly;
    subtitle = 'Скидається щопонеділка';
  } else {
    // Context leaderboard: top 5 + user's neighbors
    const ctx = await apiCall('/api/leaderboard/context?tg_id=' + tgId, {}, {top5:[], neighbors:[], my_rank:null, total_users:0});
    const top5 = (ctx && ctx.top5) || [];
    const neighbors = (ctx && ctx.neighbors) || [];
    const myRank = ctx && ctx.my_rank;
    const total = ctx && ctx.total_users;

    function lbRow(u) {
      const rankClass = u.rank===1?'gold':u.rank===2?'silver':u.rank===3?'bronze':'';
      const rankDisplay = medals[u.rank] || '#' + u.rank;
      return '<div class="lb-item ' + (u.is_me ? 'is-me' : '') + '">' +
        '<div class="lb-rank ' + rankClass + '">' + rankDisplay + '</div>' +
        '<div class="lb-name">' + (u.first_name || '?') + (u.is_me ? ' 👈' : '') + '</div>' +
        '<div class="lb-xp">⭐' + (u.xp||0) + ' | 🔥' + (u.streak||0) + '</div>' +
      '</div>';
    }

    const top5HTML = top5.map(lbRow).join('');
    const gapHTML = (neighbors.length && myRank > 5)
      ? '<div class="lb-gap">· · · · · · <span style="font-size:10px;color:var(--text2)">позиція #' + myRank + ' з ' + total + '</span> · · · · · ·</div>'
      : '';
    const neighborsHTML = neighbors.map(lbRow).join('');

    list = top5; // keep for fallback
    myXpLabel = myRank ? 'Твоя позиція: <b>#' + myRank + '</b> з ' + total + ' | XP: ' + state.xp : 'Твій XP: ' + state.xp;
    subtitle = 'Загальний рейтинг';

    document.getElementById('main').innerHTML =
      '<div class="section-title">🏆 Топ гравців</div>' +
      '<div class="leaderboard-tabs">' +
        '<button class="lb-tab ' + (lbMode==='all'?'active':'') + '" onclick="renderLeaderboard(\'all\')">🏅 Всі часи</button>' +
        '<button class="lb-tab ' + (lbMode==='weekly'?'active':'') + '" onclick="renderLeaderboard(\'weekly\')">📅 Тиждень</button>' +
      '</div>' +
      '<div style="font-size:11px;color:var(--text2);text-align:center;margin-bottom:8px">' + subtitle + '</div>' +
      '<div class="lb-list">' + top5HTML + gapHTML + neighborsHTML + '</div>' +
      '<div style="font-size:12px;text-align:center;color:var(--accent2);margin-top:8px">' + myXpLabel + '</div>' +
      '<div class="premium-banner" style="margin-top:16px">' +
        '<div class="p-star">🏆</div>' +
        '<div class="p-content">' +
          '<div class="p-title">Перше місце = Telegram Premium</div>' +
          '<div class="p-sub">Нараховується щомісяця.</div>' +
        '</div>' +
      '</div>';
    return;
  }

  const itemsHTML = list.map(function(u) {
    const rankClass = u.rank===1?'gold':u.rank===2?'silver':u.rank===3?'bronze':'';
    const rankDisplay = medals[u.rank] || u.rank;
    return '<div class="lb-item ' + (u.is_me ? 'is-me' : '') + '">' +
      '<div class="lb-rank ' + rankClass + '">' + rankDisplay + '</div>' +
      '<div class="lb-name">' + u.first_name + (u.is_me ? ' 👈' : '') + '</div>' +
      '<div class="lb-xp">⭐' + u.xp + ' | 🔥' + u.streak + '</div>' +
    '</div>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="section-title">🏆 Топ гравців</div>' +
    '<div class="leaderboard-tabs">' +
      '<button class="lb-tab ' + (lbMode==='all'?'active':'') + '" onclick="renderLeaderboard(\'all\')">🏅 Всі часи</button>' +
      '<button class="lb-tab ' + (lbMode==='weekly'?'active':'') + '" onclick="renderLeaderboard(\'weekly\')">📅 Тиждень</button>' +
    '</div>' +
    '<div style="font-size:11px;color:var(--text2);text-align:center;margin-bottom:8px">' + subtitle + '</div>' +
    '<div class="lb-list">' + itemsHTML + '</div>' +
    '<div style="font-size:12px;text-align:center;color:var(--accent2);margin-top:8px">' + myXpLabel + '</div>' +
    '<div class="premium-banner" style="margin-top:16px">' +
      '<div class="p-star">🏆</div>' +
      '<div class="p-content">' +
        '<div class="p-title">Перше місце = Telegram Premium</div>' +
        '<div class="p-sub">Нараховується щомісяця.</div>' +
      '</div>' +
    '</div>';
}

// ===== REWARDS HELPERS =====
const SKIN_DEFS = {
  base:   { name: 'Base',   req: 0,   color: 'radial-gradient(circle at 35% 35%,#c0b0ff,#5a47e8)', shadow: 'rgba(124,110,245,0.5)' },
  ice:    { name: 'Ice',    req: 30,  color: 'radial-gradient(circle at 35% 35%,#e0f0ff,#80b8f0)', shadow: 'rgba(128,184,240,0.5)' },
  gold:   { name: 'Gold',   req: 60,  color: 'radial-gradient(circle at 35% 35%,#ffe080,#c88020)', shadow: 'rgba(245,200,66,0.5)' },
  cosmic: { name: 'Cosmic', req: 100, color: 'radial-gradient(circle at 35% 35%,#ff80f0,#7020c0)', shadow: 'rgba(128,32,192,0.5)' },
};

function renderSkinItem(id, unlocked, isActive) {
  const s = SKIN_DEFS[id];
  const cls = 'skin-item' + (isActive ? ' active' : '') + (!unlocked ? ' locked-skin' : '');
  const tag = isActive ? '<div class="skin-active-tag">Активний</div>' : (!unlocked ? '<div class="skin-req">🔒 ' + s.req + ' слів</div>' : '<div style="font-size:10px;color:var(--accent2)">Розблоковано</div>');
  return '<div class="' + cls + '" onclick="' + (unlocked ? 'selectSkin(\'' + id + '\')' : '') + '">' +
    '<div class="skin-preview" style="background:' + s.color + ';box-shadow:0 0 16px ' + s.shadow + '"></div>' +
    '<div class="skin-name">' + s.name + '</div>' +
    tag +
  '</div>';
}

function renderAccItem(icon, name, unlocked) {
  const cls = 'acc-item' + (unlocked ? ' owned' : ' locked-acc');
  return '<div class="' + cls + '">' +
    '<div class="acc-icon">' + icon + '</div>' +
    '<div class="acc-name">' + name + '</div>' +
    (!unlocked ? '<div style="font-size:9px;color:var(--text2)">🔒</div>' : '') +
  '</div>';
}

function selectSkin(id) {
  state.activeSkin = id;
  saveLocal();
  showToast('Скін "' + SKIN_DEFS[id].name + '" активовано!', 'success');
  renderProfile();
}

// ===== PROFILE TAB =====
async function renderProfile() {
  const stage = LEXI_STAGES[state.lexiStage] || LEXI_STAGES[0];
  const xp = state.xp;
  const words = state.wordsLearned.length;
  let rankLabel = '🌱 Новачок';
  const rankLevels = [[1000,'👑 Майстер'],[500,'💎 Експерт'],[200,'🔥 Практик'],[50,'⚡ Учень']];
  for (let ri = 0; ri < rankLevels.length; ri++) {
    if (xp >= rankLevels[ri][0]) { rankLabel = rankLevels[ri][1]; break; }
  }

  const badges = await apiCall('/api/badges?tg_id=' + (state.user?.tg_id || 999999), {}, []);
  const badgesHTML = (badges && badges.length) ? badges.map(function(b) {
    return '<div class="badge-item ' + (b.unlocked ? '' : 'locked') + '">' +
      '<div class="badge-icon">' + b.icon + '</div>' +
      '<div class="badge-name">' + b.name + '</div>' +
    '</div>';
  }).join('') : '';

  const topics = [
    {key:'everyday',label:'Повсякденне',icon:'💬'},
    {key:'work',label:'Робота',icon:'💼'},
    {key:'travel',label:'Подорожі',icon:'✈️'},
    {key:'emotions',label:'Емоції',icon:'❤️'},
    {key:'technology',label:'Технології',icon:'💻'},
    {key:'mixed',label:'Мікс',icon:'🎲'},
  ];
  const levels = ['A1','A2','B1','B2'];

  const tgUser = tg?.initDataUnsafe?.user;
  const avatarEmoji = stage.emoji;
  const userName = (state.user && state.user.first_name) || (tgUser && tgUser.first_name) || 'Гравець';

  document.getElementById('main').innerHTML =
    '<div class="profile-section">' +
      '<div class="profile-head">' +
        '<div class="profile-avatar">' + avatarEmoji + '</div>' +
        '<div class="profile-name">' + userName + '</div>' +
        '<div class="profile-rank">' + rankLabel + '</div>' +
        '<div class="profile-companion-row">' +
          '<span class="profile-companion-label">Компаньон:</span>' +
          '<span class="profile-companion-name">' + (state.companionName || 'ЛЕКСИК') + '</span>' +
          '<button class="rename-btn" onclick="startRenameCompanion()">✏️ Перейменувати</button>' +
        '</div>' +
      '</div>' +
      '<div class="stats-row">' +
        '<div class="stat-box"><div class="stat-num">' + state.streak + '</div><div class="stat-label">Streak</div></div>' +
        '<div class="stat-box"><div class="stat-num">' + state.wordsLearned.length + '</div><div class="stat-label">Слів</div></div>' +
        '<div class="stat-box"><div class="stat-num">' + state.xp + '</div><div class="stat-label">XP</div></div>' +
      '</div>' +
      '<div class="section-title">🏅 Досягнення</div>' +
      '<div class="badges-grid">' + (badgesHTML || '<span style="color:var(--text2);font-size:13px">Пройди перший урок!</span>') + '</div>' +
      '<div class="section-title">🎯 Тема</div>' +
      '<div style="display:flex;flex-wrap:wrap;gap:8px">' +
        topics.map(function(t) {
          return '<button class="topic-pill ' + (state.topic === t.key ? 'active' : '') + '" onclick="setTopic(\'' + t.key + '\',this)">' + t.icon + ' ' + t.label + '</button>';
        }).join('') +
      '</div>' +
      '<div class="section-title">📊 Рівень</div>' +
      '<div style="display:flex;gap:8px">' +
        levels.map(function(l) {
          return '<button class="level-pill ' + (state.level === l ? 'active' : '') + '" onclick="setLevel(\'' + l + '\',this)">' + l + '</button>';
        }).join('') +
      '</div>' +
      '<div style="height:8px"></div>' +
    '</div>' +

    // ===== REWARDS SECTION =====
    '<div class="rewards-section">' +
      '<div class="rewards-title">🔥 Активні Boosts</div>' +
      '<div class="boost-row">' +
        '<div class="boost-item ' + (state.xp >= 50 ? 'active' : '') + '">' +
          '<div class="boost-icon">⚡</div>' +
          '<div class="boost-name">2x XP</div>' +
          '<div class="' + (state.xp >= 50 ? 'boost-time' : 'boost-inactive') + '">' + (state.xp >= 50 ? 'Активний' : 'Заблоковано') + '</div>' +
        '</div>' +
        '<div class="boost-item">' +
          '<div class="boost-icon">🛡️</div>' +
          '<div class="boost-name">Streak Shield</div>' +
          '<div class="boost-inactive">7-Day Streak</div>' +
        '</div>' +
        '<div class="boost-item">' +
          '<div class="boost-icon">🎯</div>' +
          '<div class="boost-name">Focus Mode</div>' +
          '<div class="boost-inactive">10 Уроків</div>' +
        '</div>' +
        '<div class="boost-item">' +
          '<div class="boost-icon">🌟</div>' +
          '<div class="boost-name">Rare Words</div>' +
          '<div class="boost-inactive">50 Слів</div>' +
        '</div>' +
      '</div>' +
    '</div>' +

    '<div class="rewards-section">' +
      '<div class="rewards-title">✨ Скіни Лексика</div>' +
      '<div class="skins-row">' +
        renderSkinItem('base',   words >= 0,  true) +
        renderSkinItem('ice',    words >= 30,  false) +
        renderSkinItem('gold',   words >= 60,  false) +
        renderSkinItem('cosmic', words >= 100, false) +
      '</div>' +
    '</div>' +

    '<div class="rewards-section">' +
      '<div class="rewards-title">🎩 Аксесуари</div>' +
      '<div class="accessories-grid">' +
        renderAccItem('👑', 'Корона',   words >= 10) +
        renderAccItem('🔮', 'Орб',      words >= 30) +
        renderAccItem('⚡', 'Аура',     words >= 60) +
        renderAccItem('🌙', 'Кільця',  words >= 100) +
      '</div>' +
    '</div>' +

    '<div class="rewards-section">' +
      '<div class="rewards-title">🔗 Запроси друга</div>' +
      '<div style="font-size:13px;color:var(--text2);margin-bottom:12px">Поділись посиланням і заробляйте разом!</div>' +
      '<button class="btn-secondary" style="width:100%" onclick="copyReferralLink()">📋 Скопіювати реферальне посилання</button>' +
    '</div>' +

    '<div style="height:32px"></div>';
}

function setTopic(topic, btn) {
  state.topic = topic;
  state.lesson = null;
  saveLocal();
  document.querySelectorAll('.topic-pill').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  showToast('Тему змінено: ' + topic, 'success');
  apiCall('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tg_id: state.user?.tg_id || 999999, topic: topic}),
  });
}

function setLevel(level, btn) {
  state.level = level;
  state.lesson = null;
  saveLocal();
  document.querySelectorAll('.level-pill').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  showToast('Рівень: ' + level, 'success');
  apiCall('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tg_id: state.user?.tg_id || 999999, level: level}),
  });
}

// ===== EVOLUTION POPUP =====
async function showEvoPopup(stage) {
  haptic('success');
  FX.levelUp(stage.stage);

  const popup = document.createElement('div');
  popup.className = 'evo-popup';
  popup.innerHTML =
    '<div class="evo-popup-card">' +
      '<div style="width:140px;height:140px;margin:0 auto 16px">' + buildCompanionHTML(stage.stage, state.petArchetype) + '</div>' +
      '<div style="color:var(--gold);font-size:24px;font-weight:800;margin-bottom:8px">' + (state.companionName || 'ЛЕКСИК').toUpperCase() + ' ЕВОЛЮЦІОНУВАВ!</div>' +
      '<div style="font-size:18px;font-weight:700;margin-bottom:4px">' + stage.name + '</div>' +
      '<div style="color:var(--text2);font-size:13px;margin-bottom:16px">' + stage.description + '</div>' +
      (stage.unlocks ? '<div style="color:var(--accent2);font-size:13px;font-weight:600;margin-bottom:20px">🔓 ' + stage.unlocks + '</div>' : '') +
      '<button class="btn-primary" onclick="this.closest(\'.evo-popup\').remove()">🎉 Круто!</button>' +
    '</div>';

  document.getElementById('app').appendChild(popup);
  setTimeout(function() { if (popup.parentNode) popup.remove(); }, 8000);
}

// ===== COMPANION CSS ART BUILDERS =====

function buildCompanionHTML(stageIdx, arch) {
  if (stageIdx === 0) return buildEggHTML();
  // Try specific character first
  const charBuilders = {
    lumix: buildLumixHTML, kitsune: buildKitsuneHTML, mochi: buildMochiHTML,
    byte: buildByteHTML, ember: buildEmberHTML, bruno: buildBrunoHTML,
    mist: buildMistHTML, marco: buildMarcoHTML, crash: buildCrashHTML,
    nova: buildNovaHTML, luna: buildLunaHTML, rex: buildRexHTML,
    sunny: buildSunnyHTML, biscuit: buildBiscuitHTML, ronin: buildRoninHTML,
    apex: buildApexHTML, bolt: buildBoltHTML,
    astro: buildAstroHTML, kaito: buildKaitoHTML, yuki: buildYukiHTML,
    vex: buildVexHTML, seraph: buildSeraphHTML,
  };
  const charId = state.petCharacter;
  if (charId && charBuilders[charId]) return charBuilders[charId](stageIdx);
  // Fallback to archetype
  const builders = { spirit: buildSpiritHTML, beast: buildBeastHTML, buddy: buildBuddyHTML };
  return (builders[arch] || builders.spirit)(stageIdx);
}

// ===== CHARACTER-SPECIFIC HTML BUILDERS =====

function _charScale(stageIdx) {
  // Returns a CSS scale transform string based on evolution stage
  const scales = [1, 1, 1.05, 1.12, 1.2, 1.3];
  return 'scale(' + (scales[stageIdx] || 1) + ')';
}

function buildLumixHTML(s) {
  const glow = s >= 4 ? '0 0 30px 12px rgba(167,139,250,0.85)' : s >= 3 ? '0 0 22px 8px rgba(167,139,250,0.7)' : '0 0 18px 6px rgba(167,139,250,0.7)';
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="lumix-wrap">' +
      '<div class="lumix-sparkle">✦</div>' +
      '<div class="lumix-sparkle">✧</div>' +
      (s >= 3 ? '<div class="lumix-sparkle">✦</div>' : '') +
      '<div class="lumix-glow"></div>' +
      '<div class="lumix-ear-l"><div class="lumix-ear-inner-l"></div></div>' +
      '<div class="lumix-ear-r"><div class="lumix-ear-inner-r"></div></div>' +
      '<div class="lumix-orb" style="box-shadow:' + glow + '"></div>' +
      '<div class="lumix-eyes">' +
        '<div class="lumix-eye"><div class="lumix-pupil"></div></div>' +
        '<div class="lumix-eye"><div class="lumix-pupil"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildKitsuneHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="kitsune-wrap">' +
      '<div class="kit-tail"></div>' +
      '<div class="kit-leg-l"><div class="kit-foot-l"></div></div>' +
      '<div class="kit-leg-r"><div class="kit-foot-r"></div></div>' +
      '<div class="kit-body"><div class="kit-belly"></div></div>' +
      '<div class="kit-paw-l"></div>' +
      '<div class="kit-paw-r"></div>' +
      '<div class="kit-head">' +
        '<div class="kit-ear-l"><div class="kit-ear-inner-l"></div></div>' +
        '<div class="kit-ear-r"><div class="kit-ear-inner-r"></div></div>' +
        '<div class="kit-eye-l"><div class="kit-iris"><div class="kit-iris-hl"></div></div></div>' +
        '<div class="kit-eye-r"><div class="kit-iris"><div class="kit-iris-hl"></div></div></div>' +
        '<div class="kit-muzzle"><div class="kit-nose"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildMochiHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="mochi-wrap">' +
      '<div class="mochi-leg-l"></div>' +
      '<div class="mochi-leg-r"></div>' +
      '<div class="mochi-body"><div class="mochi-belly"></div></div>' +
      '<div class="mochi-head">' +
        '<div class="mochi-ear-l"><div class="mochi-ear-inner-l"></div></div>' +
        '<div class="mochi-ear-r"><div class="mochi-ear-inner-r"></div></div>' +
        '<div class="mochi-eye-l"><div class="mochi-eye-hl"></div></div>' +
        '<div class="mochi-eye-r"><div class="mochi-eye-hl"></div></div>' +
        '<div class="mochi-blush-l"></div>' +
        '<div class="mochi-blush-r"></div>' +
        '<div class="mochi-nose"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildByteHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="byte-wrap">' +
      '<div class="byte-antenna"></div>' +
      '<div class="byte-head">' +
        '<div class="byte-screen">' +
          '<div class="byte-led-eye-l"></div>' +
          '<div class="byte-led-eye-r"></div>' +
          '<div class="byte-smile"></div>' +
        '</div>' +
      '</div>' +
      '<div class="byte-arm-l"></div>' +
      '<div class="byte-arm-r"></div>' +
      '<div class="byte-body"></div>' +
      '<div class="byte-leg-l"><div class="byte-foot-l"></div></div>' +
      '<div class="byte-leg-r"><div class="byte-foot-r"></div></div>' +
    '</div>' +
  '</div>';
}

function buildEmberHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="ember-wrap">' +
      '<div class="ember-tail"></div>' +
      '<div class="ember-wing-l"></div>' +
      '<div class="ember-wing-r"></div>' +
      '<div class="ember-body"><div class="ember-belly"></div></div>' +
      '<div class="ember-leg-l"></div>' +
      '<div class="ember-leg-r"></div>' +
      '<div class="ember-head">' +
        '<div class="ember-horn-l"></div>' +
        '<div class="ember-horn-r"></div>' +
        '<div class="ember-eye-l"><div class="ember-iris"><div class="ember-iris-hl"></div></div></div>' +
        '<div class="ember-eye-r"><div class="ember-iris"><div class="ember-iris-hl"></div></div></div>' +
        '<div class="ember-nostril"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildBrunoHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="bruno-wrap">' +
      '<div class="bruno-strap-l"></div>' +
      '<div class="bruno-strap-r"></div>' +
      '<div class="bruno-backpack"></div>' +
      '<div class="bruno-leg-l"><div class="bruno-foot-l"></div></div>' +
      '<div class="bruno-leg-r"><div class="bruno-foot-r"></div></div>' +
      '<div class="bruno-body"><div class="bruno-belly"></div></div>' +
      '<div class="bruno-arm-l"></div>' +
      '<div class="bruno-arm-r"></div>' +
      '<div class="bruno-head">' +
        '<div class="bruno-ear-l"><div class="bruno-ear-inner-l"></div></div>' +
        '<div class="bruno-ear-r"><div class="bruno-ear-inner-r"></div></div>' +
        '<div class="bruno-eye-l"><div class="bruno-eye-hl"></div></div>' +
        '<div class="bruno-eye-r"><div class="bruno-eye-hl"></div></div>' +
        '<div class="bruno-muzzle"><div class="bruno-nose"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildMistHTML(s) {
  const glow = s >= 3 ? 'box-shadow:0 0 28px rgba(125,211,252,0.6),0 0 50px rgba(125,211,252,0.2)' : '';
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="mist-wrap">' +
      '<div class="mist-glow"></div>' +
      '<div class="mist-body" style="' + glow + '">' +
        '<div class="mist-moon"></div>' +
        '<div class="mist-eye-l"><div class="mist-eye-hl"></div></div>' +
        '<div class="mist-eye-r"><div class="mist-eye-hl"></div></div>' +
        '<div class="mist-blush-l"></div>' +
        '<div class="mist-blush-r"></div>' +
      '</div>' +
      '<div class="mist-bottom"><div class="mist-wave"></div></div>' +
    '</div>' +
  '</div>';
}

function buildMarcoHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="marco-wrap">' +
      '<div class="marco-hat"></div>' +
      '<div class="marco-hat-brim"></div>' +
      '<div class="marco-hat-band"></div>' +
      '<div class="marco-globe">' +
        '<div class="marco-gridline-h"></div>' +
        '<div class="marco-gridline-h"></div>' +
        '<div class="marco-gridline-h"></div>' +
        '<div class="marco-gridline-h"></div>' +
        '<div class="marco-gridline-v"></div>' +
        '<div class="marco-gridline-v"></div>' +
        '<div class="marco-gridline-v"></div>' +
        '<div class="marco-gridline-v"></div>' +
        '<div class="marco-face">' +
          '<div class="marco-eye-l"><div class="marco-eye-hl"></div></div>' +
          '<div class="marco-eye-r"><div class="marco-eye-hl"></div></div>' +
          '<div class="marco-smile"></div>' +
        '</div>' +
      '</div>' +
      '<div class="marco-stand"></div>' +
    '</div>' +
  '</div>';
}

function buildCrashHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="crash-wrap">' +
      '<div class="crash-shoe-l"></div>' +
      '<div class="crash-shoe-r"></div>' +
      '<div class="crash-jean-l"></div>' +
      '<div class="crash-jean-r"></div>' +
      '<div class="crash-arm-l"></div>' +
      '<div class="crash-arm-r"></div>' +
      '<div class="crash-glove-l"></div>' +
      '<div class="crash-glove-r"></div>' +
      '<div class="crash-body"></div>' +
      '<div class="crash-head">' +
        '<div class="crash-hair">' +
          '<div class="crash-spike"></div>' +
          '<div class="crash-spike"></div>' +
          '<div class="crash-spike"></div>' +
          '<div class="crash-spike"></div>' +
          '<div class="crash-spike"></div>' +
        '</div>' +
        '<div class="crash-brow-l"></div>' +
        '<div class="crash-brow-r"></div>' +
        '<div class="crash-eye-l"><div class="crash-iris-inner"></div><div class="crash-eye-hl1"></div><div class="crash-eye-hl2"></div></div>' +
        '<div class="crash-eye-r"><div class="crash-iris-inner"></div><div class="crash-eye-hl1"></div><div class="crash-eye-hl2"></div></div>' +
        '<div class="crash-blush-l"></div>' +
        '<div class="crash-blush-r"></div>' +
        '<div class="crash-snout"><div class="crash-mouth"><div class="crash-teeth"></div></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildNovaHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="nova-wrap">' +
      '<div class="nova-cape"></div>' +
      '<div class="nova-leg-l"></div>' +
      '<div class="nova-leg-r"></div>' +
      '<div class="nova-arm-l"></div>' +
      '<div class="nova-arm-r"></div>' +
      '<div class="nova-fist-l"></div>' +
      '<div class="nova-fist-r"></div>' +
      '<div class="nova-body"></div>' +
      '<div class="nova-head">' +
        '<div class="nova-crown">' +
          '<div class="nova-star"></div>' +
          '<div class="nova-star"></div>' +
          '<div class="nova-star"></div>' +
          '<div class="nova-star"></div>' +
          '<div class="nova-star"></div>' +
        '</div>' +
        '<div class="nova-eye-l"></div>' +
        '<div class="nova-eye-r"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildLunaHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="luna-wrap">' +
      '<div class="luna-tail"></div>' +
      '<div class="luna-leg-l"></div>' +
      '<div class="luna-leg-r"></div>' +
      '<div class="luna-paw-l"></div>' +
      '<div class="luna-paw-r"></div>' +
      '<div class="luna-body"></div>' +
      '<div class="luna-head">' +
        '<div class="luna-ear-l"></div>' +
        '<div class="luna-ear-r"></div>' +
        '<div class="luna-crescent"></div>' +
        '<div class="luna-eye-l"></div>' +
        '<div class="luna-eye-r"></div>' +
        '<div class="luna-nose"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildRexHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="rex-wrap">' +
      '<div class="rex-leg-l"></div>' +
      '<div class="rex-leg-r"></div>' +
      '<div class="rex-arm-l"></div>' +
      '<div class="rex-arm-r"></div>' +
      '<div class="rex-body"></div>' +
      '<div class="rex-head">' +
        '<div class="rex-eye-l"></div>' +
        '<div class="rex-eye-r"></div>' +
        '<div class="rex-blush-l"></div>' +
        '<div class="rex-blush-r"></div>' +
        '<div class="rex-mouth"><div class="rex-teeth"></div><div class="rex-teeth-low"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildSunnyHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="sunny-wrap">' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-ray"></div>' +
      '<div class="sunny-face">' +
        '<div class="sunny-eye-l"><div class="sunny-pupil"></div><div class="sunny-eye-hl"></div></div>' +
        '<div class="sunny-eye-r"><div class="sunny-pupil"></div><div class="sunny-eye-hl"></div></div>' +
        '<div class="sunny-nose"></div>' +
        '<div class="sunny-smile"></div>' +
        '<div class="sunny-blush-l"></div>' +
        '<div class="sunny-blush-r"></div>' +
      '</div>' +
      '<div class="sunny-hand-l"></div>' +
      '<div class="sunny-hand-r"></div>' +
    '</div>' +
  '</div>';
}

function buildBiscuitHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="biscuit-wrap">' +
      '<div class="biscuit-leg-l"></div>' +
      '<div class="biscuit-leg-r"></div>' +
      '<div class="biscuit-arm-l"></div>' +
      '<div class="biscuit-arm-r"></div>' +
      '<div class="biscuit-body">' +
        '<div class="biscuit-frosting"></div>' +
        '<div class="biscuit-eye-l"><div class="biscuit-eye-hl"></div></div>' +
        '<div class="biscuit-eye-r"><div class="biscuit-eye-hl"></div></div>' +
        '<div class="biscuit-nose"></div>' +
        '<div class="biscuit-blush-l"></div>' +
        '<div class="biscuit-blush-r"></div>' +
        '<div class="biscuit-mouth"><div class="biscuit-teeth"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildRoninHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="ronin-wrap">' +
      '<div class="ronin-hakama-l"></div>' +
      '<div class="ronin-hakama-r"></div>' +
      '<div class="ronin-arm-l"></div>' +
      '<div class="ronin-body"></div>' +
      '<div class="ronin-obi"></div>' +
      '<div class="ronin-arm-r"></div>' +
      '<div class="ronin-tsuka"></div>' +
      '<div class="ronin-head">' +
        '<div class="ronin-hair"></div>' +
        '<div class="ronin-eye-l"></div>' +
        '<div class="ronin-eye-r"></div>' +
        '<div class="ronin-mouth"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildApexHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="apex-wrap">' +
      '<div class="apex-boot-l"></div>' +
      '<div class="apex-boot-r"></div>' +
      '<div class="apex-leg-l"></div>' +
      '<div class="apex-leg-r"></div>' +
      '<div class="apex-arm-l"></div>' +
      '<div class="apex-arm-r"></div>' +
      '<div class="apex-body"></div>' +
      '<div class="apex-accent-1"></div>' +
      '<div class="apex-accent-2"></div>' +
      '<div class="apex-accent-3"></div>' +
      '<div class="apex-shoulder-l"></div>' +
      '<div class="apex-shoulder-r"></div>' +
      '<div class="apex-head">' +
        '<div class="apex-visor"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildBoltHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="bolt-wrap">' +
      '<div class="bolt-shoe-l"></div>' +
      '<div class="bolt-shoe-r"></div>' +
      '<div class="bolt-leg-l"></div>' +
      '<div class="bolt-leg-r"></div>' +
      '<div class="bolt-shorts"></div>' +
      '<div class="bolt-arm-l"></div>' +
      '<div class="bolt-arm-r"></div>' +
      '<div class="bolt-body">' +
        '<div class="bolt-lightning"></div>' +
      '</div>' +
      '<div class="bolt-head">' +
        '<div class="bolt-hair">' +
          '<div class="bolt-spike"></div>' +
          '<div class="bolt-spike"></div>' +
          '<div class="bolt-spike"></div>' +
          '<div class="bolt-spike"></div>' +
        '</div>' +
        '<div class="bolt-brow-l"></div>' +
        '<div class="bolt-brow-r"></div>' +
        '<div class="bolt-eye-l"><div class="bolt-iris"></div></div>' +
        '<div class="bolt-eye-r"><div class="bolt-iris"></div></div>' +
        '<div class="bolt-mouth"><div class="bolt-teeth"></div></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildEggHTML() {
  const crack = state.lessonDoneToday
    ? '<div class="egg-crack"></div>'
    : '';
  return '<div class="comp-egg">' +
    '<div class="egg-body">' + crack + '</div>' +
    '<div class="egg-shine"></div>' +
  '</div>';
}

function buildSpiritHTML(s) {
  const sz = [0,58,68,78,88,100][s] || 68;
  const glow = s >= 4 ? '#b840f0' : s >= 3 ? '#7040e8' : '#5a47e8';
  const wisps = s >= 2 ? '<div class="sp-wisp"></div><div class="sp-wisp"></div>' + (s >= 3 ? '<div class="sp-wisp"></div>' : '') : '';
  const wings = s >= 3 ? '<div class="sp-wing-l"></div><div class="sp-wing-r"></div>' : '';
  const crown = s >= 4 ? '<div class="sp-crown">👑</div>' : '';
  const chaos = s >= 5
    ? '<div class="sp-chaos-ring" style="width:110px;height:110px;transform:translate(-50%,-50%)"></div><div class="sp-chaos-ring" style="width:140px;height:140px;transform:translate(-50%,-50%);animation-direction:reverse;animation-duration:1.5s"></div>'
    : '';
  return '<div class="comp-spirit" onclick="onCompanionTap()">' +
    chaos +
    '<div class="sp-aura2"></div><div class="sp-aura"></div>' +
    wings +
    '<div class="sp-body" style="width:' + sz + 'px;height:' + sz + 'px;background:radial-gradient(circle at 35% 35%,#c0b0ff,' + glow + ' 55%,#2d1fa0);box-shadow:0 0 ' + (20+s*6) + 'px rgba(124,110,245,' + (0.5+s*0.08) + ');">' +
      '<div class="sp-eyes"><div class="sp-eye"></div><div class="sp-eye"></div></div>' +
      '<div class="sp-mouth"></div>' +
      wisps +
    '</div>' +
    crown +
    '<div class="sp-spark" style="top:8%;left:62%;animation-delay:0s">✦</div>' +
    '<div class="sp-spark" style="top:72%;left:12%;animation-delay:0.9s">✧</div>' +
    (s >= 2 ? '<div class="sp-spark" style="top:15%;right:8%;animation-delay:1.7s">✦</div>' : '') +
  '</div>';
}

function buildBeastHTML(s) {
  const sz = [0,56,65,74,82,92][s] || 65;
  const clr = s >= 4 ? '#c83010' : s >= 3 ? '#d84818' : '#e85e20';
  const horns = s >= 3
    ? '<div class="b-horn-l"></div><div class="b-horn-r"></div>'
    : '';
  const flame = s >= 4
    ? '<div class="b-flame" style="top:5%;left:20%;animation-delay:0s">🔥</div>' +
      '<div class="b-flame" style="top:8%;right:18%;animation-delay:0.5s">🔥</div>'
    : '';
  return '<div class="comp-beast" onclick="onCompanionTap()">' +
    horns +
    '<div class="b-ear-l"></div><div class="b-ear-r"></div>' +
    '<div class="b-body" style="width:' + sz + 'px;height:' + Math.round(sz*0.9) + 'px;background:radial-gradient(circle at 40% 35%,#ff9a5e,' + clr + ' 65%,#8a2800);">' +
      '<div class="b-eye-l"></div><div class="b-eye-r"></div>' +
      '<div class="b-nose"></div>' +
      '<div class="b-cheek-l"></div><div class="b-cheek-r"></div>' +
      '<div class="b-mouth"></div>' +
    '</div>' +
    '<div class="b-tail"></div>' +
    flame +
  '</div>';
}

function buildBuddyHTML(s) {
  const sz = [0,54,62,72,82,92][s] || 62;
  const vis = s >= 5
    ? 'bu-visor bu-visor-happy'
    : 'bu-visor';
  const visorW = Math.round(sz * 0.68);
  const panels = s >= 3
    ? '<div class="bu-panel" style="bottom:8%;left:8%;width:20px;height:12px"></div>' +
      '<div class="bu-panel" style="bottom:8%;right:8%;width:20px;height:12px"></div>'
    : '';
  const circuits = s >= 3
    ? '<div class="bu-circuit-line" style="top:30%;left:5%;width:8px;height:2px"></div>' +
      '<div class="bu-circuit-line" style="top:30%;right:5%;width:8px;height:2px;animation-delay:1.5s"></div>'
    : '';
  const neon = s >= 4 ? '<div class="bu-neon"></div>' : '';
  return '<div class="comp-buddy" onclick="onCompanionTap()">' +
    '<div class="bu-antenna"></div>' +
    '<div class="bu-body" style="width:' + sz + 'px;height:' + sz + 'px;border-radius:' + Math.round(sz*0.27) + 'px;border-color:rgba(94,231,176,' + (0.4+s*0.1) + ')">' +
      neon +
      '<div class="' + vis + '" style="width:' + visorW + 'px;top:28%"><div class="bu-visor-scan"></div></div>' +
      '<div class="bu-grill" style="width:' + Math.round(sz*0.5) + 'px;height:12px">' +
        '<div class="bu-grill-bar" style="height:6px"></div>' +
        '<div class="bu-grill-bar" style="height:8px"></div>' +
        '<div class="bu-grill-bar" style="height:6px"></div>' +
        '<div class="bu-grill-bar" style="height:8px"></div>' +
        '<div class="bu-grill-bar" style="height:6px"></div>' +
      '</div>' +
      panels + circuits +
    '</div>' +
  '</div>';
}

// ===== EFFECTS ENGINE =====

const FX = {
  tap(sourceEl) {
    if (!sourceEl) return;
    const rect = sourceEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const arch = state.petArchetype || 'spirit';
    const colors = { spirit: ['#7c6ef5','#a89cff','#5ee7b0'], beast: ['#ff7040','#f5c842','#ff4020'], buddy: ['#5ee7b0','#40c8f0','#a0d0ff'] };
    const ringColor = { spirit: 'rgba(124,110,245,', beast: 'rgba(255,112,64,', buddy: 'rgba(94,231,176,' };
    const rc = ringColor[arch] || ringColor.spirit;
    const cl = colors[arch] || colors.spirit;
    // Rings
    for (let i = 0; i < 3; i++) {
      const ring = document.createElement('div');
      ring.className = 'fx-ring';
      const size = 60 + i * 35;
      ring.style.cssText = 'width:' + size + 'px;height:' + size + 'px;border:2px solid ' + rc + (0.7 - i*0.2) + ');left:' + cx + 'px;top:' + cy + 'px;animation-delay:' + (i*0.1) + 's;animation-duration:' + (0.45+i*0.1) + 's';
      document.body.appendChild(ring);
      setTimeout(function() { ring.remove(); }, 700);
    }
    // Particles
    for (let i = 0; i < 9; i++) {
      const p = document.createElement('div');
      p.className = 'fx-particle';
      const size = 4 + Math.random() * 6;
      const angle = (i / 9) * 360;
      const dist = 35 + Math.random() * 35;
      const rad = angle * Math.PI / 180;
      p.style.cssText = 'width:' + size + 'px;height:' + size + 'px;background:' + cl[i%cl.length] + ';left:' + cx + 'px;top:' + cy + 'px;transform:translate(-50%,-50%)';
      document.body.appendChild(p);
      p.offsetHeight;
      p.style.transform = 'translate(calc(-50% + ' + (Math.cos(rad)*dist) + 'px),calc(-50% + ' + (Math.sin(rad)*dist) + 'px))';
      p.style.opacity = '0';
      setTimeout(function() { p.remove(); }, 700);
    }
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
  },

  feed(word, petEl, topic) {
    if (!petEl) return;
    const petRect = petEl.getBoundingClientRect();
    const px = petRect.left + petRect.width / 2;
    const py = petRect.top + petRect.height / 2;
    // Word chip flying to pet
    const chip = document.createElement('div');
    chip.className = 'fx-word-fly';
    chip.textContent = word;
    chip.style.cssText = 'left:' + (petRect.left - 80) + 'px;top:' + (py - 16) + 'px';
    document.body.appendChild(chip);
    chip.offsetHeight;
    chip.style.transform = 'translateX(' + (80 + petRect.width/2) + 'px) scale(0.3)';
    chip.style.opacity = '0';
    setTimeout(function() {
      chip.remove();
      // Absorption pulse on pet
      petEl.style.transition = 'transform 0.2s';
      petEl.style.transform = 'scale(1.25)';
      setTimeout(function() { petEl.style.transform = ''; }, 220);
      // Topic-themed XP float
      const topicIcons = { travel:'✈️ +5 XP', work:'💼 +5 XP', emotions:'❤️ +5 XP', technology:'⚡ +5 XP', everyday:'+5 XP', mixed:'+5 XP' };
      FX.xpFloat(px, py - 20, topicIcons[topic] || '+5 XP');
    }, 450);
  },

  tapArch(petEl, arch, chainCount) {
    if (!petEl) return;
    const rect = petEl.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    if (arch === 'spirit') {
      // Orbital rings — more rings per chain
      const ringCount = Math.min(chainCount + 1, 4);
      for (let i = 0; i < ringCount; i++) {
        const ring = document.createElement('div');
        ring.className = 'fx-ring';
        const size = 55 + i * 28;
        ring.style.cssText = 'width:' + size + 'px;height:' + size + 'px;border:2px solid rgba(124,110,245,' + (0.8-i*0.18) + ');left:' + cx + 'px;top:' + cy + 'px;animation-delay:' + (i*0.07) + 's;animation-duration:' + (0.38+i*0.09) + 's';
        document.body.appendChild(ring);
        setTimeout(function() { ring.remove(); }, 650);
      }
      // Word particle orbiting (every 3rd tap in chain)
      if (chainCount >= 3 && state.wordsLearned.length > 0) {
        const orbitWord = state.wordsLearned[Math.floor(Math.random() * state.wordsLearned.length)];
        const orb = document.createElement('div');
        orb.className = 'fx-word-orbit';
        orb.textContent = orbitWord;
        orb.style.cssText = 'left:' + cx + 'px;top:' + cy + 'px;';
        document.body.appendChild(orb);
        setTimeout(function() { orb.remove(); }, 1400);
      }
      // Spark particles
      const cl = ['#7c6ef5','#a89cff','#5ee7b0','#fff'];
      for (let i = 0; i < 7; i++) {
        const p = document.createElement('div');
        p.className = 'fx-particle';
        const size = 3 + Math.random() * 5;
        const angle = (i / 7) * 360;
        const dist = 28 + Math.random() * 28;
        const rad = angle * Math.PI / 180;
        p.style.cssText = 'width:' + size + 'px;height:' + size + 'px;background:' + cl[i%cl.length] + ';border-radius:50%;left:' + cx + 'px;top:' + cy + 'px;transform:translate(-50%,-50%)';
        document.body.appendChild(p);
        p.offsetHeight;
        p.style.transform = 'translate(calc(-50% + ' + (Math.cos(rad)*dist) + 'px),calc(-50% + ' + (Math.sin(rad)*dist) + 'px))';
        p.style.opacity = '0';
        setTimeout(function() { p.remove(); }, 650);
      }

    } else if (arch === 'beast') {
      // Heavy physical bounce
      const scale = chainCount >= 4 ? 'scale(1.35) rotate(-6deg)' : chainCount >= 2 ? 'scale(1.25)' : 'scale(1.15)';
      petEl.style.transition = 'transform 0.15s cubic-bezier(0.3,0,0.7,1)';
      petEl.style.transform = scale;
      setTimeout(function() { petEl.style.transform = ''; setTimeout(function() { petEl.style.transition = ''; }, 180); }, 160);
      // Ground stomp ring
      const stomp = document.createElement('div');
      stomp.className = 'fx-ring';
      stomp.style.cssText = 'width:70px;height:22px;border-radius:50%;border:2px solid rgba(255,112,64,0.65);left:' + cx + 'px;top:' + (cy + rect.height * 0.42) + 'px;animation-duration:0.38s';
      document.body.appendChild(stomp);
      setTimeout(function() { stomp.remove(); }, 480);
      // Dirt/fire particles spreading downward
      const clrs = ['#ff7040','#f5c842','#ff4020','#ffaa40'];
      const count = 6 + chainCount * 2;
      for (let i = 0; i < count; i++) {
        const p = document.createElement('div');
        p.className = 'fx-particle';
        const size = 4 + Math.random() * 5;
        const angle = 90 + (i / count) * 180;
        const dist = 25 + Math.random() * (18 + chainCount * 5);
        const rad = angle * Math.PI / 180;
        p.style.cssText = 'width:' + size + 'px;height:' + size + 'px;background:' + clrs[i%clrs.length] + ';border-radius:50%;left:' + cx + 'px;top:' + (cy + rect.height*0.3) + 'px;transform:translate(-50%,-50%)';
        document.body.appendChild(p);
        p.offsetHeight;
        p.style.transform = 'translate(calc(-50% + ' + (Math.cos(rad)*dist) + 'px),calc(-50% + ' + (Math.sin(rad)*dist) + 'px))';
        p.style.opacity = '0';
        setTimeout(function() { p.remove(); }, 620);
      }

    } else { // buddy
      // Square/circuit-style rings
      const isChained = chainCount >= 3;
      for (let i = 0; i < 2; i++) {
        const ring = document.createElement('div');
        ring.className = 'fx-ring';
        const size = 48 + i * 38;
        ring.style.cssText = 'width:' + size + 'px;height:' + size + 'px;border:2px solid rgba(94,231,176,' + (0.7-i*0.2) + ');border-radius:' + (isChained ? '6px' : '50%') + ';left:' + cx + 'px;top:' + cy + 'px;animation-delay:' + (i*0.1) + 's;animation-duration:0.42s';
        document.body.appendChild(ring);
        setTimeout(function() { ring.remove(); }, 620);
      }
      // Data label particles
      const labels = ['+1','OK','✓','>>','++','1'];
      for (let i = 0; i < 3 + Math.min(chainCount, 3); i++) {
        const p = document.createElement('div');
        p.className = 'fx-xp';
        p.textContent = labels[i % labels.length];
        p.style.cssText = 'left:' + (cx - 32 + Math.random()*64) + 'px;top:' + (cy - 14 - Math.random()*32) + 'px;font-size:10px;color:#5ee7b0;font-family:monospace;transform:translateX(-50%)';
        document.body.appendChild(p);
        setTimeout(function() { p.remove(); }, 900);
      }
    }
  },

  xpFloat(x, y, text) {
    const el = document.createElement('div');
    el.className = 'fx-xp';
    el.textContent = text;
    el.style.cssText = 'left:' + x + 'px;top:' + y + 'px;transform:translateX(-50%)';
    document.body.appendChild(el);
    setTimeout(function() { el.remove(); }, 1000);
  },

  levelUp(stage) {
    if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    const colors = ['#7c6ef5','#5ee7b0','#f5c842','#ff5e7a','#fff','#a0c0ff'];
    for (let i = 0; i < 28; i++) {
      const c = document.createElement('div');
      c.className = 'fx-confetti';
      const color = colors[i % colors.length];
      const dur = (0.7 + Math.random() * 0.8).toFixed(2);
      const delay = (Math.random() * 0.4).toFixed(2);
      c.style.cssText = 'background:' + color + ';left:' + (cx - 80 + Math.random() * 160) + 'px;top:' + (cy - 60) + 'px;--dur:' + dur + 's;--delay:' + delay + 's;border-radius:' + (Math.random() > 0.5 ? '50%' : '2px');
      document.body.appendChild(c);
      setTimeout(function() { c.remove(); }, (parseFloat(dur)+parseFloat(delay)+0.2) * 1000);
    }
    for (let i = 0; i < 4; i++) {
      const ring = document.createElement('div');
      ring.className = 'fx-ring';
      const size = 80 + i * 50;
      ring.style.cssText = 'width:' + size + 'px;height:' + size + 'px;border:3px solid rgba(245,200,66,' + (0.8-i*0.18) + ');left:' + cx + 'px;top:' + cy + 'px;animation-delay:' + (i*0.15) + 's;animation-duration:0.65s';
      document.body.appendChild(ring);
      setTimeout(function() { ring.remove(); }, 900);
    }
  },

  streak(days, x, y) {
    const glow = document.createElement('div');
    glow.className = 'fx-streak-glow';
    const sz = 200;
    glow.style.cssText = 'width:' + sz + 'px;height:' + sz + 'px;left:' + (x || window.innerWidth/2) + 'px;top:' + (y || window.innerHeight/2) + 'px';
    document.body.appendChild(glow);
    setTimeout(function() { glow.remove(); }, 1000);
    FX.xpFloat(x || window.innerWidth/2, (y || window.innerHeight/2) - 40, '🔥 ' + days + '-Day Streak!');
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('heavy');
  },
};

// ===== GAMES TAB =====

const GAMES_LIST = [
  // ── Inline games (built-in JS) ───────────────────────────────────────
  { id: 'tamagotchi',  name: 'Tamagotchi',      icon: '🥚', desc: 'Виховуй свого компаньона!',             xp: 0,   tc: 'tc-green', hot: true,  locked: false },
  { id: 'fasttap',     name: 'Fast Tap Quiz',   icon: '⚡', desc: '5 слів за 30 сек — тапай правильний!',  xp: 30,  tc: 'tc-blue',  hot: false, locked: false },
  { id: 'matchpairs',  name: 'Match Pairs',     icon: '🃏', desc: 'З\'єднай слово з перекладом.',           xp: 20,  tc: 'tc-green', hot: false, locked: false },
  { id: 'guessword',   name: 'Guess the Word',  icon: '🎯', desc: 'Три підказки → назви слово.',            xp: 15,  tc: 'tc-blue',  hot: false, locked: false },
  { id: 'memory',      name: 'Memory Cards',    icon: '🧠', desc: 'Запам\'ятай і відтвори всі слова.',      xp: 20,  tc: 'tc-gold',  hot: false, locked: false },
  // ── Iframe games (full mockups) ──────────────────────────────────────
  { id: 'connections', name: 'Connections',     icon: '🔗', desc: 'Знайди 4 групи споріднених слів!',       xp: 40,  tc: 'tc-blue',  hot: true,  locked: false, file: 'new_16_connections.html' },
  { id: 'wordraid',    name: 'Word Raid',       icon: '⚔️', desc: 'RPG боїться — перемагай босів словами!', xp: 60,  tc: 'tc-red',   hot: true,  locked: false, file: 'new_27_wordraid.html' },
  { id: 'crossword',   name: 'Daily Crossword', icon: '✏️', desc: 'Щоденний кросворд 7×7.',                 xp: 50,  tc: 'tc-gold',  hot: false, locked: false, file: 'new_22_crossword.html' },
  { id: 'wordrace',    name: 'Word Race',       icon: '🏎️', desc: 'Гонка слів — хто швидший?',              xp: 35,  tc: 'tc-blue',  hot: false, locked: false, file: 'new_21_wordrace.html' },
  { id: 'rozvidnyk',   name: 'Розвідник',       icon: '🕵️', desc: 'Розшифруй секретні повідомлення!',       xp: 45,  tc: 'tc-green', hot: false, locked: false, file: 'new_26_rozvidnyk.html' },
  { id: 'evolution',   name: 'Word Evolution',  icon: '🧬', desc: 'Еволюція слів — Darwin ranking!',         xp: 40,  tc: 'tc-gold',  hot: false, locked: false, file: 'new_24_evolution.html' },
  { id: 'wordchain',   name: 'Word Chain',      icon: '⛓️', desc: 'Ланцюг слів — не розривай!',              xp: 35,  tc: 'tc-green', hot: false, locked: false, file: 'new_25_wordchain.html' },
  { id: 'codenames',   name: 'Codenames',       icon: '🔐', desc: 'Шпигунська гра зі словами.',              xp: 50,  tc: 'tc-red',   hot: false, locked: false, file: 'new_23_codenames.html' },
  { id: 'auction',     name: 'Word Auction',    icon: '🔨', desc: 'Торгуйся за правильні слова!',            xp: 45,  tc: 'tc-gold',  hot: false, locked: false, file: 'new_19_auction.html' },
  { id: 'balderdash',  name: 'Balderdash',      icon: '🎭', desc: 'Придумай найпереконливіше визначення!',   xp: 40,  tc: 'tc-blue',  hot: false, locked: false, file: 'new_20_balderdash.html' },
  { id: 'papers',      name: 'Papers Please',   icon: '🛂', desc: 'Граматична перевірка документів.',         xp: 55,  tc: 'tc-red',   hot: false, locked: false, file: 'new_17_papers.html' },
  { id: 'dating',      name: 'Word Dating',     icon: '💘', desc: 'Свайпай слова — підбери пару!',            xp: 30,  tc: 'tc-green', hot: false, locked: false, file: 'new_18_dating.html' },
];

function renderGames() {
  const words = state.wordsLearned.length;

  const cardsHTML = GAMES_LIST.map(function(g) {
    const isLocked = g.locked || (g.reqWords && words < g.reqWords);
    const lockBadge = isLocked ? '<div class="game-lock-badge">🔒</div>' : '';
    const hotBadge = (!isLocked && g.hot) ? '<div class="game-hot-badge">HOT</div>' : '';
    const onclick = isLocked ? '' : 'onclick="startGame(\'' + g.id + '\')"';
    return '<div class="game-card ' + g.tc + (isLocked ? ' locked' : '') + '" ' + onclick + '>' +
      lockBadge + hotBadge +
      '<div class="game-icon">' + g.icon + '</div>' +
      '<div class="game-name">' + g.name + '</div>' +
      '<div class="game-desc">' + g.desc + '</div>' +
      '<div class="game-xp-badge">⭐ +' + g.xp + ' XP</div>' +
    '</div>';
  }).join('');

  // Next unlock
  const nextLock = GAMES_LIST.find(function(g) { return g.reqWords && words < g.reqWords; });
  const unlockHTML = nextLock
    ? '<div class="game-unlock-bar">' +
        '<div class="game-unlock-icon">' + nextLock.icon + '</div>' +
        '<div class="game-unlock-info">' +
          '<div class="game-unlock-title">' + nextLock.name + '</div>' +
          '<div class="game-unlock-sub">Розблокується при ' + nextLock.reqWords + ' словах</div>' +
          '<div class="game-unlock-prog"><div class="game-unlock-fill" style="width:' + Math.min(100,Math.round(words/nextLock.reqWords*100)) + '%"></div></div>' +
        '</div>' +
        '<div class="game-unlock-label">' + words + '/' + nextLock.reqWords + '</div>' +
      '</div>'
    : '';

  const adBtn = '<div class="ad-reward-block">' +
    '<button class="btn-ad-reward" onclick="watchRewardedAd()" id="adRewardBtn">' +
      '📺 Дивись рекламу → +15 XP' +
    '</button>' +
    '<div style="font-size:10px;color:var(--text2);text-align:center;margin-top:4px">1 раз на день безкоштовно</div>' +
  '</div>';

  document.getElementById('main').innerHTML =
    '<div class="section-title">🎮 Ігри</div>' +
    adBtn +
    '<div class="games-grid">' + cardsHTML + '</div>' +
    unlockHTML;
}

function startGame(id) {
  // Inline games
  if (id === 'tamagotchi') { startTamagotchiMode(); return; }
  if (id === 'fasttap')    { startFastTapGame();    return; }
  if (id === 'matchpairs') { startMatchPairsGame(); return; }
  if (id === 'guessword')  { startGuessWordGame();  return; }
  if (id === 'memory')     { startMemoryGame();     return; }

  // Iframe games (full mockups)
  const game = GAMES_LIST.find(function(g) { return g.id === id; });
  if (game && game.file) {
    openGameIframe('/games/' + game.file, game.name, game.xp);
    return;
  }
  showToast('🚧 Незабаром!', 'success');
}

function openGameIframe(url, name, xpReward) {
  var overlay = document.getElementById('gameOverlay');
  var iframe  = document.getElementById('gameIframe');
  var title   = document.getElementById('gameOverlayTitle');
  iframe.src  = url;
  title.textContent = '🎮 ' + (name || 'Гра');
  overlay.classList.remove('hidden');
  // Store expected XP so postMessage handler knows what to give
  overlay.dataset.xp = xpReward || 0;
  overlay.dataset.gameName = name || '';
  // Hide main UI chrome while game is open
  document.getElementById('tabs').style.display = 'none';
  document.querySelector('.header').style.display = 'none';
}

function closeGameIframe() {
  var overlay = document.getElementById('gameOverlay');
  var iframe  = document.getElementById('gameIframe');
  iframe.src  = '';
  overlay.classList.add('hidden');
  document.getElementById('tabs').style.display = '';
  document.querySelector('.header').style.display = '';
}

// Listen for XP messages from iframe games
window.addEventListener('message', function(event) {
  var data = event.data;
  if (!data || typeof data !== 'object') return;

  // Game sends: { type: 'GAME_OVER', xp: 50 } or { type: 'GAME_DONE', score: 3 }
  if (data.type === 'GAME_OVER' || data.type === 'GAME_DONE' || data.type === 'VOODOO_XP') {
    var overlay = document.getElementById('gameOverlay');
    var awardXP = data.xp || parseInt(overlay.dataset.xp) || 0;
    markTaskDone('game');
    var gameName = overlay.dataset.gameName || 'гри';
    closeGameIframe();
    if (awardXP > 0) {
      // Award XP to user
      state.xp = (state.xp || 0) + awardXP;
      // Show floating XP popup
      var popup = document.createElement('div');
      popup.className = 'xp-award-popup';
      popup.textContent = '+' + awardXP + ' XP 🎉';
      document.body.appendChild(popup);
      setTimeout(function() { popup.remove(); }, 3000);
      // Sync to server
      if (state.tgId) {
        fetch('/api/progress', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ tg_id: state.tgId, xp_delta: awardXP, source: gameName })
        }).catch(function(){});
      }
    }
  }
});

// ===== TAMAGOTCHI MODE =====
const TAMA_FOODS = [
  { icon: '🍎', name: 'Яблуко',  effect: 'happy',  desc: '+настрій' },
  { icon: '⭐', name: '+10 XP',  effect: 'xp',     desc: '+досвід'  },
  { icon: '📖', name: 'Слово',   effect: 'word',   desc: '+знання'  },
  { icon: '❤️', name: 'Любов',  effect: 'heart',  desc: '+настрій' },
  { icon: '💎', name: 'Рідкість',effect: 'rare',   desc: 'рідкісно' },
  { icon: '🎁', name: '???',     effect: 'mystery',desc: 'сюрприз'  },
];

function startTamagotchiMode() {
  state.gameState = { type: 'tamagotchi', mood: 75, energy: 80, interactions: 0, fedItems: [] };
  renderTamagotchi();
}

function renderTamagotchi() {
  const gs = state.gameState;
  if (!gs || gs.type !== 'tamagotchi') return;
  const name = state.companionName || 'ЛЕКСИК';
  const moodEmoji = gs.mood >= 70 ? '😊' : gs.mood >= 40 ? '😐' : gs.mood >= 10 ? '😴' : '💤';
  const moodColor = gs.mood >= 70 ? '#5ee7b0' : gs.mood >= 40 ? '#f5c842' : '#ff7040';
  const energyColor = gs.energy >= 50 ? '#7c6ef5' : '#f5c842';
  const moodMsg = gs.mood >= 70 ? name + ' щасливий!' : gs.mood >= 40 ? name + ' спокійний...' : name + ' сумує... 😴';

  const foodHTML = TAMA_FOODS.map(function(f) {
    return '<div class="tama-food" onclick="feedTamagotchi(\'' + f.effect + '\',\'' + f.icon + '\')">' +
      '<div class="tama-food-icon">' + f.icon + '</div>' +
      '<div class="tama-food-name">' + f.name + '</div>' +
      '<div class="tama-food-desc">' + f.desc + '</div>' +
    '</div>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="game-header">' +
      '<button class="game-back-btn" onclick="state.gameState=null;renderGames()">← Ігри</button>' +
      '<div class="game-title">🥚 ' + name + '</div>' +
      '<div style="font-size:18px">' + moodEmoji + '</div>' +
    '</div>' +
    '<div class="tama-container">' +
      '<div class="tama-bars">' +
        '<div class="tama-bar-row"><span class="tama-bar-label">😊 ' + gs.mood + '%</span><div class="tama-bar"><div class="tama-bar-fill" style="width:' + gs.mood + '%;background:' + moodColor + '"></div></div></div>' +
        '<div class="tama-bar-row"><span class="tama-bar-label">⚡ ' + gs.energy + '%</span><div class="tama-bar"><div class="tama-bar-fill" style="width:' + gs.energy + '%;background:' + energyColor + '"></div></div></div>' +
      '</div>' +
      '<div class="tama-pet-zone" id="tamaArt" onclick="tamaTap()">' +
        buildCompanionHTML(Math.max(state.lexiStage, 1), state.petArchetype) +
      '</div>' +
      '<div class="tama-speech" id="tamaSpeech">' + moodMsg + '</div>' +
      '<div class="tama-interactions">' + gs.interactions + ' взаємодій</div>' +
      '<div class="tama-food-grid">' + foodHTML + '</div>' +
    '</div>';
}

function tamaTap() {
  const art = document.getElementById('tamaArt');
  if (!art) return;
  const arch = state.petArchetype || 'spirit';
  const pool = REACTION_POOLS[arch] || REACTION_POOLS.spirit;
  const gentle = pool.filter(function(e) { return e.w >= 7; });
  const entry = weightedRandom(gentle.length > 0 ? gentle : pool);
  const rect = art.getBoundingClientRect();
  executeReaction(entry, art, rect.left + rect.width/2, rect.top + rect.height/2);
  const sp = entry.sp[Math.floor(Math.random()*entry.sp.length)];
  const speechEl = document.getElementById('tamaSpeech');
  if (speechEl) speechEl.textContent = sp;
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

function feedTamagotchi(effect, icon) {
  const gs = state.gameState;
  if (!gs || gs.type !== 'tamagotchi') return;
  gs.interactions++;
  const artEl = document.getElementById('tamaArt');
  if (!artEl) return;
  const rect = artEl.getBoundingClientRect();
  const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;

  // Animate food flying to pet
  const chip = document.createElement('div');
  chip.style.cssText = 'position:fixed;font-size:32px;pointer-events:none;z-index:9999;left:' + (cx - 16) + 'px;top:' + (cy + rect.height / 2 + 50) + 'px;transition:all 0.42s cubic-bezier(0.2,0,0.4,1);';
  chip.textContent = icon;
  document.body.appendChild(chip);
  chip.offsetHeight;
  chip.style.left = (cx - 16) + 'px';
  chip.style.top = (cy - 20) + 'px';
  chip.style.opacity = '0';
  chip.style.transform = 'scale(0.2)';

  setTimeout(function() {
    chip.remove();
    var speech = '', xpGain = 0;
    var arch = state.petArchetype || 'spirit';
    var pool = REACTION_POOLS[arch] || REACTION_POOLS.spirit;

    if (effect === 'happy') {
      gs.mood = Math.min(100, gs.mood + 15); gs.energy = Math.min(100, gs.energy + 5);
      speech = '🍎 Смачно! Дякую!';
      executeReaction({fx:'bounce',args:[1.25,5,0]}, artEl, cx, cy);
      executeReaction({fx:'heart',args:[]}, artEl, cx, cy);
    } else if (effect === 'xp') {
      xpGain = 10; speech = '⭐ +10 XP! Росту!';
      executeReaction({fx:'xp_pulse',args:[]}, artEl, cx, cy);
    } else if (effect === 'word') {
      xpGain = 5; speech = '📖 Смачне слово!';
      executeReaction({fx:'word_orbit',args:[]}, artEl, cx, cy);
      gs.mood = Math.min(100, gs.mood + 8);
    } else if (effect === 'heart') {
      gs.mood = Math.min(100, gs.mood + 22); speech = '❤️ Люблю тебе!';
      executeReaction({fx:'heart',args:[]}, artEl, cx, cy);
      executeReaction({fx:'aura',args:['#ff5e7a']}, artEl, cx, cy);
    } else if (effect === 'rare') {
      xpGain = 15; gs.mood = Math.min(100, gs.mood + 12);
      speech = '💎 РІДКІСНИЙ ПОДАРУНОК!';
      executeReaction({fx:'halo',args:[]}, artEl, cx, cy);
    } else if (effect === 'mystery') {
      var effs = ['happy','xp','word','heart'];
      feedTamagotchi(effs[Math.floor(Math.random()*effs.length)], '🎁'); return;
    }

    gs.energy = Math.max(0, gs.energy - 5);
    gs.fedItems.push(effect);

    if (xpGain > 0) { state.xp += xpGain; saveLocal(); updateHeader(); FX.xpFloat(cx, cy - 35, '+' + xpGain + ' XP'); }
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');

    const speechEl = document.getElementById('tamaSpeech');
    if (speechEl) speechEl.textContent = speech;
    // Update bars without full re-render
    const moodColor = gs.mood >= 70 ? '#5ee7b0' : gs.mood >= 40 ? '#f5c842' : '#ff7040';
    const energyColor = gs.energy >= 50 ? '#7c6ef5' : '#f5c842';
    const fills = document.querySelectorAll('.tama-bar-fill');
    if (fills[0]) { fills[0].style.width = gs.mood + '%'; fills[0].style.background = moodColor; }
    if (fills[1]) { fills[1].style.width = gs.energy + '%'; fills[1].style.background = energyColor; }
    const intEl = document.querySelector('.tama-interactions');
    if (intEl) intEl.textContent = gs.interactions + ' взаємодій';
  }, 440);
}

// --- FAST TAP QUIZ ---

function startFastTapGame() {
  const lesson = state.lesson;
  if (!lesson || !lesson.words || lesson.words.length < 2) {
    showToast('Спочатку пройди урок!', 'fail'); return;
  }
  state.gameState = {
    type: 'fasttap', words: lesson.words, round: 0,
    maxRounds: 5, score: 0, timeLeft: 30, timer: null,
  };
  renderFastTapRound();
}

function renderFastTapRound() {
  const gs = state.gameState;
  if (!gs || gs.type !== 'fasttap') return;
  if (gs.round >= gs.maxRounds) { endFastTapGame(); return; }

  const words = gs.words;
  const correctWord = words[gs.round % words.length];
  const wrongPool = ['стійкий','слабкий','швидкий','амбітний','ледачий','цікавий','сильний','тихий','веселий','активний','сумний','спокійний'];
  const wrongs = wrongPool.filter(function(w) { return w !== correctWord.translation; }).sort(function() { return 0.5 - Math.random(); }).slice(0, 3);
  const answers = [correctWord.translation].concat(wrongs).sort(function() { return 0.5 - Math.random(); });

  gs._correctIdx = answers.indexOf(correctWord.translation);
  gs._answered = false;

  const optHTML = answers.map(function(a, i) {
    return '<button class="fasttap-opt" id="ftopt' + i + '" onclick="answerFastTap(' + i + ',' + gs._correctIdx + ')">' + a + '</button>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="game-header">' +
      '<button class="game-back-btn" onclick="renderGames()">← Ігри</button>' +
      '<div class="game-title">⚡ Fast Tap</div>' +
      '<div class="game-timer" id="ftTimer">' + gs.timeLeft + 's</div>' +
    '</div>' +
    '<div class="game-score-bar">' +
      '<div class="game-score">Раунд ' + (gs.round+1) + '/' + gs.maxRounds + '</div>' +
      '<div style="margin-left:auto;color:var(--accent2);font-weight:700">✓ ' + gs.score + '</div>' +
    '</div>' +
    '<div class="fasttap-question">' +
      '<div class="fasttap-q-label">Що означає слово?</div>' +
      '<div class="fasttap-q-word">' + correctWord.word + '</div>' +
      '<div style="font-size:12px;color:var(--text2);margin-top:4px">' + correctWord.transcription + '</div>' +
    '</div>' +
    '<div class="fasttap-options">' + optHTML + '</div>';

  // Start/continue timer
  if (!gs.timer) {
    gs.timer = setInterval(function() {
      gs.timeLeft--;
      const timerEl = document.getElementById('ftTimer');
      if (timerEl) {
        timerEl.textContent = gs.timeLeft + 's';
        if (gs.timeLeft <= 5) timerEl.classList.add('urgent');
      }
      if (gs.timeLeft <= 0) { clearInterval(gs.timer); gs.timer = null; endFastTapGame(); }
    }, 1000);
  }
}

function answerFastTap(idx, correctIdx) {
  const gs = state.gameState;
  if (!gs || gs._answered) return;
  gs._answered = true;

  const isCorrect = idx === correctIdx;
  const optEl = document.getElementById('ftopt' + idx);
  const corrEl = document.getElementById('ftopt' + correctIdx);
  document.querySelectorAll('.fasttap-opt').forEach(function(b) { b.onclick = null; });

  if (isCorrect) {
    if (optEl) optEl.classList.add('correct-ans');
    gs.score++;
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
  } else {
    if (optEl) optEl.classList.add('wrong-ans');
    if (corrEl) corrEl.classList.add('correct-ans');
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
  }

  gs.round++;
  setTimeout(function() { renderFastTapRound(); }, 500);
}

function endFastTapGame() {
  const gs = state.gameState;
  if (gs && gs.timer) { clearInterval(gs.timer); gs.timer = null; }
  const score = gs ? gs.score : 0;
  const max = gs ? gs.maxRounds : 5;
  const xpEarned = score * 6;
  state.xp += xpEarned;
  state.gameState = null;
  saveLocal();
  updateHeader();

  if (xpEarned > 0) {
    FX.xpFloat(window.innerWidth/2, window.innerHeight/2, '+' + xpEarned + ' XP');
    apiCall('/api/progress', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ tg_id: state.user?.tg_id||999999, event_type:'quiz', xp_earned: xpEarned, words_learned:[], data:{correct_count:score} }) });
  }

  const stars = '⭐'.repeat(Math.round(score/max*3)) + '☆'.repeat(3 - Math.round(score/max*3));
  document.getElementById('main').innerHTML =
    '<div class="word-card-new fade-in" style="text-align:center;padding:32px">' +
      '<div style="font-size:52px;margin-bottom:8px">' + (score === max ? '🏆' : score > max/2 ? '💪' : '📚') + '</div>' +
      '<div style="font-size:28px;margin-bottom:8px">' + stars + '</div>' +
      '<div style="font-size:24px;font-weight:800;margin-bottom:4px">' + score + '/' + max + '</div>' +
      '<div style="color:var(--accent2);font-size:18px;font-weight:700;margin-bottom:24px">+' + xpEarned + ' XP ⭐</div>' +
      '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="startGame(\'fasttap\')">🔄 Ще раз</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="renderGames()">🎮 Ігри</button>' +
      '</div>' +
    '</div>';
}

// --- MATCH PAIRS ---

function startMatchPairsGame() {
  const lesson = state.lesson;
  if (!lesson || !lesson.words || lesson.words.length < 2) {
    showToast('Спочатку пройди урок!', 'fail'); return;
  }
  const words = lesson.words.slice(0, 3);
  const cards = [];
  words.forEach(function(w) {
    cards.push({ id: w.word + '_en', text: w.word, pairId: w.word, type: 'en' });
    cards.push({ id: w.word + '_ua', text: w.translation, pairId: w.word, type: 'ua' });
  });
  cards.sort(function() { return 0.5 - Math.random(); });
  state.gameState = { type: 'matchpairs', cards: cards, flipped: [], matched: [], moves: 0 };
  renderMatchPairs();
}

function renderMatchPairs() {
  const gs = state.gameState;
  if (!gs || gs.type !== 'matchpairs') return;

  const cardsHTML = gs.cards.map(function(c) {
    const isMatched = gs.matched.includes(c.pairId);
    const cls = isMatched ? 'pair-card matched' : 'pair-card';
    const text = isMatched ? c.text : (gs.flipped.includes(c.id) ? c.text : '?');
    const onclick = isMatched ? '' : 'onclick="flipCard(\'' + c.id + '\')"';
    return '<div class="' + cls + '" id="pc_' + c.id + '" ' + onclick + '>' + text + '</div>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="game-header">' +
      '<button class="game-back-btn" onclick="renderGames()">← Ігри</button>' +
      '<div class="game-title">🃏 Match Pairs</div>' +
      '<div style="font-size:13px;color:var(--text2)">Хід ' + gs.moves + '</div>' +
    '</div>' +
    '<div class="pairs-grid">' + cardsHTML + '</div>';
}

function flipCard(cardId) {
  const gs = state.gameState;
  if (!gs || gs.type !== 'matchpairs') return;
  if (gs.flipped.length >= 2) return;
  if (gs.flipped.includes(cardId)) return;

  gs.flipped.push(cardId);
  const el = document.getElementById('pc_' + cardId);
  const card = gs.cards.find(function(c) { return c.id === cardId; });
  if (el && card) { el.textContent = card.text; el.classList.add('flipped'); }
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');

  if (gs.flipped.length === 2) {
    gs.moves++;
    const [id1, id2] = gs.flipped;
    const c1 = gs.cards.find(function(c) { return c.id === id1; });
    const c2 = gs.cards.find(function(c) { return c.id === id2; });
    if (c1 && c2 && c1.pairId === c2.pairId) {
      // Match!
      gs.matched.push(c1.pairId);
      gs.flipped = [];
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
      FX.xpFloat(window.innerWidth/2, 200, '+7 XP');
      state.xp += 7; saveLocal();
      setTimeout(function() {
        if (gs.matched.length >= gs.cards.length / 2) { endMatchPairsGame(); }
        else { renderMatchPairs(); }
      }, 300);
    } else {
      // No match
      const el1 = document.getElementById('pc_' + id1);
      const el2 = document.getElementById('pc_' + id2);
      if (el1) el1.classList.add('wrong-flip');
      if (el2) el2.classList.add('wrong-flip');
      if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
      setTimeout(function() {
        gs.flipped = [];
        renderMatchPairs();
      }, 700);
    }
  }
}

function endMatchPairsGame() {
  const gs = state.gameState;
  const moves = gs ? gs.moves : 0;
  const xpEarned = Math.max(10, 30 - moves * 2);
  state.xp += xpEarned; state.gameState = null; saveLocal(); updateHeader();
  FX.levelUp(0);
  apiCall('/api/progress', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ tg_id: state.user?.tg_id||999999, event_type:'quiz', xp_earned: xpEarned, words_learned:[], data:{correct_count:3} }) });

  document.getElementById('main').innerHTML =
    '<div class="word-card-new fade-in" style="text-align:center;padding:32px">' +
      '<div style="font-size:52px;margin-bottom:8px">🃏</div>' +
      '<div style="font-size:22px;font-weight:800;margin-bottom:4px">Всі пари знайдено!</div>' +
      '<div style="color:var(--text2);margin-bottom:8px">Ходів: ' + moves + '</div>' +
      '<div style="color:var(--accent2);font-size:18px;font-weight:700;margin-bottom:24px">+' + xpEarned + ' XP ⭐</div>' +
      '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="startGame(\'matchpairs\')">🔄 Знову</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="renderGames()">🎮 Ігри</button>' +
      '</div>' +
    '</div>';
}

// --- GUESS THE WORD ---

function startGuessWordGame() {
  const lesson = state.lesson;
  if (!lesson || !lesson.words || lesson.words.length === 0) {
    showToast('Спочатку пройди урок!', 'fail'); return;
  }
  const word = lesson.words[Math.floor(Math.random() * lesson.words.length)];
  const hints = [word.example_ua, word.transcription, 'Переклад: ' + word.translation];
  const wrongPool = ['time','place','mind','resilient','ambitious','calm','focus','strong','gentle','vivid'];
  const wrongs = wrongPool.filter(function(w) { return w !== word.word; }).sort(function() { return 0.5 - Math.random(); }).slice(0, 3);
  const answers = [word.word].concat(wrongs).sort(function() { return 0.5 - Math.random(); });
  state.gameState = { type: 'guessword', word: word, hints: hints, hintIdx: 0, answers: answers, correct: answers.indexOf(word.word), tries: 0 };
  renderGuessWord();
}

function renderGuessWord() {
  const gs = state.gameState;
  if (!gs || gs.type !== 'guessword') return;
  const visibleHints = gs.hints.slice(0, gs.hintIdx + 1);
  const hintsHTML = visibleHints.map(function(h, i) {
    return '<div style="padding:10px 14px;background:rgba(124,110,245,0.08);border-radius:10px;font-size:13px;color:var(--text2);margin-bottom:8px">💡 ' + h + '</div>';
  }).join('');

  const optHTML = gs.answers.map(function(a, i) {
    return '<button class="fasttap-opt" onclick="answerGuessWord(' + i + ')">' + a + '</button>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="game-header">' +
      '<button class="game-back-btn" onclick="renderGames()">← Ігри</button>' +
      '<div class="game-title">🎯 Guess the Word</div>' +
    '</div>' +
    '<div style="margin-bottom:16px">' + hintsHTML + '</div>' +
    '<div class="fasttap-options">' + optHTML + '</div>' +
    (gs.hintIdx < gs.hints.length - 1
      ? '<button class="btn-secondary" style="margin-top:12px" onclick="showNextHint()">💡 Ще підказка (-5 XP)</button>'
      : '');
}

function showNextHint() {
  const gs = state.gameState;
  if (!gs || gs.hintIdx >= gs.hints.length - 1) return;
  gs.hintIdx++;
  renderGuessWord();
}

function answerGuessWord(idx) {
  const gs = state.gameState;
  if (!gs) return;
  const isCorrect = idx === gs.correct;
  const xpEarned = isCorrect ? Math.max(5, 15 - gs.hintIdx * 5) : 0;
  state.xp += xpEarned; state.gameState = null; saveLocal(); updateHeader();
  if (xpEarned > 0) FX.xpFloat(window.innerWidth/2, 200, '+' + xpEarned + ' XP');

  document.getElementById('main').innerHTML =
    '<div class="word-card-new fade-in" style="text-align:center;padding:32px">' +
      '<div style="font-size:52px;margin-bottom:8px">' + (isCorrect ? '🎯' : '😅') + '</div>' +
      '<div style="font-size:20px;font-weight:800;margin-bottom:4px">' + (isCorrect ? 'Вірно!' : 'Не вірно') + '</div>' +
      '<div style="color:var(--text2);margin-bottom:8px">Слово: <b style="color:var(--text)">' + gs.word.word + '</b></div>' +
      (xpEarned > 0 ? '<div style="color:var(--accent2);font-size:18px;font-weight:700;margin-bottom:24px">+' + xpEarned + ' XP</div>' : '<div style="margin-bottom:24px"></div>') +
      '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="startGame(\'guessword\')">🔄 Ще</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="renderGames()">🎮 Ігри</button>' +
      '</div>' +
    '</div>';
}

// --- MEMORY GAME ---

function startMemoryGame() {
  const lesson = state.lesson;
  if (!lesson || !lesson.words || lesson.words.length === 0) {
    showToast('Спочатку пройди урок!', 'fail'); return;
  }
  const words = lesson.words;
  // Show 3 words for 3 seconds, then quiz them
  state.gameState = { type: 'memory', words: words, phase: 'show', score: 0, questionIdx: 0 };
  renderMemoryShow();
}

function renderMemoryShow() {
  const gs = state.gameState;
  if (!gs) return;
  const wordsHTML = gs.words.map(function(w) {
    return '<div style="background:rgba(124,110,245,0.1);border:1px solid rgba(124,110,245,0.3);border-radius:14px;padding:14px;margin-bottom:10px">' +
      '<span style="font-weight:800;font-size:16px">' + w.word + '</span>' +
      '<span style="color:var(--text2);margin-left:8px;font-size:13px">' + w.transcription + '</span>' +
      '<div style="color:var(--accent2);font-size:14px;margin-top:4px">' + w.translation + '</div>' +
    '</div>';
  }).join('');

  let countdown = 3;
  document.getElementById('main').innerHTML =
    '<div class="game-header"><button class="game-back-btn" onclick="renderGames()">← Ігри</button>' +
      '<div class="game-title">🧠 Memory Cards</div>' +
      '<div class="game-timer" id="memTimer">3s</div>' +
    '</div>' +
    '<div style="text-align:center;color:var(--text2);font-size:12px;margin-bottom:12px">Запам\'ятай слова!</div>' +
    wordsHTML;

  const interval = setInterval(function() {
    countdown--;
    const el = document.getElementById('memTimer');
    if (el) { el.textContent = countdown + 's'; if (countdown <= 1) el.classList.add('urgent'); }
    if (countdown <= 0) {
      clearInterval(interval);
      gs.phase = 'quiz';
      renderMemoryQuiz();
    }
  }, 1000);
}

function renderMemoryQuiz() {
  const gs = state.gameState;
  if (!gs || gs.questionIdx >= gs.words.length) { endMemoryGame(); return; }
  const correctWord = gs.words[gs.questionIdx];
  const wrongPool = ['стійкий','слабкий','швидкий','амбітний','ледачий','цікавий','сильний','тихий'];
  const wrongs = wrongPool.filter(function(w) { return w !== correctWord.translation; }).sort(function() { return 0.5 - Math.random(); }).slice(0,3);
  const answers = [correctWord.translation].concat(wrongs).sort(function() { return 0.5 - Math.random(); });
  const correctIdx = answers.indexOf(correctWord.translation);

  document.getElementById('main').innerHTML =
    '<div class="game-header"><button class="game-back-btn" onclick="renderGames()">← Ігри</button>' +
      '<div class="game-title">🧠 Memory</div>' +
      '<div style="font-size:13px;color:var(--text2)">' + (gs.questionIdx+1) + '/' + gs.words.length + '</div>' +
    '</div>' +
    '<div class="fasttap-question">' +
      '<div class="fasttap-q-label">Що означало це слово?</div>' +
      '<div class="fasttap-q-word">' + correctWord.word + '</div>' +
    '</div>' +
    '<div class="fasttap-options">' +
      answers.map(function(a, i) {
        return '<button class="fasttap-opt" onclick="answerMemory(' + i + ',' + correctIdx + ')">' + a + '</button>';
      }).join('') +
    '</div>';
}

function answerMemory(idx, correctIdx) {
  const gs = state.gameState;
  if (!gs) return;
  if (idx === correctIdx) { gs.score++; if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium'); }
  const btn = document.querySelectorAll('.fasttap-opt')[idx];
  const cbtn = document.querySelectorAll('.fasttap-opt')[correctIdx];
  document.querySelectorAll('.fasttap-opt').forEach(function(b) { b.onclick = null; });
  if (btn) btn.classList.add(idx === correctIdx ? 'correct-ans' : 'wrong-ans');
  if (cbtn && idx !== correctIdx) cbtn.classList.add('correct-ans');
  gs.questionIdx++;
  setTimeout(function() { renderMemoryQuiz(); }, 600);
}

function endMemoryGame() {
  const gs = state.gameState;
  const score = gs ? gs.score : 0;
  const total = gs ? gs.words.length : 3;
  const xpEarned = score * 8;
  state.xp += xpEarned; state.gameState = null; saveLocal(); updateHeader();
  if (xpEarned > 0) FX.xpFloat(window.innerWidth/2, 200, '+' + xpEarned + ' XP');

  document.getElementById('main').innerHTML =
    '<div class="word-card-new fade-in" style="text-align:center;padding:32px">' +
      '<div style="font-size:52px;margin-bottom:8px">' + (score === total ? '🏆' : '🧠') + '</div>' +
      '<div style="font-size:22px;font-weight:800;margin-bottom:4px">' + score + '/' + total + ' запам\'ятав</div>' +
      '<div style="color:var(--accent2);font-size:18px;font-weight:700;margin-bottom:24px">+' + xpEarned + ' XP</div>' +
      '<div style="display:flex;gap:10px">' +
        '<button class="btn-primary" style="flex:1" onclick="startGame(\'memory\')">🔄 Ще</button>' +
        '<button class="btn-secondary" style="flex:1" onclick="renderGames()">🎮 Ігри</button>' +
      '</div>' +
    '</div>';
}

// ===== NEW CHARACTER BUILDERS (preview6: Astro, Kaito, Yuki, Vex, Seraph) =====

function buildAstroHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="astro-wrap">' +
      '<div class="char-prop">📡</div>' +
      '<div class="astro-glow"></div>' +
      '<div class="astro-foot l"></div><div class="astro-foot r"></div>' +
      '<div class="astro-arm l"></div><div class="astro-arm r"></div>' +
      '<div class="astro-torso"></div>' +
      '<div class="astro-head">' +
        '<div class="astro-phone-band"></div>' +
        '<div class="astro-phone l"></div><div class="astro-phone r"></div>' +
        '<div class="astro-visor">' +
          '<div class="astro-visor-eyes">' +
            '<div class="astro-visor-eye"></div>' +
            '<div class="astro-visor-eye"></div>' +
          '</div>' +
          '<div class="astro-visor-smile"></div>' +
        '</div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildKaitoHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="kaito-wrap">' +
      '<div class="char-prop" style="font-size:14px">🎧</div>' +
      '<div class="kaito-jacket"></div>' +
      '<div class="kaito-neck"></div>' +
      '<div class="kaito-head">' +
        '<div class="kaito-hair"></div>' +
        '<div class="kaito-hair-side"></div>' +
        '<div class="kaito-ear l"></div><div class="kaito-ear r"></div>' +
        '<div class="kaito-brow l"></div><div class="kaito-brow r"></div>' +
        '<div class="kaito-eye l"></div><div class="kaito-eye r"></div>' +
        '<div class="kaito-nose"></div>' +
        '<div class="kaito-mouth"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildYukiHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="yuki-wrap">' +
      '<div class="char-prop" style="font-size:14px">🌸</div>' +
      '<div class="yuki-jacket"></div>' +
      '<div class="yuki-neck"></div>' +
      '<div class="yuki-head">' +
        '<div class="yuki-hair-back"></div>' +
        '<div class="yuki-hair-top"></div>' +
        '<div class="yuki-hair-bang"></div>' +
        '<div class="yuki-ear l"></div><div class="yuki-ear r"></div>' +
        '<div class="yuki-lash l"></div><div class="yuki-lash r"></div>' +
        '<div class="yuki-brow l"></div><div class="yuki-brow r"></div>' +
        '<div class="yuki-eye l"></div><div class="yuki-eye r"></div>' +
        '<div class="yuki-nose"></div>' +
        '<div class="yuki-lips"></div>' +
        '<div class="yuki-blush l"></div><div class="yuki-blush r"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildVexHTML(s) {
  const glowSize = s >= 4 ? '0 0 40px rgba(220,0,0,0.9),0 0 80px rgba(150,0,0,0.45),0 8px 24px rgba(0,0,0,0.7)' : '0 0 30px rgba(180,0,0,0.55),0 0 60px rgba(100,0,0,0.25),0 8px 24px rgba(0,0,0,0.7)';
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="vex-wrap">' +
      '<div class="vex-aura"></div>' +
      '<div class="vex-horn l"></div><div class="vex-horn r"></div>' +
      '<div class="vex-body" style="box-shadow:' + glowSize + '">' +
        '<div class="vex-brow l"></div><div class="vex-brow r"></div>' +
        '<div class="vex-eye l"><div class="vex-slit"></div></div>' +
        '<div class="vex-eye r"><div class="vex-slit"></div></div>' +
        '<div class="vex-scar"></div>' +
        '<div class="vex-collar"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

function buildSeraphHTML(s) {
  return '<div class="comp-char" onclick="onCompanionTap()" style="transform:' + _charScale(s) + ';transform-origin:bottom center">' +
    '<div class="seraph-wrap">' +
      '<div class="seraph-halo"></div>' +
      '<div class="seraph-wing l"></div><div class="seraph-wing r"></div>' +
      '<div class="seraph-body">' +
        '<div class="seraph-mark"></div>' +
        '<div class="seraph-brow l"></div><div class="seraph-brow r"></div>' +
        '<div class="seraph-eye l"></div><div class="seraph-eye r"></div>' +
        '<div class="seraph-collar"></div>' +
      '</div>' +
    '</div>' +
  '</div>';
}

// ===== CHARACTER DEFINITIONS =====
const CHARACTERS = [
  { id:'lumix',   name:'Люмікс',   icon:'🔮', desc:'Магічний дух',   archetype:'spirit', color:'#9333ea' },
  { id:'kitsune', name:'Кіцуне',   icon:'🦊', desc:'Дикий лисеня',   archetype:'beast',  color:'#ea580c' },
  { id:'mochi',   name:'Мочі',     icon:'🐰', desc:'Пухнастий друг', archetype:'beast',  color:'#f5c878' },
  { id:'byte',    name:'Байт',     icon:'🤖', desc:'Цифровий друг',  archetype:'buddy',  color:'#14b8a6' },
  { id:'ember',   name:'Ембер',    icon:'🐉', desc:'Вогняний дракон',archetype:'beast',  color:'#ef4444' },
  { id:'mist',    name:'Міст',     icon:'🌙', desc:'Місячний дух',   archetype:'spirit', color:'#38bdf8' },
  { id:'marco',   name:'Марко',    icon:'🌍', desc:'Мандрівник',     archetype:'buddy',  color:'#f59e0b' },
  { id:'astro',   name:'Астро',    icon:'🚀', desc:'Космічний робот', archetype:'buddy',  color:'#60a5fa' },
  { id:'kaito',   name:'Кайто',    icon:'🎧', desc:'Крутий хлопець', archetype:'spirit', color:'#1e293b' },
  { id:'yuki',    name:'Юкі',      icon:'🌸', desc:'Модна дівчина',  archetype:'spirit', color:'#4a1942' },
  { id:'vex',     name:'Векс',     icon:'😈', desc:'Темний воїн',    archetype:'beast',  color:'#cc0000' },
  { id:'seraph',  name:'Серафім',  icon:'😇', desc:'Світлий воїн',   archetype:'spirit', color:'#d97706' },
  { id:'bruno',   name:'Бруно',    icon:'🐻', desc:'Ведмідь з рюкзаком', archetype:'beast', color:'#92400e' },
  { id:'crash',   name:'Креш',     icon:'🌀', desc:'Бандикут',       archetype:'beast',  color:'#fb923c' },
  { id:'nova',    name:'Нова',     icon:'⭐', desc:'Темний герой',    archetype:'spirit', color:'#6d28d9' },
  { id:'luna',    name:'Луна',     icon:'🐱', desc:'Місячна кішка',   archetype:'beast',  color:'#a3e635' },
  { id:'rex',     name:'Рекс',     icon:'🦕', desc:'Дракончик',       archetype:'beast',  color:'#16a34a' },
  { id:'sunny',   name:'Санні',   icon:'☀️', desc:'Сонячний друг',      archetype:'spirit', color:'#fbbf24' },
  { id:'biscuit', name:'Бісквіт', icon:'🍪', desc:'Солодкий компаньон', archetype:'buddy',  color:'#d97706' },
  { id:'ronin',   name:'Ронін',   icon:'⚔️', desc:'Темний воїн',        archetype:'beast',  color:'#dc2626' },
  { id:'apex',    name:'Апекс',   icon:'⚡', desc:'Кіберпанк',           archetype:'buddy',  color:'#00e5ff' },
  { id:'bolt',    name:'Болт',    icon:'🏃', desc:'Спортсмен',           archetype:'beast',  color:'#1d4ed8' },
];

// ===== EGG HATCH ANIMATION =====
function renderEggHatch() {
  document.getElementById('tabs').style.display = 'none';
  document.getElementById('main').innerHTML =
    '<div id="hatch-screen" style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;gap:16px">' +
      '<div id="hatch-title" style="font-size:18px;font-weight:700;color:#9333ea;letter-spacing:1px;opacity:0;transition:opacity 0.5s">Щось визрівало...</div>' +
      '<div id="egg-wrap" style="position:relative;width:120px;height:140px">' +
        '<div id="egg-body" style="' +
          'position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);' +
          'width:88px;height:110px;' +
          'background:radial-gradient(ellipse at 38% 32%,#fff8e7 0%,#f5d97a 40%,#e0a820 100%);' +
          'border-radius:50% 50% 50% 50% / 60% 60% 40% 40%;' +
          'box-shadow:0 4px 24px #e0a82066,inset 0 -8px 16px #c8840044;' +
          'animation:eggWobble 0.7s ease-in-out infinite;' +
        '"></div>' +
        '<svg id="egg-cracks" viewBox="0 0 88 110" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:88px;height:110px;opacity:0;transition:opacity 0.4s">' +
          '<polyline points="44,20 38,42 50,50 36,75" stroke="#7c4a03" stroke-width="2" fill="none" stroke-linecap="round"/>' +
          '<polyline points="58,35 52,48 62,56" stroke="#7c4a03" stroke-width="1.5" fill="none" stroke-linecap="round"/>' +
          '<polyline points="30,50 40,60" stroke="#7c4a03" stroke-width="1.5" fill="none" stroke-linecap="round"/>' +
        '</svg>' +
        '<div id="egg-particles" style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:0;height:0;pointer-events:none"></div>' +
      '</div>' +
      '<div id="hatch-sub" style="font-size:14px;color:#888;opacity:0;transition:opacity 0.5s">Натисни, щоб дізнатись!</div>' +
    '</div>';

  // Fade in title
  setTimeout(function() {
    const t = document.getElementById('hatch-title');
    if (t) t.style.opacity = '1';
  }, 300);
  setTimeout(function() {
    const s = document.getElementById('hatch-sub');
    if (s) s.style.opacity = '1';
  }, 800);

  // Phase 1: wobble intensifies → cracks appear at 1.5s
  setTimeout(function() {
    const egg = document.getElementById('egg-body');
    if (egg) egg.style.animation = 'eggShake 0.18s ease-in-out infinite';
    const cracks = document.getElementById('egg-cracks');
    if (cracks) cracks.style.opacity = '1';
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
    }
  }, 1500);

  // Phase 2: burst at 2.4s → show particles → transition to picker
  setTimeout(function() {
    const wrap = document.getElementById('egg-wrap');
    if (wrap) {
      // Burst effect: scale up + fade out egg
      const egg = document.getElementById('egg-body');
      const cracks = document.getElementById('egg-cracks');
      if (egg) { egg.style.transition = 'transform 0.25s ease-out,opacity 0.25s'; egg.style.transform = 'translate(-50%,-50%) scale(1.6)'; egg.style.opacity = '0'; }
      if (cracks) { cracks.style.transition = 'transform 0.25s ease-out,opacity 0.25s'; cracks.style.transform = 'translate(-50%,-50%) scale(1.6)'; cracks.style.opacity = '0'; }

      // Spawn particle shards
      const colors = ['#f5d97a','#e0a820','#9333ea','#fb923c','#38bdf8','#a3e635'];
      const pContainer = document.getElementById('egg-particles');
      if (pContainer) {
        for (let i = 0; i < 12; i++) {
          const p = document.createElement('div');
          const angle = (i / 12) * 360;
          const dist = 55 + Math.random() * 30;
          const rad = angle * Math.PI / 180;
          const tx = Math.cos(rad) * dist;
          const ty = Math.sin(rad) * dist;
          p.style.cssText = 'position:absolute;width:' + (6+Math.random()*8) + 'px;height:' + (6+Math.random()*8) + 'px;' +
            'background:' + colors[i % colors.length] + ';border-radius:50%;' +
            'transition:transform 0.5s ease-out,opacity 0.5s;opacity:1;';
          pContainer.appendChild(p);
          setTimeout(function(el,x,y) {
            el.style.transform = 'translate(' + x + 'px,' + y + 'px)';
            el.style.opacity = '0';
          }, 20, p, tx, ty);
        }
      }
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
      }
    }

    // Title swap
    const t = document.getElementById('hatch-title');
    if (t) { t.style.opacity = '0'; setTimeout(function() { if (t) { t.textContent = '🎉 Обери свого компаньйона!'; t.style.opacity = '1'; } }, 300); }
    const s = document.getElementById('hatch-sub');
    if (s) s.style.opacity = '0';

    // After burst animation, show character picker
    setTimeout(function() {
      renderArchetypeSelect();
    }, 700);
  }, 2400);
}

// ===== PET CHARACTER ONBOARDING =====
function renderArchetypeSelect() {
  document.getElementById('tabs').style.display = 'none';

  const charArtBuilders = {
    lumix: buildLumixHTML, kitsune: buildKitsuneHTML, mochi: buildMochiHTML,
    byte: buildByteHTML, ember: buildEmberHTML, bruno: buildBrunoHTML,
    mist: buildMistHTML, marco: buildMarcoHTML, crash: buildCrashHTML,
    nova: buildNovaHTML, luna: buildLunaHTML, rex: buildRexHTML,
    sunny: buildSunnyHTML, biscuit: buildBiscuitHTML, ronin: buildRoninHTML,
    apex: buildApexHTML, bolt: buildBoltHTML,
    astro: buildAstroHTML, kaito: buildKaitoHTML, yuki: buildYukiHTML,
    vex: buildVexHTML, seraph: buildSeraphHTML,
  };
  const PREMIUM_CHARS = ['vex', 'seraph'];
  const charHTML = CHARACTERS.map(function(c) {
    const artHTML = charArtBuilders[c.id] ? charArtBuilders[c.id](1) : '<span style="font-size:28px">' + c.icon + '</span>';
    const isPremChar = PREMIUM_CHARS.indexOf(c.id) >= 0;
    const locked = isPremChar && !state.isPremium;
    const lockBadge = locked ? '<span class="char-lock-badge">⭐ Premium</span>' : '';
    const clickFn = locked
      ? 'showPremiumOffer()'
      : 'selectCharacter(\'' + c.id + '\')';
    return '<button class="char-pick-btn' + (locked ? ' char-locked' : '') + '" onclick="' + clickFn + '" style="border-color:' + c.color + '22">' +
      '<div class="char-pick-art">' + artHTML + '</div>' +
      lockBadge +
      '<span class="char-pick-name">' + c.name + '</span>' +
      '<span class="char-pick-desc">' + c.desc + '</span>' +
    '</button>';
  }).join('');

  document.getElementById('main').innerHTML =
    '<div class="onboarding-screen fade-in">' +
      '<div style="font-size:14px;color:rgba(255,255,255,0.45);letter-spacing:2px;text-transform:uppercase;margin-bottom:4px">Voodoo 🪄</div>' +
      '<div class="onb-title" style="margin-bottom:4px">Обери компаньйона</div>' +
      '<div class="onb-sub" style="margin-bottom:20px">Він буде рости разом з тобою 🌱</div>' +
      '<div class="char-pick-grid">' + charHTML + '</div>' +
      '<div style="margin-top:16px;font-size:11px;color:rgba(255,255,255,0.25);text-align:center">⭐ = Premium персонаж</div>' +
    '</div>';
}

function showPremiumOffer() {
  const overlay = document.createElement('div');
  overlay.className = 'premium-overlay';
  overlay.innerHTML =
    '<div class="premium-modal">' +
      '<div class="premium-modal-icon">⭐</div>' +
      '<div class="premium-modal-title">Voodoo Premium</div>' +
      '<div class="premium-modal-list">' +
        '<div class="pm-row">🔓 Персонажі Vex та Seraph</div>' +
        '<div class="pm-row">⚡ Подвійний XP на уроки</div>' +
        '<div class="pm-row">🏆 Premium-іконка в Leaderboard</div>' +
        '<div class="pm-row">📊 AI-аналітика прогресу</div>' +
      '</div>' +
      '<div class="premium-modal-price">75 ⭐ / місяць (~$1.50)</div>' +
      '<button class="premium-modal-btn" onclick="openTelegramSubscribe()">Отримати Premium в Telegram</button>' +
      '<button class="premium-modal-close" onclick="this.closest(\'.premium-overlay\').remove()">Закрити</button>' +
    '</div>';
  document.body.appendChild(overlay);
}

function openTelegramSubscribe() {
  if (tg) {
    tg.openTelegramLink('https://t.me/' + (tg.initDataUnsafe?.bot_username || 'YourBot_prod_bot') + '?start=subscribe');
  }
}

function selectCharacter(charId) {
  const char = CHARACTERS.find(function(c) { return c.id === charId; });
  if (!char) return;
  // Guard premium chars
  if (['vex','seraph'].indexOf(charId) >= 0 && !state.isPremium) {
    showPremiumOffer(); return;
  }
  state.petCharacter = charId;
  state.petArchetype = char.archetype;  // keep legacy compat
  saveLocal();
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
  renderNameSelect();
}

function renderGoalSelect() {
  const arch = PET_ARCHETYPES[state.petArchetype];
  const emoji = arch ? arch.stageEmojis[1] : '🐣';
  const name = state.companionName || 'Лексик';
  document.getElementById('main').innerHTML =
    '<div class="onboarding-screen fade-in">' +
      '<div class="onb-egg" style="font-size:64px">' + emoji + '</div>' +
      '<div class="onb-title">' + name + ' вже з тобою!</div>' +
      '<div class="onb-sub">Яка твоя ціль навчання?</div>' +
      '<div class="goal-grid">' +
        '<button class="goal-btn" onclick="selectGoal(\'work\')">💼<br>Робота</button>' +
        '<button class="goal-btn" onclick="selectGoal(\'travel\')">✈️<br>Подорожі</button>' +
        '<button class="goal-btn" onclick="selectGoal(\'everyday\')">💬<br>Спілкування</button>' +
      '</div>' +
    '</div>';
}

function selectArchetype(arch) {
  // Legacy path — map archetype to default character
  const defaults = { spirit:'lumix', beast:'kitsune', buddy:'byte' };
  state.petArchetype = arch;
  state.petCharacter = state.petCharacter || defaults[arch] || 'lumix';
  saveLocal();
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
  renderNameSelect();
}

// ===== COMPANION NAMING =====
function renderNameSelect() {
  const tgUser = tg?.initDataUnsafe?.user;
  const tgFirst = tgUser?.first_name ? tgUser.first_name.replace(/['"<>]/g,'') : null;
  const tgUsername = tgUser?.username ? tgUser.username.replace(/['"<>]/g,'') : null;
  const defaultNames = { spirit: 'Люмікс', beast: 'Рикс', buddy: 'Байт' };
  const suggestedName = defaultNames[state.petArchetype] || 'Лексик';

  const tgFirstOpt = tgFirst
    ? '<button class="name-opt-btn" onclick="confirmName(\'' + tgFirst + '\')">' +
        '<span class="name-opt-icon">👤</span>' +
        '<div class="name-opt-right"><span class="name-opt-label">Ім\'я з Telegram</span><span class="name-opt-val">' + tgFirst + '</span></div>' +
      '</button>'
    : '';

  const tgUserOpt = tgUsername
    ? '<button class="name-opt-btn" onclick="confirmName(\'' + tgUsername + '\')">' +
        '<span class="name-opt-icon">@</span>' +
        '<div class="name-opt-right"><span class="name-opt-label">Username Telegram</span><span class="name-opt-val">@' + tgUsername + '</span></div>' +
      '</button>'
    : '';

  document.getElementById('main').innerHTML =
    '<div class="onboarding-screen fade-in">' +
      '<div class="onb-egg" style="font-size:52px">💬</div>' +
      '<div class="onb-title">Як звати твого компаньона?</div>' +
      '<div class="onb-sub">Обери ім\'я — або введи своє</div>' +
      '<div class="name-opts">' +
        tgFirstOpt + tgUserOpt +
        '<button class="name-opt-btn" onclick="confirmName(\'' + suggestedName + '\')">' +
          '<span class="name-opt-icon">✨</span>' +
          '<div class="name-opt-right"><span class="name-opt-label">Запропонована назва</span><span class="name-opt-val">' + suggestedName + '</span></div>' +
        '</button>' +
        '<div class="name-custom-row">' +
          '<input id="nameInput" class="name-input" type="text" placeholder="Введи своє ім\'я..." maxlength="16">' +
          '<button class="btn-primary" onclick="confirmCustomName()">✓</button>' +
        '</div>' +
      '</div>' +
    '</div>';
}

function confirmName(name) {
  if (!name || !name.trim()) return;
  state.companionName = name.trim().slice(0, 16);
  saveLocal();
  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
  savePetToServer();  // persist character + name to server
  renderGoalSelect();
}

function confirmCustomName() {
  const input = document.getElementById('nameInput');
  const name = input ? input.value.trim() : '';
  if (!name) { showToast('Введи ім\'я!', 'fail'); return; }
  confirmName(name);
}

function startRenameCompanion() {
  const current = state.companionName || 'ЛЕКСИК';
  const modal = document.createElement('div');
  modal.className = 'rename-modal';
  modal.id = 'renameModal';
  modal.innerHTML =
    '<div class="rename-modal-card">' +
      '<div class="rename-modal-title">✏️ Перейменувати</div>' +
      '<input id="renameInput" class="name-input" type="text" value="' + current + '" maxlength="16" autocomplete="off">' +
      '<div style="display:flex;gap:10px;margin-top:12px">' +
        '<button class="btn-secondary" style="flex:1" onclick="document.getElementById(\'renameModal\').remove()">Скасувати</button>' +
        '<button class="btn-primary" style="flex:1" onclick="saveRename()">Зберегти</button>' +
      '</div>' +
    '</div>';
  document.getElementById('app').appendChild(modal);
  const input = document.getElementById('renameInput');
  if (input) { setTimeout(function() { input.focus(); input.select(); }, 100); }
}

function saveRename() {
  const input = document.getElementById('renameInput');
  const name = input ? input.value.trim() : '';
  const modal = document.getElementById('renameModal');
  if (modal) modal.remove();
  if (!name) return;
  state.companionName = name.slice(0, 16);
  saveLocal();
  showToast('Ім\'я змінено: ' + state.companionName + ' ✨', 'success');
  if (state.currentTab === 'home') renderHome();
  else if (state.currentTab === 'profile') renderProfile();
}

function selectGoal(topic) {
  state.topic = topic;
  saveLocal();
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
  document.getElementById('tabs').style.display = '';
  apiCall('/api/settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tg_id: state.user?.tg_id || 999999, topic: topic}),
  });
  state.lexiStage = computeLexiStage();
  state.lexiEvo = computeEvoProgress();
  renderHome();
}

// ===== TAB SWITCHER =====
function switchTab(tab) {
  stopIdleAnimation();
  document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
  var activeTab = document.querySelector('[data-tab="' + tab + '"]');
  if (activeTab) activeTab.classList.add('active');
  state.currentTab = tab;

  if (tab === 'home') renderHome();
  else if (tab === 'lesson') renderLesson();
  else if (tab === 'games') renderGames();
  else if (tab === 'review') renderReview();
  else if (tab === 'leaderboard') renderLeaderboard();
  else if (tab === 'profile') renderProfile();
}

// ===== DAILY LOGIN BONUS =====
async function checkDailyBonus() {
  var tgId = state.user && state.user.tg_id ? state.user.tg_id : null;
  if (!tgId) return;
  try {
    var r = await fetch(API + '/api/daily-bonus?tg_id=' + tgId);
    var data = await r.json();
    if (data.available) {
      showDailyBonusModal(data.day, data.reward);
    }
  } catch(e) {}
}

function showDailyBonusModal(day, reward) {
  var days = ['День 1','День 2','День 3','День 4','День 5','День 6','День 7'];
  var emojis = ['🎁','🎁','⚡','⚡','🔥','🔥','🌟'];
  var html = '<div class="bonus-overlay" id="bonusOverlay" onclick="closeBonusIfOutside(event)">'
    + '<div class="bonus-modal">'
    + '<div class="bonus-title">Щоденний бонус</div>'
    + '<div class="bonus-days">';
  for (var i = 0; i < 7; i++) {
    var cls = i < day ? 'bonus-day claimed' : (i === day ? 'bonus-day active' : 'bonus-day');
    html += '<div class="' + cls + '">'
      + '<div class="bonus-day-emoji">' + emojis[i] + '</div>'
      + '<div class="bonus-day-label">' + days[i] + '</div>'
      + '</div>';
  }
  html += '</div>'
    + '<div class="bonus-reward">+' + reward.xp + ' XP &nbsp; +' + reward.hp + ' HP ❤️</div>'
    + '<button class="bonus-claim-btn" onclick="claimDailyBonus(' + day + ')">Забрати!</button>'
    + '</div></div>';
  document.body.insertAdjacentHTML('beforeend', html);
}

async function claimDailyBonus(day) {
  haptic('success');
  var overlay = document.getElementById('bonusOverlay');
  if (overlay) overlay.remove();
  try {
    var tgId = state.user && state.user.tg_id ? state.user.tg_id : 999999;
    var r = await fetch(API + '/api/daily-bonus/claim', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({tg_id: tgId})
    });
    var data = await r.json();
    if (data.ok) {
      state.xp = data.new_xp;
      FX.xpFloat(window.innerWidth / 2, window.innerHeight / 2 - 60, '+' + data.xp_bonus + ' XP 🎁');
      updateHeader();
    }
  } catch(e) {}
}

function closeBonusIfOutside(e) {
  if (e.target.id === 'bonusOverlay') {
    document.getElementById('bonusOverlay').remove();
  }
}

// ===== HOME SCREEN SHORTCUT PROMPT =====
function maybePromptHomeScreen() {
  var tgApp = window.Telegram && window.Telegram.WebApp;
  if (!tgApp) return;
  var lessons = (state.user && state.user.total_lessons) || 0;
  var shown = localStorage.getItem('homeScreenPrompted');
  if ((lessons >= 3 || state.streak >= 3) && !shown && tgApp.addToHomeScreen) {
    localStorage.setItem('homeScreenPrompted', '1');
    setTimeout(function() {
      tgApp.addToHomeScreen();
    }, 2000);
  }
}

// ===== REFERRAL / INVITE =====
function copyReferralLink() {
  haptic('light');
  var tgId = state.user && state.user.tg_id ? state.user.tg_id : '';
  var link = 'https://t.me/VoodooBot?start=ref_' + tgId;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(link).then(function() {
      showToast('Посилання скопійовано!', 'success');
    });
  }
}

// ===== TOAST =====
var toastTimer = null;
function showToast(msg, type) {
  if (!type) type = 'success';
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'result-toast ' + type;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { el.className = 'result-toast hidden'; }, 3000);
}

// ===== INIT =====
async function init() {
  loadLocal();
  updateHeader();

  // First-time users: show character picker immediately
  if (!state.petCharacter && !state.petArchetype) {
    initUser();  // init in background (no await — don't block UI)
    renderArchetypeSelect();
    return;
  }
  // Ensure petArchetype is set for legacy compatibility
  if (state.petCharacter && !state.petArchetype) {
    const char = CHARACTERS.find(function(c) { return c.id === state.petCharacter; });
    if (char) state.petArchetype = char.archetype;
  }

  state.lexiStage = computeLexiStage();
  state.lexiEvo = computeEvoProgress();

  renderHome();
  setTimeout(startIdleAnimation, 1200);

  initUser().then(function() {
    if (state.user) {
      state.xp = Math.max(state.xp, state.user.xp || 0);
      state.streak = Math.max(state.streak, state.user.streak || 0);
      // Re-check evolution after server data arrives
      const newStage = computeLexiStage();
      if (newStage > state.lexiStage) {
        state.lexiStage = newStage;
        state.lexiEvo = computeEvoProgress();
        saveLocal();
      }
    }
    updateHeader();
    checkDailyBonus();
    initAdsgram();
  });

  setTimeout(async function() {
    if (!state.lesson) state.lesson = await fetchLesson();
  }, 1000);

  // Fetch leaderboard in background to get real leader XP
  setTimeout(async function() {
    const tgId = state.user?.tg_id || 999999;
    const lb = await apiCall('/api/leaderboard?tg_id=' + tgId, {}, null);
    if (lb && lb.length > 0) {
      state.leaderXP = lb[0].xp || 0;
    }
  }, 1500);
}

init();
