// Prices a prepared book twice in the browser: the original product and an editable
// after file. Pyodide brings CPython; the engine comes from the repository at main;
// the sample files are served with the site. The after editor is CodeMirror, coloured
// by ipn.js's classify() and completed from the grammar table.
import { EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { StreamLanguage, syntaxHighlighting, HighlightStyle, indentUnit, indentService } from "@codemirror/language";
import { autocompletion, completionKeymap } from "@codemirror/autocomplete";
import { tags } from "@lezer/highlight";
import { completionSource, indentation } from "./ipn-complete.js";

const REPO = "https://raw.githubusercontent.com/jorjives/ipn/main/";
const ENGINE = ["__init__.py", "__main__.py", "cli.py", "engine.py", "expr.py", "model.py",
                "parser.py", "scenarios.py", "tables.py", "versions.py"];
const PRICE = `
import csv, io, json
from ipngine.cli import batch
from ipngine.parser import ParseError

def priced(product, risks):
    buf = io.StringIO()
    try:
        code = batch(product, risks, out=buf)
    except ParseError as e:
        return {"error": str(e).replace("/work/", "")}
    text = buf.getvalue()
    if code != 0:
        return {"error": text.strip().splitlines()[0] if text.strip() else "batch failed"}
    return {"rows": list(csv.DictReader(io.StringIO(text)))}

json.dumps({"before": priced("/work/before.ipn", "/work/risks.csv"),
            "after": priced("/work/after.ipn", "/work/risks.csv")})
`;

const out = document.getElementById("bk-out"), run = document.getElementById("bk-run"),
      reset = document.getElementById("bk-reset"), status = document.getElementById("bk-status"),
      book = document.getElementById("bk-risks");
let preparedAfter = "", risks = [], risksCsv = "";

function say(text) { status.textContent = text; }
function fetchText(path) {
  return fetch(REPO + path).then(r => { if (!r.ok) throw new Error(path + ": " + r.status); return r.text(); });
}
function asset(name) {
  return fetch(new URL("../book/" + name, import.meta.url)).then(r => {
    if (!r.ok) throw new Error(name + ": " + r.status);
    return r.text();
  });
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const headers = lines[0].split(",");
  return lines.slice(1).filter(Boolean).map(line => {
    const cells = line.split(",");
    return Object.fromEntries(headers.map((h, i) => [h, cells[i] ?? ""]));
  });
}

// --- editor -----------------------------------------------------------------

const STYLE = { c: "comment", s: "string", n: "number", k: "definitionKeyword", ty: "typeName", kw: "keyword" };
const idl = StreamLanguage.define({
  startState: () => ({ atStart: true, indent: 0 }),
  token(stream, state) {
    if (stream.sol()) { state.atStart = true; state.indent = stream.indentation(); }
    if (stream.eatSpace()) return null;
    const classify = window.oidlClassify || (rest => [null, rest.length]);
    const [cls, len] = classify(stream.string.slice(stream.pos), state.atStart, state.indent);
    stream.pos += len;
    state.atStart = false;
    return cls ? STYLE[cls] : null;
  },
});
const colours = HighlightStyle.define([
  { tag: tags.definitionKeyword, class: "k" }, { tag: tags.keyword, class: "kw" }, { tag: tags.typeName, class: "ty" },
  { tag: tags.string, class: "s" }, { tag: tags.number, class: "n" }, { tag: tags.comment, class: "c" },
]);
const table = fetch(new URL("../ipn-grammar.json", import.meta.url)).then(r => {
  if (!r.ok) throw new Error("ipn-grammar.json: " + r.status);
  return r.json();
});
const completion = table.then(t => [autocompletion({ override: [completionSource(t)], icons: true }),
                                    indentService.of((cx, pos) => indentation(t, cx.state.doc.toString(), pos))],
                              e => { console.error("No completion: " + e.message); return []; });
const common = [
  lineNumbers(), drawSelection(), highlightActiveLine(), indentUnit.of("  "),
  idl, syntaxHighlighting(colours), EditorView.lineWrapping,
];
const beforeView = new EditorView({
  parent: document.getElementById("bk-before"),
  state: EditorState.create({ doc: "", extensions: [...common, EditorState.readOnly.of(true)] }),
});
const afterView = new EditorView({
  parent: document.getElementById("bk-after"),
  state: EditorState.create({
    doc: "",
    extensions: [
      ...common, history(),
      keymap.of([...completionKeymap, ...defaultKeymap, ...historyKeymap, indentWithTab]),
      await completion,
    ],
  }),
});
function source(view) { return view.state.doc.toString(); }
function replace(view, text) {
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
}

// --- engine -----------------------------------------------------------------

const engine = loadPyodide().then(py =>
  Promise.all(ENGINE.map(f => fetchText("ipngine/" + f))).then(files => {
    py.FS.mkdirTree("/work/ipngine");
    files.forEach((text, i) => py.FS.writeFile("/work/ipngine/" + ENGINE[i], text));
    py.runPython("import sys; sys.path.insert(0, '/work')");
    return py;
  }));

const files = Promise.all(["before.ipn", "after.ipn", "risks.csv"].map(asset));
files.then(([before, after, csv]) => {
  preparedAfter = after;
  risksCsv = csv;
  replace(beforeView, before);
  replace(afterView, after);
  risks = parseCsv(csv);
  book.innerHTML = renderBook(risks);
}, e => say("Could not load the sample: " + e.message));

Promise.all([engine, files]).then(([py]) => {
  say("Ready.");
  run.disabled = false;
  reset.disabled = false;
  price(py);
}, e => say("The engine could not load: " + e.message));

function renderBook(rows) {
  const cols = Object.keys(rows[0] || {});
  return "<table><thead><tr>" + cols.map(c => "<th>" + esc(c) + "</th>").join("") +
    "</tr></thead><tbody>" + rows.map(r => "<tr>" + cols.map(c => "<td>" + esc(r[c]) + "</td>").join("") +
    "</tr>").join("") + "</tbody></table>";
}

function delta(before, after) {
  if (before.error || after.error || before.total === "" || after.total === "") return "";
  const d = Number(after.total) - Number(before.total);
  return (d > 0 ? "+" : "") + d.toFixed(2);
}

function compare(beforeRows, afterRows) {
  return beforeRows.map((b, i) => {
    const a = afterRows[i] || {}, r = risks[i] || {};
    const moved = b.eligibility !== a.eligibility || b.total !== a.total || (b.error || "") !== (a.error || "");
    return {
      risk: b.risk, type: r.property_type || "",
      elig: b.eligibility === a.eligibility ? (b.eligibility || a.error || "")
            : (b.eligibility || "—") + " → " + (a.eligibility || a.error || "—"),
      before: b.total, after: a.total, delta: delta(b, a), moved,
    };
  }).sort((x, y) => Number(y.moved) - Number(x.moved) || Math.abs(Number(y.delta || 0)) - Math.abs(Number(x.delta || 0))
                    || Number(x.risk) - Number(y.risk));
}

function renderResult(rows) {
  const head = "<thead><tr><th>Risk</th><th>Type</th><th>Eligibility</th><th>Before</th><th>After</th><th>Delta</th><th></th></tr></thead>";
  const body = rows.map(r => "<tr" + (r.moved ? ' class="moved"' : "") + "><td>" +
    [r.risk, r.type, r.elig, r.before, r.after, r.delta, r.moved ? "Moved" : ""].map(esc).join("</td><td>") +
    "</td></tr>").join("");
  return "<table>" + head + "<tbody>" + body + "</tbody></table>";
}

function price(py) {
  say("Pricing...");
  py.FS.writeFile("/work/before.ipn", source(beforeView));
  py.FS.writeFile("/work/after.ipn", source(afterView));
  py.FS.writeFile("/work/risks.csv", risksCsv);
  try {
    const result = JSON.parse(py.runPython(PRICE));
    if (result.before.error || result.after.error) {
      out.innerHTML = "<pre class=\"check-out\">" + esc(result.after.error || result.before.error) + "</pre>";
    } else {
      out.innerHTML = renderResult(compare(result.before.rows, result.after.rows));
    }
  } catch (e) {
    out.textContent = String(e);
  }
  say("Ready.");
}

run.addEventListener("click", () => engine.then(price).catch(e => { out.textContent = String(e); say("Ready."); }));
reset.addEventListener("click", () => replace(afterView, preparedAfter));
window.oidlBook = { beforeView, afterView };
