function next(q, h, s) {
  var story = String(q.story || '');
  var question = String(q.question || '');
  var target = String(q.target || '').trim();
  var lines = story.split(/\r?\n/);
  var parsed = [];
  var names = [];
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/^\s*([^:\n]{1,60}):\s*(.*)$/);
    if (!m || !/^[A-Za-z][A-Za-z .'-]*$/.test(m[1].trim())) {
      parsed.push(null);
      continue;
    }
    var name = m[1].trim();
    parsed.push({name: name, text: m[2]});
    if (names.indexOf(name) < 0 && !/^(all|everyone)$/i.test(name)) names.push(name);
  }
  function esc(x) { return x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function nestedCandidates() {
    var found = [];
    for (var j = 0; j < names.length; j++) {
      var n = names[j];
      if (n.toLowerCase() === target.toLowerCase()) continue;
      var re = new RegExp('\\b' + esc(n) + '\\s+(?:believes?|thinks?|knows?|understands?|is\\s+aware|was\\s+aware|thought|believed|knew)\\b', 'i');
      if (re.test(question)) found.push(n);
    }
    return found;
  }
  if (!h.length) {
    return 'Identify the direct holder of the belief being evaluated. In a genuinely nested question like “What does Alice believe Bob thinks?”, answer Bob. In “What does Alice believe about Bob?” or “What does Alice believe Bob did?”, answer Alice: the person discussed is not necessarily a believer. A question can contain another person in a quoted fact or mistaken premise without asking for that person’s belief. Output only one exact name from the list.\nNames: ' + names.join(', ') + '\nOuter person: ' + target + '\nQuestion: ' + question;
  }
  if (h.length === 1) {
    var answer = String(h[0].text || '').trim().replace(/^[\s"'`]+|[\s"'`.,:;!]+$/g, '');
    var candidates = nestedCandidates();
    var outer = names.filter(function(n) { return n.toLowerCase() === target.toLowerCase(); });
    var matched = names.filter(function(n) { return n.toLowerCase() === answer.toLowerCase(); });
    var person = '';
    if (outer.length === 1 && candidates.length === 0) person = outer[0];
    else if (candidates.length === 1) person = candidates[0];
    else if (candidates.length > 1 && matched.length === 1 && candidates.indexOf(matched[0]) >= 0) person = matched[0];
    function fallback() { s.mode = 'picture'; return String(q.pictureFirst || ''); }
    if (!person || !target || names.length < 2) return fallback();
    var first = -1;
    for (var k = 0; k < parsed.length; k++) {
      if (parsed[k] && parsed[k].name === person) { first = k; break; }
    }
    if (first < 0) return fallback();
    var arrival = /\b(?:i(?:'m|’m| am) back|i(?:'ve|’ve| have) returned|glad to be back|back again|(?:hi|hello|hey) again|(?:join|joining|joined) (?:in|you|the conversation|the discussion)|(?:couldn['’]t help but|just) (?:overhear|overheard|hear|heard|catch|caught|join)|(?:hope i (?:haven['’]t|didn['’]t) miss|sorry (?:i|to have) (?:had to |have )?(?:step(?:ped)? away|missed))|(?:finished|just finished) (?:my |a )?(?:phone )?call|hope i['’]m not interrupting|hope i am not interrupting)\b/i;
    var departure = /\b(?:i (?:need|have|have got|got) to (?:leave|go|head out|step away|step out|duck out|get going)|i(?:'ll|’ll| will) have to (?:leave|go|catch up)|i(?:'m|’m| am) (?:going to |gonna )?(?:leave|head out|step away|step out|duck out)|i(?:'ll|’ll| will) (?:be back|catch up|join (?:you |the conversation )?(?:again |as soon as))|i must (?:take my leave|be on my way|leave|go)|i have to check on something|i hate to (?:duck out|cut this)|(?:carry on|continue) (?:with the conversation|without me)|(?:excuse me|do excuse me)[^.!?]{0,80}\b(?:for a (?:moment|bit|while)|i have to go))\b/i;
    var returning = /\b(?:i(?:'m|’m| am) back|i(?:'ve|’ve| have) returned|(?:hi|hello|hey) again|glad to be back|back again|sorry to have missed|apologies for the interruption|sorry about (?:the interruption|that)|sorry i had to leave)\b/i;
    var prior = 0;
    for (var p = 0; p < first; p++) if (parsed[p] && parsed[p].text.trim()) prior++;
    var late = prior >= 3 && arrival.test(parsed[first].text);
    var absent = late;
    var sawBoundary = late;
    var masked = 0;
    var output = [];
    var inGap = false;
    for (var t = 0; t < lines.length; t++) {
      var row = parsed[t];
      if (row && row.name === person && absent) {
        if (t === first && late || returning.test(row.text)) {
          absent = false;
          sawBoundary = true;
        } else {
          return fallback();
        }
      }
      if (absent) {
        if (lines[t].trim()) {
          masked++;
          if (!inGap) output.push('[Some dialogue occurred while ' + person + ' was absent; its specific content is unavailable to ' + person + '.]');
          inGap = true;
        }
      } else {
        output.push(lines[t]);
        inGap = false;
      }
      if (row && row.name === person && departure.test(row.text) && !returning.test(row.text)) {
        absent = true;
        sawBoundary = true;
      }
    }
    if (!sawBoundary || !masked) return fallback();
    s.mode = 'filtered';
    s.person = person;
    s.view = output.join('\n');
    return 'Examine the question using only the visible dialogue. The bracketed gap is speech ' + person + ' did not hear; do not invent its details. Read the time of the question carefully: speech after someone joins or returns is heard by those present. A general mention of a topic does not reveal every specific detail, but later explicit statements can convey details. In a nested belief, distinguish what ' + target + ' can infer from what ' + person + ' heard, said, or shared with others. A speaker knows their own statements.\n\nDialogue:\n' + s.view + '\n\nQuestion: ' + question + '\n\nGive at most three short bullets: identify the relevant visible statements, when the relevant people were present, and whether the specific information asked about was actually conveyed. Do not guess missing dialogue.';
  }
  if (h.length === 2) {
    if (s.mode === 'filtered') {
      return 'Answer from the dialogue and question. The gap hides only speech that ' + s.person + ' did not hear; it does not hide speech before departure or after arrival or return. Shared conversation and a person’s own statements are evidence of knowledge. A general topic summary conveys only what it says, while a later specific statement can convey specific facts. For nested beliefs, consider what ' + target + ' can reasonably infer about ' + s.person + ' from shared, visible events. Check the time asked about. Compare both options against the actual evidence; do not automatically choose ignorance because a gap exists.\n\nDialogue:\n' + s.view + '\n\nEarlier evidence notes, which may contain errors:\n' + String(h[1].text || '') + '\n\nQuestion: ' + question + '\n(a) ' + String(q.options[0]) + '\n(b) ' + String(q.options[1]) + '\n\nChoose the better-supported option. Output only (a) or (b).';
    }
    return String(q.pictureLast || '').replace('{perspective}', function() { return String(h[1].text || ''); }) + '\nOutput only (a) or (b).';
  }
  return null;
}