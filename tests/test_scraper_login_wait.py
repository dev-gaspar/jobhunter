# -*- coding: utf-8 -*-
"""Tests de la espera de login en LinkedIn (regresion del bug de page.url obsoleto).

CONTEXTO DEL BUG: en la API sync de Playwright, page.url es un valor CACHEADO que
solo se refresca cuando el bucle de eventos del driver se bombea. time.sleep()
bloquea el hilo sin bombearlo, asi que la navegacion que hace el USUARIO al
iniciar sesion nunca llegaba al lado de Python: el login funcionaba pero se
reportaba como fallido tras 5 minutos.

Los fakes de abajo reproducen esa semantica: FakePage.url NO avanza solo; solo
avanza cuando se llama a wait_for_timeout() (que es lo que bombea el loop). Un
bucle implementado con time.sleep() NO puede pasar estos tests.
"""
import unittest

from jobhunter.scraper import linkedin_session_ready, wait_for_linkedin_session

LI_COOKIE = {"name": "li_at", "value": "AQEDAT...", "domain": ".www.linkedin.com"}
OTHER_COOKIE = {"name": "bcookie", "value": "v=2", "domain": ".linkedin.com"}


class FakeBrowser:
    """Contexto falso: expone cookies() y cuenta los bombeos del loop."""

    def __init__(self, cookie_after_pumps=None, raise_on_cookies=False):
        self.pumps = 0
        self._cookie_after = cookie_after_pumps
        self._raise = raise_on_cookies

    def cookies(self):
        if self._raise:
            raise RuntimeError("contexto cerrado")
        if self._cookie_after is not None and self.pumps >= self._cookie_after:
            return [OTHER_COOKIE, LI_COOKIE]
        return [OTHER_COOKIE]


class FakePage:
    """Pagina falsa con la semantica REAL de Playwright sync.

    `url` devuelve un valor cacheado. Solo wait_for_timeout() (que bombea el
    bucle de eventos) hace avanzar ese cache a la siguiente URL real.
    """

    def __init__(self, browser, urls, raise_on_wait=False):
        self.browser = browser
        self._urls = list(urls)
        self._i = 0
        self._raise_on_wait = raise_on_wait
        self.waits = []

    @property
    def url(self):
        return self._urls[self._i]

    def wait_for_timeout(self, ms):
        if self._raise_on_wait:
            raise RuntimeError("Target page, context or browser has been closed")
        self.waits.append(ms)
        self.browser.pumps += 1
        self._i = min(self._i + 1, len(self._urls) - 1)


class WaitForLinkedinSessionTests(unittest.TestCase):
    def test_detects_login_by_cookie(self):
        """La cookie li_at es la senal autoritativa: aparece tras 2 bombeos."""
        browser = FakeBrowser(cookie_after_pumps=2)
        page = FakePage(browser, ["https://www.linkedin.com/login"])
        self.assertTrue(wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=1))

    def test_detects_login_by_url_when_cookie_missing(self):
        """Sin cookie visible, la URL del feed tambien vale (fallback)."""
        browser = FakeBrowser(cookie_after_pumps=None)
        page = FakePage(browser, [
            "https://www.linkedin.com/login",
            "https://www.linkedin.com/checkpoint/challenge",
            "https://www.linkedin.com/feed/",
        ])
        self.assertTrue(wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=1))

    def test_pumps_the_event_loop(self):
        """REGRESION: debe usarse page.wait_for_timeout, no time.sleep.

        Si el bucle usara time.sleep, no habria bombeos y la URL jamas avanzaria.
        """
        browser = FakeBrowser(cookie_after_pumps=None)
        page = FakePage(browser, [
            "https://www.linkedin.com/login",
            "https://www.linkedin.com/feed/",
        ])
        wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=7)
        self.assertGreater(len(page.waits), 0, "no se bombeo el bucle de eventos")
        self.assertEqual(page.waits[0], 7)

    def test_returns_false_on_timeout(self):
        browser = FakeBrowser(cookie_after_pumps=None)
        page = FakePage(browser, ["https://www.linkedin.com/login"])
        self.assertFalse(wait_for_linkedin_session(browser, page, timeout_s=0.05, poll_ms=1))

    def test_page_closed_still_checks_cookies(self):
        """Si el usuario cierra la pestana pero la sesion existe, es exito."""
        browser = FakeBrowser(cookie_after_pumps=0)  # cookie ya presente
        page = FakePage(browser, ["about:blank"], raise_on_wait=True)
        self.assertTrue(wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=1))

    def test_page_closed_without_session_is_failure(self):
        browser = FakeBrowser(cookie_after_pumps=None)
        page = FakePage(browser, ["about:blank"], raise_on_wait=True)
        self.assertFalse(wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=1))

    def test_detects_session_saved_in_another_tab(self):
        """La cookie no depende de la pestana: login en otra ventana igual cuenta."""
        browser = FakeBrowser(cookie_after_pumps=1)
        page = FakePage(browser, ["https://www.linkedin.com/login"])  # esta pestana nunca cambia
        self.assertTrue(wait_for_linkedin_session(browser, page, timeout_s=5, poll_ms=1))


class LinkedinSessionReadyTests(unittest.TestCase):
    def test_true_with_cookie(self):
        self.assertTrue(linkedin_session_ready(FakeBrowser(cookie_after_pumps=0), None))

    def test_false_without_cookie_or_url(self):
        browser = FakeBrowser(cookie_after_pumps=None)
        page = FakePage(browser, ["https://www.linkedin.com/login"])
        self.assertFalse(linkedin_session_ready(browser, page))

    def test_ignores_empty_cookie_value(self):
        class Empty(FakeBrowser):
            def cookies(self):
                return [{"name": "li_at", "value": "", "domain": ".www.linkedin.com"}]
        self.assertFalse(linkedin_session_ready(Empty(), None))

    def test_survives_cookies_error(self):
        browser = FakeBrowser(raise_on_cookies=True)
        page = FakePage(browser, ["https://www.linkedin.com/feed/"])
        self.assertTrue(linkedin_session_ready(browser, page))


if __name__ == "__main__":
    unittest.main()
