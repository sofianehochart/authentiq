(function () {
  var TIMER_MS = 15000;
  var startTime = Date.now();
  var timerInterval = null;
  var answered = false;

  var timerBar = document.getElementById('timer-bar');
  var timerLabel = document.getElementById('timer-label');
  var wrap = document.getElementById('sm-card-wrap');
  var card = document.getElementById('sm-card');

  function hash32(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0);
  }

  function mulberry32(a) {
    return function () {
      var t = a += 0x6D2B79F5;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function initialsFromName(name) {
    name = (name || '').trim();
    if (!name) return '?';
    var parts = name.split(/\s+/).filter(Boolean);
    var a = parts[0] ? parts[0][0] : '?';
    var b = parts.length > 1 ? parts[parts.length - 1][0] : '';
    return (a + b).toUpperCase();
  }

  function colorFromName(name) {
    var palette = ['#7c3aed', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#22c55e', '#a855f7'];
    var idx = hash32(name || '') % palette.length;
    return palette[idx];
  }

  function formatCount(n) {
    if (n >= 1000000) return (Math.round(n / 100000) / 10) + 'M';
    if (n >= 1000) return (Math.round(n / 100) / 10) + 'K';
    return String(n);
  }

  function setMockStats() {
    if (!wrap) return;
    var qid = wrap.getAttribute('data-question-id') || '0';
    var persona = wrap.getAttribute('data-persona') || '';
    var handle = wrap.getAttribute('data-handle') || '';
    var seed = hash32(qid + '|' + persona + '|' + handle);
    var rnd = mulberry32(seed);

    var initials = initialsFromName(persona);
    var color = colorFromName(persona);
    document.querySelectorAll('[data-persona-name]').forEach(function (el) { el.textContent = persona; });
    document.querySelectorAll('[data-handle-text]').forEach(function (el) { el.textContent = handle; });
    document.querySelectorAll('[data-initials]').forEach(function (el) {
      el.textContent = initials;
      el.style.background = color;
    });
    document.querySelectorAll('[data-initials-text]').forEach(function (el) { el.textContent = initials; });

    // tweet-like counts
    var replies = Math.floor(20 + rnd() * 900);
    var retweets = Math.floor(80 + rnd() * 7000);
    var likes = Math.floor(200 + rnd() * 65000);
    var rEl = document.querySelector('[data-replies]');
    var rtEl = document.querySelector('[data-retweets]');
    var lEl = document.querySelector('[data-likes]');
    if (rEl) rEl.textContent = formatCount(replies);
    if (rtEl) rtEl.textContent = formatCount(retweets);
    if (lEl) lEl.textContent = formatCount(likes);

    // instagram-like counts
    var hearts = Math.floor(300 + rnd() * 250000);
    var comments = Math.floor(10 + rnd() * 4500);
    var hEl = document.querySelector('[data-ig-hearts]');
    var cEl = document.querySelector('[data-ig-comments]');
    if (hEl) hEl.textContent = formatCount(hearts);
    if (cEl) cEl.textContent = formatCount(comments);
  }

  function setAudioBehavior() {
    var playBtn = document.getElementById('audio-play');
    if (!playBtn) return;
    var audioEl = document.getElementById('audio-el');
    var statusEl = document.getElementById('audio-status');
    if (!audioEl) {
      playBtn.addEventListener('click', function () {
        if (statusEl) statusEl.textContent = 'Audio unavailable in demo';
      });
      return;
    }
    if (statusEl) statusEl.textContent = 'Ready';
    playBtn.addEventListener('click', function () {
      if (audioEl.paused) {
        audioEl.play();
        playBtn.textContent = 'Pause';
      } else {
        audioEl.pause();
        playBtn.textContent = 'Play';
      }
    });
    audioEl.addEventListener('ended', function () { playBtn.textContent = 'Play'; });
  }

  function flipReveal(payload) {
    if (!card) return;
    var pill = document.getElementById('reveal-pill');
    var pointsEl = document.getElementById('reveal-points');
    var expl = document.getElementById('reveal-expl-text');
    var cReal = document.getElementById('choice-real');
    var cAi = document.getElementById('choice-ai');

    var correct = !!payload.correct;
    if (pill) {
      pill.textContent = correct ? 'Correct' : 'Incorrect';
      pill.classList.toggle('ok', correct);
      pill.classList.toggle('bad', !correct);
    }
    if (pointsEl) pointsEl.textContent = payload.points ? ('+' + payload.points) : '';
    if (expl) expl.textContent = payload.explanation || '—';

    var ca = payload.correct_answer;
    if (cReal) cReal.classList.toggle('is-correct', ca === 'real');
    if (cAi) cAi.classList.toggle('is-correct', ca === 'ai');

    card.classList.add('is-flipped');

    var nextBtn = document.getElementById('next-btn');
    if (nextBtn) {
      nextBtn.onclick = function () {
        window.location.href = payload.next_url || '/quiz';
      };
    }
  }

  function submitAnswer(answer) {
    if (answered) return;
    answered = true;
    clearInterval(timerInterval);
    var elapsed = Date.now() - startTime;
    document.getElementById('answer-input').value = answer;
    document.getElementById('response-time-input').value = elapsed;
    // Prefer the JSON endpoint so we can show a "flip" reveal first.
    var form = document.getElementById('answer-form');
    var fd = new FormData(form);
    var answerUrl = (form && form.getAttribute('data-answer-url')) || '/quiz/answer_json';
    fetch(answerUrl, { method: 'POST', body: fd, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.redirect_url) {
          window.location.href = data.redirect_url;
          return;
        }
        flipReveal(data);
      })
      .catch(function () {
        // Fallback to original behavior
        form.submit();
      });
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

  setMockStats();
  setAudioBehavior();
})();
