// Runs `check` in the browser. Pyodide brings CPython; the engine and the products come
// from the repository at main, so the playground always runs what the site describes.
(function () {
  var REPO = "https://raw.githubusercontent.com/jorjives/open-idl/main/";
  var ENGINE = ["__init__.py", "__main__.py", "cli.py", "engine.py", "expr.py", "model.py",
                "parser.py", "scenarios.py", "tables.py", "versions.py"];
  var CHECK = "import io, contextlib\nfrom ideclare import cli\nbuf = io.StringIO()\n" +
              "with contextlib.redirect_stdout(buf):\n    cli.main(['check', '/work/product.idl'])\nbuf.getvalue()\n";
  var src = document.getElementById("pg-src"), out = document.getElementById("pg-out"),
      run = document.getElementById("pg-run"), pick = document.getElementById("pg-example"),
      status = document.getElementById("pg-status");
  var siblings = {};  // CSV files the loaded product refers to, written beside it at check time

  function say(text) { status.textContent = text; }
  function fetchText(path) {
    return fetch(REPO + path).then(function (r) { if (!r.ok) throw new Error(path + ": " + r.status); return r.text(); });
  }

  var engine = loadPyodide().then(function (py) {
    return Promise.all(ENGINE.map(function (f) { return fetchText("ideclare/" + f); })).then(function (files) {
      py.FS.mkdirTree("/work/ideclare");
      files.forEach(function (text, i) { py.FS.writeFile("/work/ideclare/" + ENGINE[i], text); });
      py.runPython("import sys; sys.path.insert(0, '/work')");
      return py;
    });
  });
  engine.then(function () { say("Ready."); run.disabled = false; },
              function (e) { say("The engine could not load: " + e.message); });

  function load(path) {
    say("Loading " + path + "...");
    fetchText(path).then(function (text) {
      src.value = text;
      out.textContent = "";
      siblings = {};
      var dir = path.slice(0, path.lastIndexOf("/") + 1);
      var names = (text.match(/from "([^"]+\.csv)"/g) || []).map(function (m) { return m.slice(6, -1); });
      return Promise.all(names.map(function (f) { return fetchText(dir + f).then(function (t) { siblings[f] = t; }); }));
    }).then(function () { say(run.disabled ? "Loading the engine..." : "Ready."); },
            function (e) { say("Could not load " + path + ": " + e.message); });
  }

  run.addEventListener("click", function () {
    say("Checking...");
    engine.then(function (py) {
      py.FS.writeFile("/work/product.idl", src.value);
      Object.keys(siblings).forEach(function (f) { py.FS.writeFile("/work/" + f, siblings[f]); });
      out.textContent = py.runPython(CHECK).replace(/\/work\/product\.idl/g, "product.idl");
      window.oidlCheckOutput(out);
      say("Ready.");
    }).catch(function (e) { out.textContent = String(e); say("Ready."); });
  });
  pick.addEventListener("change", function () { load(pick.value); });
  load(pick.value);
})();
