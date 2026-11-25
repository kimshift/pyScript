#!/usr/bin/env node
/**
 * mise 任务菜单 —— `npm start` 的入口。
 *
 * 做的事：
 *   1. 用 `mise tasks ls --json` 读出当前项目 mise.toml 里的全部 task（不在脚本里硬编码）
 *   2. 在终端列出可选项（按 `ld:` / `qs:` / `wb:` 这类前缀分组）
 *   3. ↑/↓ 移动、字母键过滤、Enter 执行 `mise run <task>`、Esc 退出
 *
 * 直接指定任务（跳过菜单）：
 *   npm start -- ld:check
 *   npm start -- qs:dry
 *   npm start -- --list        # 只打印任务清单
 *
 * 依赖：仅 Node 内置模块，无第三方包。
 */
'use strict';

const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const MISE_BIN = process.env.MISE_BIN || 'mise';

// 菜单配置文件（可用环境变量覆盖）
const CONFIG_PATH =
  process.env.MISE_MENU_CONFIG || path.join(__dirname, '..', 'config', 'mise-menu.txt');

// ---------- 终端宽窄与 ANSI ----------

const USE_COLOR = Boolean(process.stdout.isTTY) && !process.env.NO_COLOR;

function c(code) {
  return (s) => (USE_COLOR ? '\x1b[' + code + 'm' + s + '\x1b[0m' : String(s));
}
const bold = c('1');
const dim = c('2');
const cyan = c('36');
const red = c('31');
const green = c('32');

/** 单个码位的显示宽度（CJK / emoji 占 2 列） */
function charWidth(cp) {
  if (cp < 32 || cp === 0x7f) return 0;
  if (
    (cp >= 0x1100 && cp <= 0x115f) ||
    (cp >= 0x2e80 && cp <= 0x303e) ||
    (cp >= 0x3041 && cp <= 0x33ff) ||
    (cp >= 0x3400 && cp <= 0x4dbf) ||
    (cp >= 0x4e00 && cp <= 0x9fff) ||
    (cp >= 0xa000 && cp <= 0xa4cf) ||
    (cp >= 0xac00 && cp <= 0xd7a3) ||
    (cp >= 0xf900 && cp <= 0xfaff) ||
    (cp >= 0xfe30 && cp <= 0xfe6f) ||
    (cp >= 0xff00 && cp <= 0xff60) ||
    (cp >= 0xffe0 && cp <= 0xffe6) ||
    (cp >= 0x1f300 && cp <= 0x1f64f) ||
    (cp >= 0x1f900 && cp <= 0x1f9ff) ||
    (cp >= 0x20000 && cp <= 0x3fffd)
  ) {
    return 2;
  }
  return 1;
}

function textWidth(s) {
  let w = 0;
  for (const ch of s) w += charWidth(ch.codePointAt(0));
  return w;
}

/** 超出 maxWidth 列就截断并加省略号 */
function truncate(s, maxWidth) {
  if (maxWidth <= 0) return '';
  if (textWidth(s) <= maxWidth) return s;
  let out = '';
  let w = 0;
  for (const ch of s) {
    const cw = charWidth(ch.codePointAt(0));
    if (w + cw > maxWidth - 1) break;
    out += ch;
    w += cw;
  }
  return out + '…';
}

function terminalWidth() {
  return Math.max(40, (process.stdout.columns || 100) - 1);
}

// ---------- 读取 mise 任务 ----------

function loadTasks() {
  const r = spawnSync(MISE_BIN, ['tasks', 'ls', '--json'], {
    encoding: 'utf8',
    windowsHide: true,
  });
  if (r.error) {
    const hint =
      r.error.code === 'ENOENT'
        ? `找不到 mise 可执行文件（${MISE_BIN}）。请确认已安装 mise 并在 PATH 里，或用 MISE_BIN 指定完整路径。`
        : `调用 mise 失败：${r.error.message}`;
    throw new Error(hint);
  }
  if (r.status !== 0) {
    throw new Error(`mise tasks ls 退出码 ${r.status}\n${(r.stderr || '').trim()}`);
  }
  const raw = (r.stdout || '').trim();
  if (!raw) return [];

  let list;
  try {
    list = JSON.parse(raw);
  } catch (e) {
    throw new Error(`无法解析 mise tasks ls --json 的输出：${e.message}`);
  }
  if (!Array.isArray(list)) return [];

  return list
    .filter((t) => t && t.name && !t.hide && !t.global)
    .map((t) => ({
      name: String(t.name),
      group: t.name.includes(':') ? t.name.split(':')[0] : '',
      short: t.name.includes(':') ? t.name.slice(t.name.indexOf(':') + 1) : t.name,
      description: String(t.description || ''),
    }));
}

// ---------- 菜单配置文件（config/mise-menu.txt） ----------
const GENERIC_SECTION = '通用';

function sectionKeyOf(task) {
  return task.group || GENERIC_SECTION;
}

function taskMap(tasks) {
  const m = new Map();
  for (const t of tasks) m.set(t.name, t);
  return m;
}

/**
 * 解析配置文件：
 *   `# [组名]`        分组标题（顺序即菜单顺序）
 *   名字              显示
 *   `# 名字`          隐藏（记录保留）
 *   `名字  # 说明`    末尾说明仅供阅读，不参与解析
 */
function parseConfig(text) {
  const sections = [];
  let cur = null;
  for (const raw of String(text).split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) continue;

    const header = /^#+\s*\[(.+?)\]\s*$/.exec(line);
    if (header) {
      cur = { label: header[1].trim(), entries: [] };
      sections.push(cur);
      continue;
    }

    let hidden = false;
    let body = line;
    if (body.startsWith('#')) {
      hidden = true;
      body = body.replace(/^#+\s*/, '');
    }
    const name = body.split('#')[0].trim();
    // 不是任务名的行（例如纯说明注释）直接忽略
    if (!/^[A-Za-z0-9][\w.:-]*$/.test(name)) continue;

    if (!cur) {
      cur = { label: GENERIC_SECTION, entries: [] };
      sections.push(cur);
    }
    cur.entries.push({ name, hidden });
  }
  return sections;
}

function renderConfig(sections, tasks) {
  const byName = taskMap(tasks);
  const allNames = sections.reduce((acc, s) => acc.concat(s.entries.map((e) => e.name)), []);
  const width = Math.min(24, Math.max(10, ...allNames.map((n) => n.length)));

  const out = [
    '# mise 菜单配置 —— `npm start` 按这个文件决定显示哪些任务',
    '#',
    '#   名字                 → 菜单里显示、可执行',
    '#   # 名字               → 菜单里隐藏（记录仍保留在本文件，想恢复就把行首的 # 删掉）',
    '#   # [组名]             → 分组标题，本文件里的先后顺序就是菜单顺序',
    '#   名字  # 说明         → 末尾说明只供阅读，不参与解析',
    '#',
    '# mise.toml 里新增的 task 会被自动补到这里；删掉本文件会按 mise.toml 重新生成。',
    '',
  ];

  for (const section of sections) {
    if (!section.entries.length && section.label !== GENERIC_SECTION) continue;
    out.push('# [' + section.label + ']');
    for (const e of section.entries) {
      const t = byName.get(e.name);
      const desc = t && t.description ? t.description : '';
      const nameCol = e.name.padEnd(width, ' ');
      const lineText = desc ? nameCol + '  # ' + desc : nameCol;
      out.push(e.hidden ? '# ' + lineText : lineText);
    }
    out.push('');
  }

  return out.join('\n').replace(/\s+$/, '') + '\n';
}

/** 读配置；文件不存在返回 null */
function loadConfig() {
  try {
    return fs.readFileSync(CONFIG_PATH, 'utf8');
  } catch (e) {
    if (e.code === 'ENOENT') return null;
    throw new Error(`读取菜单配置失败（${CONFIG_PATH}）：${e.message}`);
  }
}

function saveConfig(sections, tasks) {
  try {
    fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true });
    fs.writeFileSync(CONFIG_PATH, renderConfig(sections, tasks), 'utf8');
    return true;
  } catch (e) {
    return false;
  }
}

/** 把 mise.toml 里配置文件还没有的任务补进去，返回新增/失效条目 */
function mergeConfig(sections, tasks) {
  const present = new Set();
  for (const s of sections) for (const e of s.entries) present.add(e.name);

  const added = [];
  for (const t of tasks) {
    if (present.has(t.name)) continue;
    present.add(t.name);
    const key = sectionKeyOf(t);
    let target = sections.find((s) => s.label === key);
    if (!target) {
      target = { label: key, entries: [] };
      sections.push(target);
    }
    target.entries.push({ name: t.name, hidden: false });
    added.push(t.name);
  }

  const known = new Set(tasks.map((t) => t.name));
  const stale = [];
  for (const s of sections) for (const e of s.entries) if (!known.has(e.name)) stale.push(e.name);

  return { added, stale };
}

/** 按配置顺序拍平任务列表（隐藏项与失效项不出现） */
function applyConfig(sections, tasks) {
  const byName = taskMap(tasks);
  const ordered = [];
  const shown = new Set();
  const recorded = new Set();
  for (const section of sections) {
    for (const e of section.entries) {
      recorded.add(e.name);
      if (e.hidden || shown.has(e.name)) continue;
      const t = byName.get(e.name);
      if (!t) continue;
      shown.add(e.name);
      ordered.push(Object.assign({}, t, { section: section.label }));
    }
  }
  // 兜底：配置文件里一条记录都没有的任务（例如写入失败时）仍然给出，避免整个菜单空掉
  for (const t of tasks) {
    if (!recorded.has(t.name)) ordered.push(Object.assign({}, t, { section: sectionKeyOf(t) }));
  }
  return ordered;
}

/**
 * 读出「要在菜单里显示」的任务，并顺带维护配置文件。
 * 返回 { tasks, added, stale, configPath, readOnly }
 */
function resolveTasks() {
  const raw = loadConfig();
  const all = loadTasks();
  const sections = raw === null ? [] : parseConfig(raw);
  const { added, stale } = mergeConfig(sections, all);

  let saved = true;
  if (raw === null || added.length) {
    if (all.length) saved = saveConfig(sections, all);
  }

  return {
    tasks: applyConfig(sections, all),
    added,
    stale,
    configPath: CONFIG_PATH,
    saved,
  };
}

// ---------- 渲染 ----------

function buildRows(tasks, query) {
  const rows = [];
  if (query) {
    const q = query.toLowerCase();
    for (const t of tasks) {
      const hay = (t.name + ' ' + t.description).toLowerCase();
      if (hay.includes(q)) rows.push({ kind: 'task', task: t });
    }
    return rows;
  }
  let last = null;
  for (const t of tasks) {
    const section = t.section || GENERIC_SECTION;
    if (section !== last) {
      rows.push({ kind: 'header', label: section });
      last = section;
    }
    rows.push({ kind: 'task', task: t });
  }
  return rows;
}

function firstTaskIndex(rows, from, step) {
  let i = from;
  while (i >= 0 && i < rows.length) {
    if (rows[i].kind === 'task') return i;
    i += step;
  }
  return -1;
}

function printPlain(tasks) {
  const rows = buildRows(tasks, '');
  const nameCol = Math.max(12, ...rows.filter((r) => r.kind === 'task').map((r) => r.task.name.length));
  for (const row of rows) {
    if (row.kind === 'header') {
      console.log('\n' + row.label);
      continue;
    }
    const pad = row.task.name.padEnd(nameCol, ' ');
    console.log('  ' + pad + '  ' + row.task.description);
  }
}

function printHelp() {
  console.log(
    [
      '用法：',
      '  npm start                  交互菜单（↑/↓ 选择，Enter 执行，字母过滤，Esc 退出）',
      '  npm start -- <task>        直接执行某个 mise task，例如 npm start -- ld:check',
      '  npm start -- --list        只打印任务清单',
      '  npm start -- --config      打印菜单配置文件路径',
      '',
      '菜单内容由 config/mise-menu.txt 决定：把某个任务那行行首加上「# 」就不再显示。',
      '对应的 mise 命令：mise tasks ls --json / mise run <task>',
    ].join('\n'),
  );
}

// ---------- 交互菜单 ----------

function interactive(tasks) {
  return new Promise((resolve) => {
    const all = tasks;
    let query = '';
    let rows = buildRows(all, query);
    let index = firstTaskIndex(rows, 0, 1);
    let renderedLines = 0;
    let scrollTop = 0;
    let finished = false;

    readline.emitKeypressEvents(process.stdin);
    let rawMode = false;
    try {
      process.stdin.setRawMode(true);
      rawMode = true;
    } catch (e) {
      rawMode = false;
    }
    process.stdin.resume();
    process.stdout.write('\x1b[?25l'); // 隐藏光标

    function restore() {
      if (finished) return;
      finished = true;
      if (rawMode) {
        try {
          process.stdin.setRawMode(false);
        } catch (e) {
          /* ignore */
        }
      }
      process.stdin.pause();
      process.stdin.removeListener('keypress', onKeypress);
      process.stdout.removeListener('resize', onResize);
      process.stdout.write('\x1b[?25h\n'); // 显示光标并换行
    }

    function render() {
      const width = terminalWidth();
      const termRows = Math.max(12, process.stdout.rows || 30);

      const total = all.length;
      const shown = rows.filter((r) => r.kind === 'task').length;
      const head = [
        cyan(bold(truncate('pyscript · mise 任务（' + total + (query ? '，匹配 ' + shown : '') + '）', width))),
        dim(truncate('↑/↓ 移动 · Enter 执行 · 直接输入过滤 · Backspace 删除 · Esc 退出', width)),
        '',
      ];

      // 过滤时同名任务会重名（ld:check / qs:check），所以显示完整任务名
      const filtering = Boolean(query);
      const labelOf = (t) => (filtering ? t.name : t.short);

      const nameCol = Math.max(
        6,
        Math.min(24, ...rows.filter((r) => r.kind === 'task').map((r) => labelOf(r.task).length)),
      );

      // 先把每一行渲染成字符串（body 行带 rowIdx，方便视口滚动）
      const body = [];
      let hintTask = null;
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row.kind === 'header') {
          const tail = Math.max(0, width - textWidth(row.label) - 5);
          body.push({ text: dim('── ' + row.label + ' ' + '─'.repeat(tail)) });
          continue;
        }
        const selected = i === index;
        if (selected) hintTask = row.task;
        const nameText = labelOf(row.task);
        const namePlain = nameText + ' '.repeat(Math.max(0, nameCol - nameText.length));
        const prefixPlain = selected ? '▶ ' : '  ';
        const desc = truncate(row.task.description, width - textWidth(prefixPlain) - nameCol - 2);
        const prefix = selected ? cyan(prefixPlain) : prefixPlain;
        const nameOut = selected ? cyan(bold(namePlain)) : namePlain;
        body.push({ text: prefix + nameOut + '  ' + dim(desc), rowIdx: i });
      }
      if (body.length === 0) body.push({ text: red('  没有匹配的任务，按 Backspace 继续') });

      const tail = ['', dim('› ') + (query ? query : dim('（输入关键字过滤）'))];
      if (hintTask) tail.push(dim(truncate('将执行：mise run ' + hintTask.name, width)));

      // 视口：任务多时只显示能放下的部分，并跟随选中项滚动
      const overflow = body.length > Math.max(3, termRows - 1 - head.length - tail.length);
      // 溢出时要额外留 2 行给「上面/下面还有 N 行」的提示
      const viewHeight = Math.max(3, termRows - 1 - head.length - tail.length - (overflow ? 2 : 0));
      const selInBody = body.findIndex((b) => b.rowIdx === index);
      if (body.length > viewHeight) {
        if (selInBody < scrollTop) scrollTop = selInBody;
        else if (selInBody >= scrollTop + viewHeight) scrollTop = selInBody - viewHeight + 1;
        scrollTop = Math.max(0, Math.min(scrollTop, body.length - viewHeight));
      } else {
        scrollTop = 0;
      }
      const visible = body.slice(scrollTop, scrollTop + viewHeight);

      // 视口顶部/底部被截断时给出提示，避免误以为只有这些任务
      if (scrollTop > 0) visible.unshift({ text: dim('  ⋮ 上面还有 ' + scrollTop + ' 行') });
      const restBelow = body.length - (scrollTop + viewHeight);
      if (restBelow > 0) visible.push({ text: dim('  ⋮ 下面还有 ' + restBelow + ' 行') });

      if (body.length > viewHeight) {
        const from = scrollTop + 1;
        const to = Math.min(body.length, scrollTop + viewHeight);
        tail[0] = dim(`  ${from}-${to} / ${body.length}（↑/↓ 滚动）`);
      }

      const lines = head.concat(visible.map((v) => v.text), tail);

      if (renderedLines > 0) {
        readline.moveCursor(process.stdout, 0, -renderedLines);
        process.stdout.write('\r\x1b[0J'); // \r 回到行首，否则首行左侧会残留上一帧
      } else {
        process.stdout.write('\x1b[0J');
      }
      process.stdout.write(lines.join('\n'));
      renderedLines = Math.max(0, lines.length - 1);
    }

    function onResize() {
      // 终端重排后行数记账会失真，插一个换行重新开始
      process.stdout.write('\n');
      renderedLines = 0;
      render();
    }

    function onKeypress(str, key) {
      if (!key) return;
      if (key.ctrl && key.name === 'c') {
        restore();
        resolve(130);
        return;
      }
      if (key.name === 'escape') {
        restore();
        resolve(0);
        return;
      }
      if (key.name === 'return' || key.name === 'enter') {
        const row = rows[index];
        if (!row || row.kind !== 'task') return;
        restore();
        resolve(runTask(row.task.name, []));
        return;
      }
      if (key.name === 'up' || key.name === 'down') {
        if (rows.length === 0) return;
        const step = key.name === 'up' ? -1 : 1;
        let next = index;
        for (let guard = 0; guard <= rows.length; guard++) {
          next += step;
          if (next < 0) next = rows.length - 1;
          if (next >= rows.length) next = 0;
          if (rows[next].kind === 'task') break;
        }
        index = next;
        render();
        return;
      }
      if (key.name === 'backspace') {
        if (query) {
          query = query.slice(0, -1);
          rows = buildRows(all, query);
          index = firstTaskIndex(rows, 0, 1);
          scrollTop = 0;
          render();
        }
        return;
      }
      if (str && !key.ctrl && !key.meta && str.length === 1 && str >= ' ') {
        query += str;
        rows = buildRows(all, query);
        index = firstTaskIndex(rows, 0, 1);
        scrollTop = 0;
        render();
      }
    }

    process.stdin.on('keypress', onKeypress);
    process.stdout.on('resize', onResize);
    render();
  });
}

// ---------- 执行 ----------

function runTask(name, extraArgs) {
  return new Promise((resolve) => {
    const args = ['run', name].concat(extraArgs || []);
    console.log(dim('$ ' + MISE_BIN + ' ' + args.join(' ')));
    const child = spawn(MISE_BIN, args, { stdio: 'inherit' });
    child.on('error', (err) => {
      console.error(red('启动 mise 失败：' + err.message));
      resolve(1);
    });
    child.on('exit', (code, signal) => {
      if (signal) {
        console.log(dim(`被信号 ${signal} 终止`));
        resolve(1);
        return;
      }
      if (code !== 0) console.log(red(`任务失败，退出码 ${code}`));
      resolve(code || 0);
    });
  });
}

// ---------- 入口 ----------

function main(argv) {
  const first = argv[0];

  if (first === '-h' || first === '--help') {
    printHelp();
    return Promise.resolve(0);
  }

  if (first === '--config') {
    console.log(CONFIG_PATH);
    return Promise.resolve(0);
  }

  let resolved;
  try {
    resolved = resolveTasks();
  } catch (err) {
    console.error(red(err.message));
    return Promise.resolve(1);
  }
  const tasks = resolved.tasks;

  // 直接指定任务：不受菜单配置的「隐藏」影响，只要 mise 里存在就跑
  if (first && !first.startsWith('-')) {
    const known = new Set(loadTasks().map((t) => t.name));
    if (!known.has(first)) {
      console.error(red(`没有这个任务：${first}`));
      console.error(dim('可用任务：npm start -- --list'));
      return Promise.resolve(1);
    }
    return runTask(first, argv.slice(1));
  }

  if (!resolved.saved) {
    console.error(
      red('菜单配置未能写入：' + resolved.configPath + '（请检查目录权限，或设 MISE_MENU_CONFIG 指到可写位置）'),
    );
  }

  if (first === '-l' || first === '--list') {
    if (!tasks.length) {
      console.error(red('菜单里没有可执行任务（检查 ' + resolved.configPath + ' 是否全被注释掉了）'));
      return Promise.resolve(1);
    }
    printPlain(tasks);
    if (resolved.stale.length) {
      console.log(dim('\n提示：以下任务在 mise.toml 里已不存在，配置文件中的记录已跳过：'));
      console.log(dim('  ' + resolved.stale.join('、')));
    }
    return Promise.resolve(0);
  }

  if (!tasks.length) {
    console.error(red('菜单里没有可执行任务（检查 ' + resolved.configPath + ' 是否全被注释掉了）'));
    return Promise.resolve(1);
  }

  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    printPlain(tasks);
    console.log(
      green('\n当前不是交互终端。用 `npm start -- <task>` 直接执行，例如：npm start -- ld:check'),
    );
    return Promise.resolve(0);
  }

  return interactive(tasks);
}

module.exports = {
  loadTasks,
  resolveTasks,
  parseConfig,
  renderConfig,
  mergeConfig,
  applyConfig,
  buildRows,
  textWidth,
  truncate,
  interactive,
  main,
  CONFIG_PATH,
};

if (require.main === module) {
  main(process.argv.slice(2))
    .then((code) => {
      process.exitCode = code;
    })
    .catch((err) => {
      console.error(red(err && err.stack ? err.stack : String(err)));
      process.exitCode = 1;
    });
}
