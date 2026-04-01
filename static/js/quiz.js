(function () {
  const TIMER_MS = 15000;
  let startTime = Date.now();
  let timerInterval = null;
  let answered = false;

  function submitAnswer(answer) {
    if (answered) return;
    answered = true;
    clearInterval(timerInterval);
    const elapsed = Date.now() - startTime;
    document.getElementById('answer-input').value = answer;
    document.getElementById('response-time-input').value = elapsed;
    document.getElementById('answer-form').submit();
  }

  document.querySelectorAll('.answer-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      submitAnswer(btn.dataset.answer);
    });
  });

  timerInterval = setInterval(function () {
    const elapsed = Date.now() - startTime;
    if (elapsed >= TIMER_MS) {
      submitAnswer('timeout');
    }
  }, 100);
})();
