(function () {
  var TIMER_MS = 15000;
  var startTime = Date.now();
  var timerInterval = null;
  var answered = false;

  var timerBar = document.getElementById('timer-bar');
  var timerLabel = document.getElementById('timer-label');

  function submitAnswer(answer) {
    if (answered) return;
    answered = true;
    clearInterval(timerInterval);
    var elapsed = Date.now() - startTime;
    document.getElementById('answer-input').value = answer;
    document.getElementById('response-time-input').value = elapsed;
    document.getElementById('answer-form').submit();
  }

  document.querySelectorAll('.answer-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      submitAnswer(btn.getAttribute('data-answer'));
    });
  });

  timerInterval = setInterval(function () {
    var elapsed = Date.now() - startTime;
    var remaining = Math.max(0, TIMER_MS - elapsed);
    var pct = (remaining / TIMER_MS) * 100;
    if (timerBar) timerBar.style.width = pct + '%';
    if (timerLabel) timerLabel.textContent = Math.ceil(remaining / 1000) + 's';
    if (remaining <= 0) {
      submitAnswer('timeout');
    }
  }, 100);
})();
