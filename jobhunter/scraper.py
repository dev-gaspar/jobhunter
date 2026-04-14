# -*- coding: utf-8 -*-
"""Scraping de LinkedIn via Playwright y login persistente."""
import os
import random
import time
import urllib.parse

from playwright.sync_api import sync_playwright

from jobhunter.browser import find_chrome, kill_playwright_zombies
from jobhunter.constants import SESSION_DIR, TIME_FILTERS
from jobhunter.ui import console


def scrape_posts(page, query, max_scroll=4, time_filter="24h"):
    """Busca en LinkedIn por contenido, scrollea y extrae posts con emails."""
    encoded = urllib.parse.quote(query)
    date_param = TIME_FILTERS.get(time_filter, "past-24h")
    try:
        page.goto(
            f"https://www.linkedin.com/search/results/content/?keywords={encoded}"
            f"&datePosted=%5B%22{date_param}%22%5D&sortBy=%5B%22date_posted%22%5D",
            wait_until="domcontentloaded", timeout=60000,
        )
    except Exception:
        return []

    page.wait_for_timeout(random.randint(4000, 6000))
    for _ in range(max_scroll):
        page.evaluate(f"window.scrollBy(0, {random.randint(500, 1100)})")
        page.wait_for_timeout(random.randint(1500, 3500))

    page.evaluate("""() => {
        document.querySelectorAll('button[data-testid="expandable-text-button"]').forEach(b => { try{b.click()}catch(e){} });
    }""")
    page.wait_for_timeout(random.randint(1500, 3000))

    post_urls = {}
    try:
        listitems = page.locator('[role="listitem"]')
        for i in range(listitems.count()):
            try:
                menu_btn = listitems.nth(i).locator('button[aria-label*="controles"]').first
                if not menu_btn.is_visible(timeout=500):
                    continue
                menu_btn.click()
                page.wait_for_timeout(random.randint(400, 900))
                activity_id = page.evaluate(r"""() => {
                    const links = document.querySelectorAll('a[href*="entityUrn"]');
                    for (const l of links) {
                        const m = (l.getAttribute('href') || '').match(/activity%3A(\d+)/);
                        if (m) return m[1];
                    }
                    return null;
                }""")
                if activity_id:
                    post_urls[i] = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}"
                page.keyboard.press("Escape")
                page.wait_for_timeout(random.randint(200, 500))
            except Exception:
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
    except Exception:
        pass

    posts = page.evaluate(r"""() => {
        const boxes = document.querySelectorAll('span[data-testid="expandable-text-box"]');
        const posts = []; const seen = new Set();
        boxes.forEach((box, idx) => {
            const text = box.innerText || '';
            if (text.length < 50) return;
            const key = text.substring(0, 100);
            if (seen.has(key)) return;
            seen.add(key);
            const emails = [...new Set((text.match(/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g) || []))];
            posts.push({text: text.substring(0, 4000), emails_found: emails, index: idx});
        });
        return posts;
    }""")

    for post in posts:
        post["post_url"] = post_urls.get(post["index"])

    return posts


def do_linkedin_login():
    """Flujo compartido de login en LinkedIn. Retorna True si la sesion quedo guardada.

    Abre Chrome persistente con Playwright, espera a /feed o /in (max 5min),
    soporta 2FA. Cierra el navegador explicitamente para grabar cookies.
    """
    kill_playwright_zombies()
    os.makedirs(SESSION_DIR, exist_ok=True)
    chrome = find_chrome()
    console.print("  1. Se abrira Chrome")
    console.print("  2. Inicia sesion con [bold]correo y contrasena[/bold]")
    console.print("     [red]NO uses el boton de Google[/red] (bloqueado en automatizado)")
    console.print("  3. Si pide [bold]verificacion en dos pasos[/bold], completala en tu celular/email")
    console.print("  4. NO cierres el navegador. Se cerrara [bold]automaticamente[/bold] cuando la sesion este lista")
    input("\n  Presiona Enter para abrir el navegador...")

    success = False
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR, headless=False,
            viewport={"width": 1300, "height": 850}, executable_path=chrome,
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            page.goto("https://www.linkedin.com/login")
        except Exception:
            pass
        console.print("  [dim]Esperando que completes el login y el 2FA (hasta 5 minutos)...[/dim]")

        start = time.time()
        while time.time() - start < 300:
            try:
                url = page.url
                if "/feed" in url or "/in/" in url or "linkedin.com/home" in url:
                    time.sleep(3)
                    success = True
                    break
                time.sleep(2)
            except Exception:
                break

        try:
            browser.close()
        except Exception:
            pass

    if success:
        console.print("  [green]>[/green] Sesion de LinkedIn guardada correctamente")
    else:
        console.print("  [yellow]![/yellow] No se detecto el login completo. Si completaste el 2FA pero no llegaste al feed, vuelve a ejecutar [cyan]jobhunter login[/cyan]")
    return success


# Alias retrocompatible con el nombre interno original
_do_linkedin_login = do_linkedin_login
