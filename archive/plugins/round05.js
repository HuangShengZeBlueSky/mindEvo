function next(q, h, s) {
  var story = String(q.story || '');
  var question = String(q.question || '');
  var target = String(q.target || '').trim();
  var options = q.options || [];
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
    if (names.indexOf(name) < 0 && !/^(all|everyone|both)$/i.test(name)) names.push(name);
  }
  if (!h.length) {
    return 'Identify the person whose own knowledge, understanding, thoughts or belief is embedded in the question. For “What does A believe B thinks...?” or “What does A believe about B\'s understanding...?”, choose B. For “What does A believe B said, suggested, did, or prefers?”, choose A: B is the subject of a fact, not necessarily an embedded believer. If there is no embedded belief, choose the outer believer. Output only the exact name from the list.\nNames: ' + names.join(', ') + '\nOuter believer: ' + target + '\nQuestion: ' + question;
  }
  if (h.length === 1) {
    var answer = String(h[0].text || '').trim().replace(/^[\s"'`]+|[\s"'`.,:;!]+$/g, '');
    var matches = names.filter(function(n) { return n.toLowerCase() === answer.toLowerCase(); });
    var person = matches.length === 1 ? matches[0] : '';
    var fallback = function() { s.mode = 'picture'; return String(q.pictureFirst || ''); };
    if (!person || !target || names.length < 2) return fallback();
    var first = -1;
    for (var j = 0; j < parsed.length; j++) {
      if (parsed[j] && parsed[j].name === person) { first = j; break; }
    }
    if (first < 0) return fallback();
    var arrival = /\b(?:i(?:'m|’m| am) back|i(?:'ve|’ve| have) returned|just (?:got|came) back|hi|hello|hey|greetings|mind if i join|can i join|may i join|(?:could(?:n't|n’t)|could not) help but (?:overhear|catch|join|notice)|just (?:overheard|caught|joined)|(?:sorry|apologies)[^.!?]{0,45}\b(?:late|delay|interrupt|away)|entering|coming over|joining|(?:i hope|hope) i(?:'m|’m| am) not interrupting)\b/i;
    var departure = /\b(?:i (?:need|have|have got|got) to (?:leave|go|head out|step away|step out|duck out|get going|run)|i(?:'m|’m| am) (?:going to |gonna )?(?:leave|head out|step away|step out|duck out|going to grab)|i(?:'ll|’ll| will) (?:have to |need to )?(?:leave|go|be back|catch up)|i have to (?:go|leave|run|check|pick up)|i (?:have|need) to take (?:this|a) (?:phone )?call|i (?:got|have) to go for a (?:quick )?(?:bathroom|break)|i hate to (?:duck out|cut this[^.!?]*short)|(?:excuse me|do excuse me)[^.!?]{0,80}\b(?:for a (?:moment|bit|while)|i have to)|continue without me|carry on (?:without me|with the conversation)|in my absence|(?:see|catch) you (?:both |all )?later)\b/i;
    var returning = /\b(?:i(?:'m|’m| am) back|i(?:'ve|’ve| have) returned|just (?:got|came) back|(?:hi|hello|hey) again|hello again|glad to be back|back again|welcome back|finish(?:ed)? my errands|sorry (?:about|for) the interruption)\b/i;
    var prior = 0;
    for (var k = 0; k < first; k++) if (parsed[k] && parsed[k].text.trim()) prior++;
    var late = prior >= 3 && arrival.test(parsed[first].text);
    var absent = late;
    var sawBoundary = late;
    var masked = 0;
    var out = [];
    var inGap = false;
    for (var t = 0; t < lines.length; t++) {
      var row = parsed[t];
      if (row && row.name === person && absent) {
        if (t === first || returning.test(row.text) || /\b(?:hi|hello|hey)\b/i.test(row.text)) {
          absent = false;
          sawBoundary = true;
        } else {
          return fallback();
        }
      }
      if (absent) {
        if (lines[t].trim()) {
          masked++;
          if (!inGap) out.push('[Conversation occurred while ' + person + ' was absent; its specific contents are unavailable to ' + person + '.]');
          inGap = true;
        }
      } else {
        out.push(lines[t]);
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
    s.view = out.join('\n');
    return 'Answer this belief question using the dialogue available to ' + person + '. A gap hides speech that this person did not hear. Do not reconstruct hidden details from the options or general knowledge. All shown dialogue after arrival or return is available: a specific statement or specific retelling can convey information, but a broad summary does not convey unstated details. Pay attention to whether the question asks about events before, during, or after joining. For a nested belief, distinguish outer believer ' + target + ' from inner believer ' + person + '; shared presence and observable statements can support what the outer believer thinks the inner person knows. Do not assume ignorance just because a person was absent at another time.\n\nDialogue:\n' + s.view + '\n\nQuestion: ' + question + '\n(a) ' + String(options[0] || '') + '\n(b) ' + String(options[1] || '') + '\n\nIn at most three short bullets, cite the most relevant visible statements, identify which specific claims in the options were or were not conveyed in the relevant period, and say which option is better supported. Do not invent dialogue.';
  }
  if (h.length === 2) {
    if (s.mode !== 'filtered') return String(q.pictureLast || '').replace('{perspective}', function() { return String(h[1].text || ''); });
    return 'Choose the better-supported answer to the belief question. The gap hides content not heard by ' + s.person + '; do not treat the options as evidence of what was said. After arrival or return, all shown dialogue is available, including specific information actually shared. A general summary conveys only what it says. Check the time period asked about: events after joining can be known even if earlier events were missed. Shared presence and observed statements can support nested beliefs; do not assume ignorance merely because someone was absent earlier. Check the earlier analysis against the dialogue.\n\nDialogue:\n' + s.view + '\n\nEarlier brief analysis (it may contain errors):\n' + String(h[1].text || '') + '\n\nQuestion: ' + question + '\n(a) ' + String(options[0] || '') + '\n(b) ' + String(options[1] || '') + '\n\nOutput only (a) or (b).';
  }
  return null;
}