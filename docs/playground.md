---
title: Playground
nav_order: 6
---

# Playground

Write a product here and check it. The engine runs in your browser: this page loads
CPython through [Pyodide](https://pyodide.org) (about 10 MB, fetched once) and the Open IDL
engine straight from the repository, so nothing you type leaves your machine.

<div class="oidl-play">
<div class="bar">
<label for="pg-example">Start from</label>
<select id="pg-example">
<optgroup label="Examples">
<option value="examples/cycle.idl">Cycle</option>
<option value="examples/family.idl">Cycle, several bikes</option>
<option value="examples/multibike.idl">Cycle, ranked bikes</option>
<option value="examples/gadget.idl">Gadget, four countries</option>
<option value="examples/home.idl">Home contents</option>
<option value="examples/household.idl">Buildings and contents</option>
<option value="examples/travel.idl">Single-trip travel</option>
<option value="examples/pet.idl">Lifetime pet</option>
<option value="examples/motor.idl">Private motor</option>
<option value="examples/van.idl">Light commercial vehicle</option>
<option value="examples/life.idl">Level term life</option>
<option value="examples/mortality.idl">Term life from a curve</option>
<option value="examples/income.idl">Income protection</option>
<option value="examples/pi.idl">Professional indemnity</option>
<option value="examples/runoff.idl">Professional indemnity run-off</option>
<option value="examples/leasing.idl">Cycle leasing scheme</option>
</optgroup>
<optgroup label="Templates">
<option value="templates/annual-product.idl">Annual product</option>
<option value="templates/multi-item-product.idl">Several items on one policy</option>
<option value="templates/fixed-term-benefit.idl">Fixed-term benefit</option>
<option value="templates/commercial-claims-made.idl">Commercial claims-made</option>
<option value="templates/rated-from-a-table.idl">Rated from a table</option>
</optgroup>
</select>
<button id="pg-run" class="btn btn-primary" disabled>Check</button>
<span id="pg-status" class="status" aria-live="polite">Loading the engine...</span>
</div>
<div id="pg-src" class="editor" aria-label="Product source"></div>
<p class="hint">As you type, a list offers what the grammar allows next and the names the product declares; Ctrl-Space opens it, Enter or Tab takes a suggestion, Tab indents. Anything after # is a comment. Products with a rating table in a CSV file get the file fetched alongside.</p>
<pre id="pg-out" class="check-out" aria-label="Check output" aria-live="polite"></pre>
</div>

Change an `expect` line and check again to see a failure; change a rate and watch the
scenarios that pin it fail. The [command line](cli.md) page shows the same `check` run
locally, where it belongs in a pipeline.

<script src="https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.js"></script>
<script type="importmap">
{"imports": {
  "codemirror": "https://esm.sh/*codemirror@6.0.2",
  "@codemirror/state": "https://esm.sh/*@codemirror/state@6.7.4",
  "@codemirror/view": "https://esm.sh/*@codemirror/view@6.43.11",
  "@codemirror/language": "https://esm.sh/*@codemirror/language@6.12.4",
  "@codemirror/autocomplete": "https://esm.sh/*@codemirror/autocomplete@6.20.3",
  "@codemirror/commands": "https://esm.sh/*@codemirror/commands@6.11.0",
  "@lezer/common": "https://esm.sh/*@lezer/common@1.5.2",
  "@lezer/highlight": "https://esm.sh/*@lezer/highlight@1.2.3",
  "@lezer/lr": "https://esm.sh/*@lezer/lr@1.4.10",
  "style-mod": "https://esm.sh/*style-mod@4.1.3",
  "w3c-keyname": "https://esm.sh/*w3c-keyname@2.2.8",
  "crelt": "https://esm.sh/*crelt@1.0.7"
}}
</script>
<script type="module" src="{{ site.baseurl }}/assets/js/playground.js"></script>
