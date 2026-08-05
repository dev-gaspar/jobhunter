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


# La UI nueva de busqueda ya no expone el URN del post en el DOM (ni en hrefs
# ni en atributos); la unica fuente 1:1 es el item "Copiar enlace a la
# publicacion" del menu de tres puntos, que escribe un lnkd.in al portapapeles.
# Requiere lanzar el contexto con permissions=["clipboard-read", "clipboard-write"].
COPY_LINK_JS = r"""async (idx) => {
    const items = document.querySelectorAll('[role="listitem"]');
    const item = items[idx];
    if (!item) return null;
    item.scrollIntoView({block: 'center'});
    await new Promise(r => setTimeout(r, 500));
    const menuBtn = [...item.querySelectorAll('button')]
        .find(b => /controles|control menu|menú de control/i.test(b.getAttribute('aria-label') || ''));
    if (!menuBtn) return null;
    menuBtn.click();
    await new Promise(r => setTimeout(r, 700));
    let url = null;
    try {
        const opts = [...document.querySelectorAll('[role="menu"] *, .artdeco-dropdown__content *')]
            .filter(e => /Copiar enlace|Copy link/i.test(e.textContent || '') && e.children.length <= 2);
        const target = opts.find(e => e.closest('li') || e.tagName === 'BUTTON' || e.getAttribute('role') === 'menuitem') || opts[0];
        if (target) {
            target.click();
            await new Promise(r => setTimeout(r, 800));
            url = await navigator.clipboard.readText();
        }
    } catch (e) {}
    try { if (menuBtn.getAttribute('aria-expanded') === 'true') menuBtn.click(); } catch (e) {}
    return url;
}"""


def collect_post_urls(page, count):
    """Extrae la URL de cada post via el menu "Copiar enlace" (portapapeles).

    Retorna {indice_listitem: url}. Los fallos por item se ignoran (url ausente).
    """
    urls = {}
    for i in range(count):
        try:
            url = page.evaluate(COPY_LINK_JS, i)
        except Exception:
            continue
        if isinstance(url, str) and url.strip().startswith("http"):
            urls[i] = url.strip()
        try:
            page.wait_for_timeout(random.randint(200, 500))
        except Exception:
            pass
    return urls


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
        n_items = page.locator('[role="listitem"]').count()
        post_urls = collect_post_urls(page, n_items)
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

def extract_post_text(page):
    """Extrae el texto principal de una publicacion con selectores en cascada."""
    try:
        btn = page.query_selector("button.feed-shared-inline-show-more-text__see-more-less-toggle")
        if btn:
            btn.click()
            page.wait_for_timeout(500)
    except Exception:
        pass
    selectors = [
        'span[data-testid="expandable-text-box"]',
        "div.feed-shared-update-v2__description",
        "article",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = (el.inner_text() or "").strip()
                if len(text) >= 50:
                    return text
        except Exception:
            continue
    try:
        return (page.inner_text("main") or "").strip()[:6000]
    except Exception:
        return ""


def scrape_single_post(url):
    """Abre una publicacion individual con la sesion persistente y extrae su texto.

    Retorna el texto, o None si fallo (ya imprime la causa).
    """
    if not os.path.exists(SESSION_DIR):
        console.print("  [red]✗[/red] Sin sesion LinkedIn. Ejecuta: [cyan]jobhunter login[/cyan]")
        return None
    kill_playwright_zombies()
    try:
        with sync_playwright() as p:
            chrome = find_chrome()
            browser = p.chromium.launch_persistent_context(
                user_data_dir=SESSION_DIR, headless=True,
                viewport={"width": 1300, "height": 850}, executable_path=chrome,
            )
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            if "login" in page.url or "signin" in page.url or "authwall" in page.url:
                console.print("  [red]![/red] Sesion expirada. Ejecuta: [cyan]jobhunter login[/cyan]")
                browser.close()
                return None
            text = extract_post_text(page)
            browser.close()
            if not text:
                console.print("  [red]✗[/red] No se pudo extraer texto de la publicacion. Copia el texto y usa: [cyan]jobhunter apply[/cyan]")
                return None
            return text
    except Exception as e:
        console.print(f"  [red]✗[/red] No se pudo abrir la publicacion: {e}")
        return None
