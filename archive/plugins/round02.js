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
    if (names.indexOf(name) < 0) names.push(name);
  }
  if (!h.length) {
    return 'Identify the person whose knowledge or belief is directly being asked about. In a nested question such as “What does Alice believe Bob thinks about ...?”, choose Bob; for “What does Alice believe about ...?”, choose Alice unless the question asks about another person’s understanding or belief. Do not choose the person merely discussed as the subject of a fact. Output only the exact name from the list, with no explanation.\nNames: ' + names.join(', ') + '\nQuestion: ' + question;
  }
  if (h.length === 1) {
    var answer = String(h[0].text || '').trim().replace(/^[\s"'`]+|[\s"'`.,:;!]+$/g, '');
    var matches = names.filter(function(n) { return n.toLowerCase() === answer.toLowerCase(); });
    var person = matches.length === 1 ? matches[0] : '';
    var fallback = function() { s.mode = 'picture'; return q.pictureFirst; };
    if (!person || !target || names.length < 2) return fallback();
    var first = -1;
    for (var j = 0; j < parsed.length; j++) {
      if (parsed[j] && parsed[j].name === person) { first = j; break; }
    }
    if (first < 0) return fallback();
    var firstText = parsed[first].text;
    var arrival = /\b(?:i(?:'m| am) back|i(?:’m| am) back|i(?:'ve| have) returned|i(?:’ve| have) returned|(?:hi|hello|hey)\b[^.!?]{0,80}\b(?:join|back|missed|conversation|discussion|everyone|guys|folks)|(?:mind if i join|can i join|may i join|couldn['’]t help but (?:overhear|catch)|just (?:overheard|caught)|sorry (?:i|to have) (?:had to |have )?(?:step(?:ped)? away|missed)))\b/i;
    var departure = /\b(?:i (?:need|have|have got|got) to (?:leave|go|head out|step away|step out|duck out|get going)|i(?:'m|’m| am) (?:going to |gonna )?(?:leave|head out|step away|step out|duck out|going to grab)|i(?:'ll|’ll| will) (?:be back|join (?:you |the conversation )?(?:again |as soon as)|catch up (?:later|with you later))|(?:excuse me|do excuse me)[^.!?]{0,80}\b(?:for a (?:moment|bit|while)|i have to go)|i hate to (?:duck out|cut this[^.!?]*short)|continue without me|carry on (?:without me|with the conversation))\b/i;
    var returning = /\b(?:i(?:'m|’m| am) back|i(?:'ve|’ve| have) returned|(?:hi|hello|hey) again|glad to be back|back again|sorry (?:about|for) the interruption)\b/i;
    var prior = 0;
    for (var k = 0; k < first; k++) if (parsed[k] && parsed[k].text.trim()) prior++;
    var late = prior >= 3 && arrival.test(firstText);
    var absent = late;
    var sawBoundary = late;
    var masked = 0;
    var out = [];
    var inGap = false;
    for (var t = 0; t < lines.length; t++) {
      var row = parsed[t];
      if (row && row.name === person) {
        if (absent && (t === first || returning.test(row.text))) {
          absent = false;
          sawBoundary = true;
        } else if (absent) {
          return fallback();
        }
      }
      if (absent) {
        if (lines[t].trim()) {
          masked++;
          if (!inGap) out.push('[Conversation occurred while ' + person + ' was absent; its contents are unavailable to ' + person + '.]');
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
    var task = '\nQuestion: ' + question + '\n(a) ' + String(q.options[0]) + '\n(b) ' + String(q.options[1]);
    return 'Use the dialogue as evidence for a belief question. The bracketed gap hides speech that ' + person + ' did not hear; do not infer its specific content. A broad summary after the gap conveys only what it actually says, while specific later statements can convey specific facts. People who were present together can know what they heard, and a speaker knows what they said. For nested beliefs, distinguish the outer believer ' + target + ' from the inner believer ' + person + '. Do not assume that returning reveals missed details.\n\nDialogue as available to ' + person + ':\n' + s.view + task + '\n\nIn at most three short bullets, identify relevant visible evidence, any missing specific information, and which option is better supported. Do not invent dialogue.';
  }
  if (h.length === 2) {
    if (s.mode === 'picture') return q.pictureLast.replace('{perspective}', function() { return String(h[1].text || ''); });
    if (s.mode === 'filtered') {
      return 'Answer the question using the dialogue below. ' + s.person + ' did not hear the content hidden in the gap. Later dialogue may convey general topics or specific details; use exactly what was conveyed. In nested beliefs, consider what ' + s.person + ' heard and what ' + target + ' can reasonably believe about that. When both people heard a discussion, shared knowledge is evidence. Compare the options for supported details.\n\nDialogue:\n' + s.view + '\n\nEarlier brief analysis, which may contain errors:\n' + String(h[1].text || '') + '\n\nQuestion: ' + question + '\n(a) ' + String(q.options[0]) + '\n(b) ' + String(q.options[1]) + '\n\nChoose the better-supported option. Output only (a) or (b).';
    }
    return q.pictureLast.replace('{perspective}', function() { return String(h[1].text || ''); });
  }
  return null;
}