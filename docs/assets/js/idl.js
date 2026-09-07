// Colours fenced ```idl blocks. Rouge has no lexer for Open IDL, so the blocks arrive as
// plain text; this wraps block openers, statement words, types, strings, numbers and
// comments in spans styled by _sass/custom/custom.scss. The playground editor colours its
// text with the same classify() so the two never disagree.
(function () {
  var BLOCKS = /^(product|inputs|eligibility|cover|rating|lifecycle|claims|scenario|table|enrichment|upgrading)\b/;
  var TYPES = /^(money|integer|number|text|date|calculated|yes\/no|choice|collection)\b/;
  var WORDS = /^(decline|refer|excludes|available|when|because|unless|otherwise|limit|excess|deductible|base|factor|add|discount|load|minimum|maximum|tax|fee|commission|round|cooling|cancellation|adjustment|lapse|renewal|instalments|invite|index|claim|requires|asks|pays|co-payment|depreciation|settlement|counts|given|select|expect|for|each|from|until|per|term|territory|currency|published|optional|waiting|reinstatement|class|premium|premiums|allocate|keyed|interpolated|provides|unavailable|held|ordered|selected|and|or|not|is|of|to|by|on|with|x|ask|after|in|force|up|less|claimed|amount|does|count|towards)\b/;
  var STRING = /^"[^"]*"/, DATE = /^\d{4}-\d{2}-\d{2}/, NUM = /^\d+(\.\d+)?%?/, IDENT = /^[A-Za-z_][A-Za-z0-9_\/-]*/;

  // The class and length of the token at the start of `rest`: c, s, n, k, ty, kw, or null for
  // plain text. `atStart` and `indent` say whether a block opener is possible here.
  function classify(rest, atStart, indent) {
    var m;
    if (rest[0] === "#") return ["c", rest.length];
    if ((m = rest.match(STRING))) return ["s", m[0].length];
    if ((m = rest.match(DATE))) return ["n", m[0].length];
    if ((m = rest.match(NUM))) return ["n", m[0].length];
    if (atStart && indent === 0 && (m = rest.match(BLOCKS))) return ["k", m[0].length];
    if ((m = rest.match(TYPES))) return ["ty", m[0].length];
    if ((m = rest.match(WORDS))) return ["kw", m[0].length];
    if ((m = rest.match(IDENT))) return [null, m[0].length];
    return [null, 1];
  }

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function span(cls, s) { return '<span class="' + cls + '">' + esc(s) + "</span>"; }

  function line(text) {
    var out = "", i = 0, atStart = true;
    var indent = text.match(/^\s*/)[0];
    out += indent; i = indent.length;
    while (i < text.length) {
      var rest = text.slice(i);
      var tok = classify(rest, atStart, indent.length), cls = tok[0], len = tok[1];
      out += cls ? span(cls, rest.slice(0, len)) : esc(rest.slice(0, len));
      i += len;
      atStart = false;
    }
    return out;
  }

  function colour(code) {
    code.innerHTML = code.textContent.split("\n").map(line).join("\n");
  }

  function checkOutput(code) {
    code.innerHTML = code.textContent.split("\n").map(function (t) {
      if (/^PASS /.test(t)) return span("pass", "PASS") + esc(t.slice(4));
      if (/^FAIL /.test(t)) return span("fail", "FAIL") + esc(t.slice(4));
      return esc(t);
    }).join("\n");
  }

  window.oidlClassify = classify;      // the playground's editor tokenises with it
  window.oidlCheckOutput = checkOutput;  // and colours its output the same way

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".language-idl pre code, code.language-idl, code.idl").forEach(colour);
    document.querySelectorAll(".language-check pre code, code.language-check").forEach(checkOutput);
  });
})();
