function next(q, history, state) {
  if (!history.length) return q.pictureFirst;
  if (history.length === 1) return q.pictureLast.replace("{perspective}", () => history[0].text);
  return null;
}
