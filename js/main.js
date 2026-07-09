// main.js — 入口、渲染循环
(function () {
  'use strict';
  const HF = (window.HF = window.HF || {});

  function init() {
    HF.ui.init();
    requestAnimationFrame(loop);
  }

  function loop() {
    HF.renderer.draw();
    requestAnimationFrame(loop);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
