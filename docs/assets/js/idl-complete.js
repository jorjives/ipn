// Offers what the grammar allows next. Walks the table compiled from docs/reference/grammar.md
// (assets/idl-grammar.json) over the enclosing block up to the cursor; the tokeniser and the
// Walker are line-for-line ports of scripts/grammar_table.py, which the tests hold to every
// example and template.

const TOKEN = /\s*(?:("[^"]*")|(\d{4}-\d{2}-\d{2})|(\d+(?:\.\d+)?)|(co-payment|[A-Za-z_][A-Za-z0-9_\/]*)|(<=|>=|[<>:,%()+\-*\/^]))/y;
const KINDS = ["str", "date", "num", "id", "op"];
const CLASS_KINDS = { str: ["string"], date: ["date"], num: ["number", "integer"],
                      id: ["name", "word", "item_name", "field_name", "collection_name", "old_item_name"] };

function stripComment(raw) {
  let quoted = false;
  for (let i = 0; i < raw.length; i++) {
    if (raw[i] === '"') quoted = !quoted;
    if (raw[i] === "#" && !quoted) return raw.slice(0, i).trimEnd();
  }
  return raw.trimEnd();
}

// Tokens as {kind, text}: the parser's kinds plus NEWLINE, INDENT and DEDENT. With `open`,
// the last line is the one being typed: its indent counts even when it is blank, it gets no
// NEWLINE, and nothing is closed. Throws on text the parser could not read either.
export function tokenise(text, open = false) {
  const out = [], stack = [0], lines = text.split("\n");
  lines.forEach((raw, i) => {
    const last = open && i === lines.length - 1;
    const body = stripComment(raw);
    if (!body.trim() && !last) return;
    const indent = body.trim() ? body.length - body.trimStart().length : raw.length;
    if (indent > stack[stack.length - 1]) { stack.push(indent); out.push({ kind: "INDENT", text: "" }); }
    while (indent < stack[stack.length - 1]) { stack.pop(); out.push({ kind: "DEDENT", text: "" }); }
    if (indent !== stack[stack.length - 1]) throw new Error("inconsistent indentation");
    const line = body.trim();
    TOKEN.lastIndex = 0;
    while (TOKEN.lastIndex < line.length) {
      const at = TOKEN.lastIndex, m = TOKEN.exec(line);
      if (!m || TOKEN.lastIndex === at) throw new Error("cannot read " + line.slice(at));
      out.push({ kind: KINDS[m.slice(1).findIndex(g => g !== undefined)], text: m[0].trim() });
    }
    if (!last) out.push({ kind: "NEWLINE", text: "" });
  });
  if (!open) for (let i = 1; i < stack.length; i++) out.push({ kind: "DEDENT", text: "" });
  return out;
}

export function matches(kind, value, tok) {
  if (kind === "lit") return value === tok.text;
  if (kind === "tok") return value === tok.kind;
  if (value === "integer") return tok.kind === "num" && !tok.text.includes(".");
  return (CLASS_KINDS[tok.kind] || []).includes(value);
}

export class Walker {
  constructor(table, start) {
    this.rules = table.rules;
    this.live = [{ rule: start, state: 0, stack: [] }];
  }

  closed() {
    const seen = new Map(), todo = [...this.live];
    const key = c => c.rule + "\0" + c.state + "\0" + c.stack.map(r => r.rule + ":" + r.state).join(",");
    todo.forEach(c => seen.set(key(c), c));
    while (todo.length) {
      const { rule, state, stack } = todo.pop(), node = this.rules[rule][state], found = [];
      for (const [kind, value, target] of node.edges) {
        if (kind === "call") found.push({ rule: value, state: 0, stack: [...stack, { rule, state: target }] });
      }
      if (node.accept && stack.length) found.push({ ...stack[stack.length - 1], stack: stack.slice(0, -1) });
      for (const c of found) if (!seen.has(key(c))) { seen.set(key(c), c); todo.push(c); }
    }
    return [...seen.values()];
  }

  // [{rule, kind, value, target}] for every non-call edge of every live configuration.
  expected() {
    const out = [];
    for (const { rule, state } of this.closed()) {
      for (const [kind, value, target] of this.rules[rule][state].edges) if (kind !== "call") out.push({ rule, kind, value, target });
    }
    return out;
  }

  feed(tok) {
    const next = [];
    for (const { rule, state, stack } of this.closed()) {
      for (const [kind, value, target] of this.rules[rule][state].edges) {
        if (kind !== "call" && matches(kind, value, tok)) next.push({ rule, state: target, stack });
      }
    }
    this.live = next;
    return next.length > 0;
  }

  accepted() {
    return this.closed().some(({ rule, state, stack }) => this.rules[rule][state].accept && !stack.length);
  }
}

// The names a product declares, scanned from its text: what the grammar's word classes offer.
export function declared(text) {
  const d = { names: ["claim", "claimed", "position", "territory"], words: ["yes", "no"], covers: [], tables: [],
              collections: [], items: [], fields: [] };
  let collectionIndent = -1;
  for (const raw of text.split("\n")) {
    const line = stripComment(raw), indent = line.length - line.trimStart().length, body = line.trim();
    if (!body) continue;
    if (indent <= collectionIndent) collectionIndent = -1;
    let m;
    if ((m = body.match(/^cover\s+("[^"]+"|\S+)/))) d.covers.push(m[1]);
    else if ((m = body.match(/^table\s+("[^"]+")/))) d.tables.push(m[1]);
    else if ((m = body.match(/^([A-Za-z_]\w*):\s*((?:money|integer|number|text|yes\/no|date|calculated|choice of|collection of)\b.*)$/))) {
      const [, name, type] = m;
      if (type.startsWith("collection of ")) {
        d.collections.push(name); d.items.push(type.slice(14).trim().split(/[\s,]/)[0]); collectionIndent = indent;
      } else {
        (collectionIndent >= 0 ? d.fields : d.names).push(name);
        if (type.startsWith("choice of ")) d.words.push(...type.slice(10).split(",").map(s => s.trim()).filter(Boolean));
      }
    }
  }
  return d;
}

// What a terminal class offers, by the rule that wants it: [[names, type], ...].
function offered(rule, value, d) {
  if (rule === "cover_name") return [[d.covers, "class"]];
  if (value === "string") return [[rule === "lookup" ? d.tables : [], "text"]];
  if (value === "collection_name") return [[d.collections, "namespace"]];
  if (value === "item_name" || value === "old_item_name") return [[d.items, "namespace"]];
  if (value === "field_name") return [[d.fields, "property"]];
  if (value === "name") return [[[...d.names, ...d.fields], "variable"], [d.words, "constant"], [d.covers.filter(c => !c.startsWith('"')), "class"]];
  if (value === "word") return [[d.words, "constant"]];
  return [];
}

// A literal, extended through any literals that must follow it (`does not count towards ...`).
function phrase(rules, rule, value, target) {
  let label = value, state = rules[rule][target];
  while (!state.accept && state.edges.length === 1 && state.edges[0][0] === "lit") {
    const word = state.edges[0][1];
    label += (word === "," || word === ":" ? "" : " ") + word;
    state = rules[rule][state.edges[0][2]];
  }
  return label;
}

const WORD_BEFORE = /(co-payment|[A-Za-z_][A-Za-z0-9_\/]*)$/;

// Completions at `pos` in `text`, or null: {from, options: [{label, type, boost}]}.
export function completions(table, text, pos) {
  const before = text.slice(0, pos);
  const word = before.match(WORD_BEFORE);
  const from = word ? pos - word[0].length : pos;
  const upTo = before.slice(0, from);
  const lineStart = upTo.lastIndexOf("\n") + 1;
  if (stripComment(upTo.slice(lineStart)).length < upTo.slice(lineStart).trimEnd().length) return null;  // in a comment
  const starts = [0];
  for (let nl = upTo.indexOf("\n"); nl >= 0; nl = upTo.indexOf("\n", nl + 1)) starts.push(nl + 1);
  const blockStart = starts.reverse().find(i => /^[A-Za-z_]/.test(upTo.slice(i))) ?? -1;
  const slice = blockStart < 0 ? upTo : upTo.slice(blockStart);
  const start = blockStart < 0 ? table.start : /^product\b/.test(slice) ? "product_block$line" : "block$line";
  let tokens;
  try { tokens = tokenise(slice, true); } catch (e) { return null; }
  const walker = new Walker(table, start);
  for (const tok of tokens) if (!walker.feed(tok)) return null;
  let expected = walker.expected();
  if (walker.accepted() && /(^|\n)$/.test(upTo)) expected = expected.concat(new Walker(table, "block$line").expected());  // a new block may start
  const d = declared(text), seen = new Set(), options = [];
  const add = (label, type, boost) => { if (label && !seen.has(label)) { seen.add(label); options.push({ label, type, boost }); } };
  for (const { rule, kind, value, target } of expected) {
    if (kind === "lit") add(phrase(table.rules, rule, value, target), /^[A-Za-z"]/.test(value) ? "keyword" : "text", 1);
    else if (kind === "cls") offered(rule, value, d).forEach(([names, type]) => names.forEach(n => add(n, type, 0)));
  }
  options.sort((a, b) => b.boost - a.boost || a.label.localeCompare(b.label));
  return options.length ? { from, options } : null;
}

// The column a new line after `pos` should start at, or null to keep the current indent:
// one level deeper when the grammar expects nested lines there (`cover Theft` ⏎).
export function indentation(table, text, pos) {
  const before = text.slice(0, pos), lineStart = before.lastIndexOf("\n") + 1;
  const line = before.slice(lineStart), indent = line.length - line.trimStart().length;
  const starts = [0];
  for (let nl = before.indexOf("\n"); nl >= 0; nl = before.indexOf("\n", nl + 1)) starts.push(nl + 1);
  const blockStart = starts.reverse().find(i => /^[A-Za-z_]/.test(before.slice(i))) ?? -1;
  const slice = blockStart < 0 ? before : before.slice(blockStart);
  const start = blockStart < 0 ? table.start : /^product\b/.test(slice) ? "product_block$line" : "block$line";
  let tokens;
  try { tokens = tokenise(slice, true); } catch (e) { return null; }
  const walker = new Walker(table, start);
  for (const tok of [...tokens, { kind: "NEWLINE", text: "" }]) if (!walker.feed(tok)) return null;
  return walker.expected().some(e => e.kind === "tok" && e.value === "INDENT") ? indent + 2 : null;
}

// A CodeMirror completion source over the table.
export function completionSource(table) {
  return context => {
    const result = completions(table, context.state.doc.toString(), context.pos);
    return result && { ...result, validFor: /^(co-payment|[A-Za-z_][A-Za-z0-9_\/]*)$/ };
  };
}
