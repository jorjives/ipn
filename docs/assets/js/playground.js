// Runs `check` in the browser. Pyodide brings CPython; the engine and the products come
// from the repository at main, so the playground always runs what the site describes. The
// editor is CodeMirror, coloured by ipn.js's classify() and completed from the grammar table.
import { EditorView, keymap, lineNumbers, highlightActiveLine, drawSelection } from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { StreamLanguage, syntaxHighlighting, HighlightStyle, indentUnit, indentService } from "@codemirror/language";
import { autocompletion, completionKeymap } from "@codemirror/autocomplete";
import { tags } from "@lezer/highlight";
import { completionSource, indentation } from "./ipn-complete.js";

const REPO = "https://raw.githubusercontent.com/jorjives/open-idl/main/";
const ENGINE = ["__init__.py", "__main__.py", "cli.py", "engine.py", "expr.py", "model.py",
                "parser.py", "scenarios.py", "tables.py", "versions.py"];
const CHECK = "import io, contextlib\nfrom ipngine import cli\nbuf = io.StringIO()\n" +
              "with contextlib.redirect_stdout(buf):\n    cli.main(['check', '/work/product.ipn'])\nbuf.getvalue()\n";
const out = document.getElementById("pg-out"), run = document.getElementById("pg-run"),
      pick = document.getElementById("pg-example"), status = document.getElementById("pg-status");
let siblings = {};  // CSV files the loaded product refers to, written beside it at check time

function say(text) { status.textContent = text; }
function fetchText(path) {
  return fetch(REPO + path).then(r => { if (!r.ok) throw new Error(path + ": " + r.status); return r.text(); });
}

// --- editor -----------------------------------------------------------------

const STYLE = { c: "comment", s: "string", n: "number", k: "definitionKeyword", ty: "typeName", kw: "keyword" };
const idl = StreamLanguage.define({
  startState: () => ({ atStart: true, indent: 0 }),
  token(stream, state) {
    if (stream.sol()) { state.atStart = true; state.indent = stream.indentation(); }
    if (stream.eatSpace()) return null;
    const classify = window.oidlClassify || (rest => [null, rest.length]);  // ipn.js may be a cached copy without it
    const [cls, len] = classify(stream.string.slice(stream.pos), state.atStart, state.indent);
    stream.pos += len;
    state.atStart = false;
    return cls ? STYLE[cls] : null;
  },
});
const colours = HighlightStyle.define([  // the same classes ipn.js gives the reference pages
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

const view = new EditorView({
  parent: document.getElementById("pg-src"),
  state: EditorState.create({
    doc: "",
    extensions: [
      lineNumbers(), history(), drawSelection(), highlightActiveLine(), indentUnit.of("  "),
      idl, syntaxHighlighting(colours), EditorView.lineWrapping,
      keymap.of([...completionKeymap, ...defaultKeymap, ...historyKeymap, indentWithTab]),
      await completion,
    ],
  }),
});
window.oidlEditor = view;  // a handle for browser checks
const source = () => view.state.doc.toString();
const replace = text => view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });

// --- engine -----------------------------------------------------------------

const engine = loadPyodide().then(py =>
  Promise.all(ENGINE.map(f => fetchText("ipngine/" + f))).then(files => {
    py.FS.mkdirTree("/work/ipngine");
    files.forEach((text, i) => py.FS.writeFile("/work/ipngine/" + ENGINE[i], text));
    py.runPython("import sys; sys.path.insert(0, '/work')");
    return py;
  }));
engine.then(() => { say("Ready."); run.disabled = false; },
            e => say("The engine could not load: " + e.message));

function load(path) {
  say("Loading " + path + "...");
  fetchText(path).then(text => {
    replace(text);
    out.textContent = "";
    siblings = {};
    const dir = path.slice(0, path.lastIndexOf("/") + 1);
    const names = (text.match(/from "([^"]+\.csv)"/g) || []).map(m => m.slice(6, -1));
    return Promise.all(names.map(f => fetchText(dir + f).then(t => { siblings[f] = t; })));
  }).then(() => say(run.disabled ? "Loading the engine..." : "Ready."),
          e => say("Could not load " + path + ": " + e.message));
}

run.addEventListener("click", () => {
  say("Checking...");
  engine.then(py => {
    py.FS.writeFile("/work/product.ipn", source());
    Object.keys(siblings).forEach(f => py.FS.writeFile("/work/" + f, siblings[f]));
    out.textContent = py.runPython(CHECK).replace(/\/work\/product\.ipn/g, "product.ipn");
    window.oidlCheckOutput(out);
    say("Ready.");
  }).catch(e => { out.textContent = String(e); say("Ready."); });
});
pick.addEventListener("change", () => load(pick.value));
load(pick.value);
