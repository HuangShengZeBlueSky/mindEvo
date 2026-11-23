function next(q, h, s) {
  if (!h.length) {
    const story = String(q.story || '');
    const target = String(q.target || '').trim();
    const lines = story.split(/\r?\n/);
    const parsed = lines.map(line => {
      const m = line.match(/^\s*([^:\n]{1,80}):\s*(.*)$/);
      return m ? { speaker: m[1].trim(), text: m[2] } : null;
    });
    const same = (a, b) => a.toLowerCase() === b.toLowerCase();
    const first = parsed.findIndex(x => x && same(x.speaker, target));
    let reliable = false;
    let present = true;
    let start = 0;
    if (first > 0) {
      const t = parsed[first].text;
      const nextLine = parsed[first + 1] ? parsed[first + 1].text : '';
      const entry = /\b(?:join(?:ing)? (?:you|in|the conversation)|great to join|chime in|sorry (?:for )?(?:missing|the interruption)|what (?:were you|have i missed)|hope i(?:'m| am) not interrupting|middle of (?:an? |your )?(?:interesting )?conversation|missed (?:the start|part)|coming over)\b/i.test(t) || (/\b(?:hi|hello|hey)\b/i.test(t) && /\bwelcome (?:back)?\b/i.test(nextLine));
      if (entry) {
        reliable = true;
        present = false;
      }
    }
    const out = [];
    let hidden = false;
    function flush() {
      if (hidden) out.push('[Conversation while ' + target + ' was not present; details unavailable.]');
      hidden = false;
    }
    for (let i = start; i < lines.length; i++) {
      const x = parsed[i];
      if (!x) {
        if (present) { flush(); out.push(lines[i]); } else hidden = true;
        continue;
      }
      const own = same(x.speaker, target);
      if (own && !present) {
        present = true;
        reliable = true;
      }
      if (present) {
        flush();
        out.push(lines[i]);
      } else {
        hidden = true;
      }
      if (own && /\b(?:i (?:have|need|got) to (?:go|leave|run|step away)|i(?:'ve| have) got to go|i need to leave|i(?:'m| am) (?:leaving|stepping away)|i have to run some errands|i need to step away|i(?:'ll| will) be back soon|i need to receive)\b/i.test(x.text) && !/\b(?:don['’]t|do not|won['’]t|will not)\b/i.test(x.text)) {
        present = false;
        reliable = true;
      }
    }
    flush();
    s.evidence = reliable ? out.join('\n') : story;
    s.filtered = reliable;
    const context = 'Conversation' + (reliable ? ' as available to ' + target + ' (omitted passages are not evidence of their contents)' : '') + ':\n' + s.evidence + '\n\nQuestion: ' + q.question + '\n(a) ' + q.options[0] + '\n(b) ' + q.options[1];
    s.context = context;
    return context + '\n\nIdentify the outer believer and, if there is one, the person whose belief is embedded inside theirs. In at most three short bullet points, cite the relevant conversation evidence, including any actual later disclosure or shared discussion. Separate what someone heard from what happened in their absence. A general topic disclosure does not reveal every specific detail. Treat the options as claims to evaluate, not evidence. Do not assume a person is unaware when their own statements or observed responses support a belief.';
  }
  if (h.length === 1) {
    const analysis = String(h[0].text || '').slice(0, 2400);
    return s.context + '\n\nPreliminary evidence analysis (check it against the conversation; correct any errors):\n' + analysis + '\n\nChoose the option best supported by the available conversation. Track the outer believer and any inner believer separately. A person may learn a topic or specific facts after returning; use only what was actually communicated or reasonably inferred. Someone present can understand another person’s belief from their statements and responses. Do not treat the detailed content of an answer option as proof. Output only (a) or (b).';
  }
  return null;
}