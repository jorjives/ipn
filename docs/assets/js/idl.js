// Colours fenced ```idl blocks. Rouge has no lexer for Open IDL, so the blocks arrive as
// plain text; this wraps block openers, statement words, types, strings, numbers and
// comments in spans styled by _sass/custom/custom.scss.
(function () {
  var BLOCKS = /^(product|inputs|eligibility|cover|rating|lifecycle|claims|scenario|table|enrichment|upgrading)\b/;
  var TYPES = /^(money|integer|number|text|date|calculated|yes\/no|choice|collection)\b/;
  var WORDS = /^(decline|refer|excludes|available|when|because|unless|otherwise|limit|excess|deductible|base|factor|add|discount|load|minimum|maximum|tax|fee|commission|round|cooling|cancellation|adjustment|lapse|renewal|instalments|invite|index|claim|requires|asks|pays|co-payment|depreciation|settlement|counts|given|select|expect|for|each|from|until|per|term|territory|currency|published|optional|waiting|reinstatement|keyed|interpolated|provides|unavailable|held|ordered|selected|and|or|not|is|of|to|by|on|with|x|ask|after|in|force|up|less|claimed|amount|does|count|towards)\b/;
  var STRING = /^"[^"]*"/, DATE = /^\d{4}-\d{2}-\d{2}/, NUM = /^\d+(\.\d+)?%?/, IDENT = /^[A-Za-z_][A-Za-z0-9_\/-]*/;

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function span(cls, s) { return '<span class="' + cls + '">' + esc(s) + "</span>"; }

  function line(text) {
    var out = "", i = 0, atStart = true, m;
    var indent = text.match(/^\s*/)[0];
    out += indent; i = indent.length;
    while (i < text.length) {
      var rest = text.slice(i);
      if (rest[0] === "#") { out += span("c", rest); break; }
      if ((m = rest.match(STRING))) { out += span("s", m[0]); }
      else if ((m = rest.match(DATE))) { out += span("n", m[0]); }
      else if ((m = rest.match(NUM))) { out += span("n", m[0]); }
      else if (atStart && indent.length === 0 && (m = rest.match(BLOCKS))) { out += span("k", m[0]); }
      else if ((m = rest.match(TYPES))) { out += span("ty", m[0]); }
      else if ((m = rest.match(WORDS))) { out += span("kw", m[0]); }
      else if ((m = rest.match(IDENT))) { out += esc(m[0]); }
      else { m = [rest[0]]; out += esc(m[0]); }
      i += m[0].length;
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

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".language-idl pre code, code.idl").forEach(colour);
    document.querySelectorAll(".language-check pre code").forEach(checkOutput);
  });
})();
