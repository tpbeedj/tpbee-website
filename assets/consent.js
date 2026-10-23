// Google Analytics and the home page's Twitch live player only after the visitor says
// yes (UK PECR: their cookies need consent). Until then neither loads at all. The
// choice is kept in this browser; "Cookies" at the foot of each page changes it.
// Loaded in <head> without defer, so window.tpbeeConsent exists before script.js runs.
(function () {
  var GA_ID = 'G-3CTKX5TWD7';
  var KEY = 'tpbee-analytics';  // "yes" / "no"; nothing saved = not asked yet

  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { dataLayer.push(arguments); };

  function choice() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function remember(value) {
    try { localStorage.setItem(KEY, value); } catch (e) { /* private window: ask again next visit */ }
  }

  // For other scripts (script.js's Twitch player): run fn now if allowed, else on Allow.
  var onAllow = [];
  window.tpbeeConsent = {
    whenAllowed: function (fn) {
      if (choice() === 'yes') fn();
      else onAllow.push(fn);
    }
  };

  var loaded = false;
  function loadAnalytics() {
    if (loaded) return;
    loaded = true;
    gtag('js', new Date());
    gtag('config', GA_ID);
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
  }

  function clearAnalyticsCookies() {
    document.cookie.split(';').forEach(function (c) {
      var name = c.split('=')[0].trim();
      if (name.indexOf('_ga') !== 0) return;
      [location.hostname, '.' + location.hostname.replace(/^www\./, '')].forEach(function (domain) {
        document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=' + domain;
      });
      document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
    });
  }

  // Clicks between tpb.ee's own pages as a "link_click" event. Links off the site are
  // already counted by GA4's built-in "click" event (outbound clicks).
  document.addEventListener('click', function (e) {
    if (!loaded) return;
    var a = e.target.closest && e.target.closest('a[href]');
    if (a && a.hostname === location.hostname) gtag('event', 'link_click', {
      link_url: a.href,
      link_text: (a.getAttribute('aria-label') || a.textContent).trim().replace(/\s+/g, ' ').slice(0, 100)
    });
  });

  var banner = null;
  function showBanner() {
    if (banner) return;
    banner = document.createElement('div');
    banner.className = 'cookie-banner';
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-label', 'Cookies');
    // Says who sets what. The counts are the cookies seen in testing (2026-10-23):
    // Google _ga + _ga_3CTKX5TWD7; Twitch 6 on twitch.tv + 1 on twitchcdn.net.
    banner.innerHTML =
      '<p><strong>Can tpb.ee use cookies from these two?</strong> Nothing loads from either until you say yes.</p>' +
      '<ul>' +
      '<li><strong>Google Analytics</strong> - counts visits and which links get clicked, so I can see what ' +
      'gets played. 2 cookies, set by Google. ' +
      '<a href="https://policies.google.com/technologies/partner-sites" target="_blank" rel="noopener">How Google uses them</a></li>' +
      '<li><strong>Twitch</strong> - the live player on the home page, shown when I\'m streaming. ' +
      '7 cookies, set by Twitch. ' +
      '<a href="https://legal.twitch.com/legal/cookie-notice/" target="_blank" rel="noopener">How Twitch uses them</a></li>' +
      '</ul>' +
      '<p>Your answer is saved in this browser - change it any time with <em>Cookies</em> at the bottom of the page.</p>' +
      '<div class="cookie-banner-buttons">' +
      '<button type="button" data-choice="yes">Allow</button>' +
      '<button type="button" data-choice="no">No thanks</button>' +
      '</div>';
    banner.addEventListener('click', function (e) {
      var picked = e.target.getAttribute && e.target.getAttribute('data-choice');
      if (!picked) return;
      var before = choice();
      remember(picked);
      banner.remove();
      banner = null;
      if (picked === 'yes') {
        loadAnalytics();
        onAllow.splice(0).forEach(function (fn) { fn(); });
      } else if (before === 'yes' || loaded) {
        // Turned off after being on: drop GA's cookies and reload without GA or the
        // Twitch player (Twitch's own cookies are on twitch.tv - a page here can't remove them).
        clearAnalyticsCookies();
        location.reload();
      }
    });
    document.body.appendChild(banner);
  }

  function addSettingsLink() {
    var link = document.createElement('button');
    link.type = 'button';
    link.className = 'cookie-settings';
    link.textContent = 'Cookies';
    link.addEventListener('click', showBanner);
    var footer = document.getElementById('site-footer');
    if (footer) {
      footer.appendChild(link);
    } else {
      var line = document.createElement('p');
      line.className = 'cookie-settings-line';
      line.appendChild(link);
      (document.querySelector('main') || document.body).appendChild(line);
    }
  }

  if (choice() === 'yes') loadAnalytics();

  function start() {
    addSettingsLink();
    if (choice() === null) showBanner();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
