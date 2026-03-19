const SERVER = 'http://localhost:7778';
let polling = false;

async function poll() {
  if (polling) return;
  polling = true;
  console.log('[Claude Bridge] Started polling', SERVER);

  while (true) {
    try {
      const res = await fetch(`${SERVER}/command`, { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        const cmd = await res.json();
        if (cmd && cmd.id) {
          console.log('[Claude Bridge] Got command:', cmd);
          const result = await executeCommand(cmd);
          await fetch(`${SERVER}/result`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: cmd.id, result })
          });
        }
      }
    } catch (e) {
      // сервер не запущено — чекаємо
    }
    await new Promise(r => setTimeout(r, 1000));
  }
}

async function executeCommand(cmd) {
  try {
    if (cmd.type === 'eval') {
      // Виконати JS на вкладці
      const tabs = await chrome.tabs.query({ url: cmd.url_pattern || '<all_urls>' });
      const tab = cmd.tab_id
        ? tabs.find(t => t.id === cmd.tab_id)
        : tabs.find(t => cmd.url_match ? t.url.includes(cmd.url_match) : true) || tabs[0];

      if (!tab) return { error: 'Tab not found', available_tabs: tabs.map(t => ({ id: t.id, url: t.url, title: t.title })) };

      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: new Function(`return (async () => { ${cmd.code} })()`),
      });
      return { ok: true, tab_url: tab.url, value: results[0]?.result };

    } else if (cmd.type === 'list_tabs') {
      const tabs = await chrome.tabs.query({});
      return tabs.map(t => ({ id: t.id, url: t.url, title: t.title, active: t.active }));

    } else if (cmd.type === 'navigate') {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      await chrome.tabs.update(tabs[0].id, { url: cmd.url });
      await new Promise(r => setTimeout(r, 3000));
      return { ok: true, navigated_to: cmd.url };

    } else if (cmd.type === 'screenshot') {
      const dataUrl = await chrome.tabs.captureVisibleTab();
      return { ok: true, screenshot: dataUrl };
    }

    return { error: `Unknown command type: ${cmd.type}` };
  } catch (e) {
    return { error: e.message };
  }
}

// Старт
poll();
chrome.runtime.onStartup.addListener(poll);
