import asyncio, random, time, yaml, requests, json
from pyppeteer import connect
import tkinter as tk
from tkinter import messagebox, scrolledtext
import sys

# --- nowa funkcja logująca po polsku ---
def log(tekst: str):
    print(f"[AKCJA] {tekst}")

# --- Funkcja opóźnienia (synchroniczna) ---
def random_delay_sync(min_s, max_s):
    delay = random.randint(min_s, max_s)
    log(f"Losuję opóźnienie między {min_s} a {max_s} sek. → czekam {delay} sek.")
    time.sleep(delay)

# --- Wczytywanie konfiguracji z YAML ---
def load_config(path="config.yaml"):
    log(f"Wczytuję dane konfiguracyjne z pliku {path}")
    with open(path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    log("Konfiguracja została poprawnie załadowana.")
    return config_data

config = load_config()

# --- Funkcja wczytująca listę profili z profile.json ---
def load_profiles(path="profile.json") -> list[int]:
    """Wczytuje ID profili z profile.json."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids = data.get("profile_ids", []) if isinstance(data, dict) else data
    log(f"Znaleziono {len(ids)} profil(y): {ids}")
    return ids

# --- Uruchomienie profilu przez API ---
def start_profile(pid: int):
    url = f"http://localhost:3001/v1.0/browser_profiles/{pid}/start?automation=1"
    log(f"Startuję profil AntyDolphin o ID {pid} → {url}")
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        log("Profil uruchomiony, czekam na gotowość przeglądarki…")
        random_delay_sync(
            config["profiles"]["launch_delay"]["min_seconds"],
            config["profiles"]["launch_delay"]["max_seconds"]
        )
        return data
    else:
        err = f"{resp.status_code} {resp.text}"
        log(f"BŁĄD podczas uruchamiania profilu {pid}: {err}")
        raise

# --- Funkcja zatrzymująca profil przez API ---
def stop_profile(pid: int):
    url = f"http://localhost:3001/v1.0/browser_profiles/{pid}/stop"
    log(f"Zatrzymuję profil {pid} → {url}")
    resp = requests.get(url)
    if resp.status_code == 200:
        log(f"Profil {pid} zatrzymany poprawnie.")
    else:
        log(f"BŁĄD przy zatrzymaniu profilu {pid}: {resp.status_code} {resp.text}")

# --- Funkcja klikająca przycisk "Lubię to!" ---
async def click_like(page):
    log("Czekam na przycisk ‘Lubię to!’…")
    try:
        el = await page.waitForSelector('span[data-ad-rendering-role="lubię to!_button"]', {'timeout':60000})
        if el:
            await safe_click(page, el)
            log("Kliknięto ‘Lubię to!’")
    except Exception as e:
        log(f"Nie udało się kliknąć ‘Lubię to!’: {e}")

# --- Funkcja bezpiecznego klikania ---
async def safe_click(page, element) -> bool:
    try:
        is_visible = await page.evaluate('(el) => el.offsetParent !== null', element)
        if not is_visible:
            log("Element nie jest widoczny, przewijam do elementu…")
            await page.evaluate('(el) => el.scrollIntoView({ behavior: "smooth", block: "center" })', element)
            await asyncio.sleep(2)

        is_enabled = await page.evaluate('(el) => !el.disabled', element)
        log(f"Element klikalny: {is_enabled}")

        log("Klikam element…")
        box = await element.boundingBox()
        if box:
            cx = box['x'] + box['width']/2
            cy = box['y'] + box['height']/2
            await click_perfect(page, cx, cy)
        else:
            await page.evaluate('(el) => el.click()', element)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        log(f"BŁĄD: safe_click nie powiodło się: {e}")
        return False

# --- Funkcje do „ludzkiego” ruchu myszką i klikania ---
def _cubic_bezier(p0, p1, p2, p3, t):
    return (
        (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0],
        (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1],
    )

# --- Funkcja inicjująca czerwoną kropkę na stronie ---
async def init_cursor_dot(page):
    await page.evaluate("""
      if (!document.getElementById('__automation_cursor_dot')) {
        const dot = document.createElement('div');
        dot.id = '__automation_cursor_dot';
        dot.style.position = 'fixed';
        dot.style.width = '8px';
        dot.style.height = '8px';
        dot.style.background = 'red';
        dot.style.borderRadius = '50%';
        dot.style.zIndex = '2147483647';
        dot.style.pointerEvents = 'none';
        dot.style.transform = 'translate(-50%, -50%)';
        document.body.appendChild(dot);
      }
    """)

async def human_like_mouse_move(page, dest_x, dest_y,
                                steps_min=20, steps_max=40,
                                jitter=10,
                                speed_variation=(0.002, 0.02)):
    box = await page.evaluate("() => ({ x: window._lastMouseX||0, y: window._lastMouseY||0 })")
    start = (box['x'], box['y'])
    end = (dest_x, dest_y)
    cp1 = ( start[0] + random.uniform(-jitter, jitter),
            start[1] + random.uniform(-jitter, jitter) )
    cp2 = ( end[0] + random.uniform(-jitter, jitter),
            end[1] + random.uniform(-jitter, jitter) )
    steps = random.randint(steps_min, steps_max)
    for i in range(1, steps+1):
        t = i/steps
        x, y = _cubic_bezier(start, cp1, cp2, end, t)
        await page.mouse.move(x, y)
        await page.evaluate(
          "(x,y)=>{const d=document.getElementById('__automation_cursor_dot'); if(d){d.style.left=x+'px';d.style.top=y+'px';}}",
          x, y
        )
        await asyncio.sleep(random.uniform(*speed_variation))
    await page.evaluate(f"window._lastMouseX={dest_x};window._lastMouseY={dest_y};")

async def click_perfect(page, x, y):
    await human_like_mouse_move(page, x, y)
    await asyncio.sleep(random.uniform(0.05, 0.15))
    await page.mouse.click(x, y, {'delay': random.uniform(10,40)})

async def human_click(page, selector, wait_opts=None):
    """
    Czeka na selector, wylicza boundingBox i klika po środku
    za pomocą click_perfect.
    """
    if wait_opts is None:
        wait_opts = {'timeout': 30000}
    handle = await page.waitForSelector(selector, wait_opts)
    box = await handle.boundingBox()
    cx = box['x'] + box['width']/2
    cy = box['y'] + box['height']/2
    await click_perfect(page, cx, cy)
    await asyncio.sleep(0.2)
    return True

async def add_friend(page) -> bool:
    xpaths = [
        '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[1]/div/div[2]/div[1]/div[2]/div/div[2]/div/a/div[1]/div[2]/div/div[2]/div/div/div[1]/div[1]',
        '/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[2]/div[1]/div/div/div[1]/div[2]/div/div/div/div[4]/div/div/div[1]/div/div/div/div[1]/div[2]/span/span'
    ]
    try:
        for xpath in xpaths:
            log(f"Szukam przycisku ‘Dodaj znajomego’ po XPath: {xpath}")
            try:
                button_handle = await page.waitForXPath(xpath, {'timeout': 5000})
                if button_handle:
                    log("Przycisk ‘Dodaj znajomego’ znaleziony. Klikam…")
                    await safe_click(page, button_handle)
                    log("Kliknięto przycisk ‘Dodaj znajomego’.")
                    await asyncio.sleep(3)
                    await page.screenshot({'path': f'add-friend-{int(time.time())}.png'})
                    return True
            except Exception:
                log(f"Nie znaleziono przycisku po XPath: {xpath}")
        log("Nie znaleziono żadnego przycisku ‘Dodaj znajomego’.")
        await page.screenshot({'path': f'add-friend-fail-{int(time.time())}.png'})
        return False
    except Exception as e:
        log(f"BŁĄD przy dodawaniu znajomego: {e}")
        await page.screenshot({'path': f'add-friend-error-{int(time.time())}.png'})
        return False

# --- Funkcja odwiedzająca profil i próbująca dodać znajomego ---
async def visit_profile_and_add_friend(page, profile_url):
    log(f"Odwiedzam profil: {profile_url}")
    await page.goto(profile_url)
    load_wait = random.randint(3, 6)
    log(f"Czekam {load_wait} sekund na załadowanie profilu.")
    await asyncio.sleep(load_wait)
    if await add_friend(page):
        log(f"Dodanie znajomego zakończone na profilu: {profile_url}")
    else:
        log(f"Nie udało się dodać znajomego na profilu: {profile_url}")

# --- Funkcja symulująca przeglądanie profili i dodawanie znajomych ---
async def simulate_browse_profiles_and_add_friends(page):
    log("Przechodzę do sugestii znajomych i dodaję jednego znajomego…")
    await page.goto(
        "https://www.facebook.com/friends/suggestions",
        {'timeout': 90000, 'waitUntil': 'networkidle2'}
    )
    await asyncio.sleep(5)

    if await add_friend(page):
        log("Pomyślnie dodano jednego znajomego ze sugestii.")
        delay = random.randint(10, 20)
        log(f"Oczekuję {delay} sekund po dodaniu znajomego.")
        await asyncio.sleep(delay)
    else:
        log("Nie udało się dodać znajomego ze sugestii.")

# --- Inne symulacje na Facebooku ---
async def simulate_share_post(page):
    log("Rozpoczynam symulację udostępniania postu na Facebooku…")
    await asyncio.sleep(2)
    log("Udostępnianie postu zakończone.")

async def simulate_click_interested(page):
    log("Rozpoczynam symulację klikania ‘Zainteresowany’ przy wydarzeniu…")
    await asyncio.sleep(2)
    log("Kliknięcie ‘Zainteresowany’ zakończone.")

async def simulate_browse_homepage(page):
    log("Rozpoczynam symulację przeglądania strony głównej Facebooka…")
    await page.goto("https://www.facebook.com", {'timeout': 90000, 'waitUntil': 'networkidle2'})
    duration = random.randint(
        config["facebook"]["actions"]["browse_homepage"]["duration"]["min_seconds"],
        config["facebook"]["actions"]["browse_homepage"]["duration"]["max_seconds"]
    )
    log(f"Ustalony czas przeglądania strony głównej: {duration} sekund.")
    start = time.time()
    profile_list = [
        "https://www.facebook.com/profile.php?id=61558009544686"
    ]
    while (time.time() - start) < duration:
        try:
            log("Próbuję kliknąć specjalny przycisk na stronie głównej…")
            special_button = await page.waitForXPath('/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[2]/div[1]/div/div[2]/div/div/div/div[2]/div/div[4]/div/div[2]/div[1]/div/div/div/div/div/div/div/div/div/div/div/div/div/div[13]/div/div/div[4]/div/div/div/div/div[2]/div/div[4]/div', {'timeout': 3000})
            if special_button:
                await safe_click(page, special_button)
                log("Kliknięto specjalny przycisk na stronie głównej.")
                await asyncio.sleep(2)
            else:
                log("Nie znaleziono specjalnego przycisku na stronie głównej.")
        except Exception as e:
            log(f"Błąd podczas klikania specjalnego przycisku na stronie głównej: {e}")

        decision = random.random()
        log(f"Losowa decyzja: {decision:.2f}")
        if decision < 0.3:
            profile_url = random.choice(profile_list)
            log(f"Decyzja: odwiedź profil {profile_url} i dodaj znajomego.")
            await visit_profile_and_add_friend(page, profile_url)
            log("Powrót na stronę główną Facebooka.")
            await page.goto("https://www.facebook.com")
        elif decision < 0.6:
            await page.evaluate("window.scrollBy(0, 250);")
            log("Przewinięto stronę o 250 pikseli.")
            log("Próba kliknięcia ‘Lubię to!’…")
            await click_like(page)
        else:
            await page.evaluate("window.scrollBy(0, 250);")
            log("Tylko scroll – przewinięto stronę o 250 pikseli.")
        scroll_sleep = random.randint(
            config["facebook"]["actions"]["browse_homepage"]["scroll_interval"]["min_seconds"],
            config["facebook"]["actions"]["browse_homepage"]["scroll_interval"]["max_seconds"]
        )
        log(f"Oczekiwanie {scroll_sleep} sekund przed kolejną akcją.")
        await asyncio.sleep(scroll_sleep)
    log("Zakończono przeglądanie strony głównej Facebooka.")

async def simulate_facebook_actions(page):
    if config["facebook"]["pre_login"]:
        log("Symuluję wpisywanie ‘facebook’ w wyszukiwarce Google…")
        await page.goto("https://www.google.com")
        try:
            consent = await page.querySelector('button[aria-label="Zaakceptuj wszystko"]')
            if consent:
                log("Akceptuję cookies Google…")
                await consent.click()
                await asyncio.sleep(1)
            await human_click(page, 'textarea[name="q"]')
            await page.keyboard.type('facebook', {'delay':100})
            log("Wpisano frazę: ‘facebook’")
            await asyncio.sleep(0.2)
            await page.keyboard.press('Enter')
            log("Wciśnięto Enter. Czekam na wyniki wyszukiwania…")
            await asyncio.sleep(3)
        except Exception as e:
            log(f"BŁĄD przy wpisywaniu treści w wyszukiwarce: {e}")

    log("Przechodzę do strony Facebooka…")
    await page.goto("https://www.facebook.com")
    wait_time = random.randint(3, 5)
    log(f"Czekam {wait_time} sekund po załadowaniu Facebooka.")
    await asyncio.sleep(wait_time)

    fb_email = config["facebook"]["credentials"]["email"]
    fb_password = config["facebook"]["credentials"]["password"]
    try:
        log("Wprowadzam dane logowania (email, hasło).")
        await page.type("#email", fb_email)
        await page.type("#pass", fb_password)
        await human_click(page, "button[name='login']")
        log("Kliknięto przycisk logowania.")
    except Exception as e:
        log(f"BŁĄD podczas logowania: {e}")

    login_wait = random.randint(5, 8)
    log(f"Czekam {login_wait} sekund po logowaniu.")
    await asyncio.sleep(login_wait)
    log("Zalogowano na Facebooku!")

    await like_fanpage(page, "https://www.facebook.com/profile.php?id=61572203260750")
    await simulate_browse_homepage(page)
    await simulate_browse_profiles_and_add_friends(page)

# --- Funkcja przewijania onet.pl przed przejściem do Facebooka ---
async def browse_onet_before_facebook(page, duration_seconds=60):
    log(f"Wchodzę na onet.pl i przewijam stronę przez {duration_seconds} sekund…")
    await page.goto("https://www.onet.pl", {'timeout': 60000, 'waitUntil': 'networkidle2'})
    start = time.time()
    scroll_step = 300
    while (time.time() - start) < duration_seconds:
        await page.evaluate(f"window.scrollBy(0, {scroll_step});")
        await asyncio.sleep(2)
    log("Zakończono przewijanie onet.pl, przechodzę do Facebooka.")

# --- Funkcja polubienia fanpage ---
async def like_fanpage(page, fanpage_url):
    log(f"Wchodzę na fanpage: {fanpage_url}")
    await page.goto(fanpage_url, {'timeout': 60000, 'waitUntil': 'networkidle2'})
    await asyncio.sleep(5)

    try:
        log("Szukam przycisku ‘Polub’…")
        like_button = await page.waitForXPath('/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div/div/div[1]/div[2]/div/div/div/div[4]/div/div/div[2]/div/div/div/div[1]/div[2]/span/span', {'timeout': 10000})
        if like_button:
            await safe_click(page, like_button)
            log("Kliknięto przycisk ‘Polub’.")
            await asyncio.sleep(3)
            await page.screenshot({'path': f'fanpage-like-{int(time.time())}.png'})

            log("Szukam kolejnego przycisku po polubieniu…")
            next_button = await page.waitForXPath('/html/body/div[1]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div/div[1]/div[3]/div[12]/div[2]/div', {'timeout': 10000})
            if next_button:
                await safe_click(page, next_button)
                log("Kliknięto kolejny przycisk po polubieniu.")
                await asyncio.sleep(2)
                await page.screenshot({'path': f'fanpage-next-{int(time.time())}.png'})
            else:
                log("Nie znaleziono kolejnego przycisku po polubieniu.")
        else:
            log("Nie znaleziono przycisku ‘Polub’.")
    except Exception as e:
        log(f"BŁĄD: Nie udało się kliknąć ‘Polub’ lub kolejnego przycisku: {e}")

# --- Funkcja symulująca wpisywanie tekstu ---
async def simulate_typing(page, selector, text):
    """
    Symuluje wpisywanie tekstu do pola wskazanego selektorem (z uwzględnieniem
    losowych opóźnień i prób zamykania ewentualnych popupów o cookies).
    """
    print(f"[LOG] Szukam pola do wpisania: {selector}")
    await page.waitForSelector(selector, visible=True)

    # Spróbuj zamknąć popupy cookies/zgody
    try:
        print("[LOG] Sprawdzam popupy cookies/zgody...")
        agree_btn = await page.Jx('//button[contains(., "Zgadzam się") or '
                                  'contains(., "Akceptuję") or contains(., "Accept all")]')
        if agree_btn:
            print("[LOG] Klikam przycisk zgody/cookies.")
            await agree_btn[0].click()
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[LOG] Brak popupów cookies/zgody lub błąd: {e}")

    # Kliknij pole kilka razy jeśli trzeba
    for attempt in range(3):
        try:
            print(f"[LOG] Próbuję kliknąć pole wyszukiwania (próba {attempt+1})")
            await human_click(page, selector)
            await asyncio.sleep(0.5)
            break
        except Exception as e:
            print(f"[LOG] Nie udało się kliknąć pola: {e}")
            await asyncio.sleep(1)

    # Wpisywanie tekstu (z usuwaniem poprzedniej zawartości)
    print(f"[LOG] Wpisuję tekst: {text}")
    await page.focus(selector)
    await page.keyboard.down("Control")
    await page.keyboard.press("A")
    await page.keyboard.up("Control")
    await page.keyboard.press("Backspace")
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.07, 0.18))

    await asyncio.sleep(random.uniform(0.5, 1.2))
    await page.keyboard.press("Enter")
    print(f"[LOG] Wpisano '{text}' i zatwierdzono Enterem.")

# --- Funkcja do przekierowania logów do GUI ---
class TextRedirector(object):
    def __init__(self, widget):
        self.widget = widget
    def write(self, str):
        self.widget.configure(state='normal')
        self.widget.insert(tk.END, str)
        self.widget.see(tk.END)
        self.widget.configure(state='disabled')
    def flush(self):
        pass

def start_gui():
    def on_start():
        profile_url = entry.get()
        if not profile_url.startswith("http"):
            messagebox.showerror("Błąd", "Wpisz poprawny link do profilu Facebook!")
            return
        start_btn.config(state="disabled")
        root.after(100, lambda: asyncio.get_event_loop().run_until_complete(main()))

    def on_entry_focus_in(event):
        entry.configure(bg="#23272f", fg="#00bfff")

    def on_entry_focus_out(event):
        entry.configure(bg="#2c313c", fg="#ffffff")

    def on_enter(e):
        start_btn['bg'] = "#0099cc"
        start_btn['fg'] = "#ffffff"

    def on_leave(e):
        start_btn['bg'] = "#00bfff"
        start_btn['fg'] = "#23272f"

    root = tk.Tk()
    root.title("Facebook Friend Adder")
    root.geometry("600x440")
    root.configure(bg="#23272f")
    root.resizable(False, False)

    header = tk.Label(
        root, text="Facebook Friend Adder",
        font=("Segoe UI", 20, "bold"),
        bg="#23272f", fg="#00bfff"
    )
    header.pack(pady=(18, 2))

    subtitle = tk.Label(
        root,
        text="Podaj link do profilu Facebook, który chcesz dodać do znajomych:",
        font=("Segoe UI", 11),
        bg="#23272f", fg="#e0e0e0"
    )
    subtitle.pack(pady=(0, 14))

    entry = tk.Entry(
        root, width=48, font=("Segoe UI", 12),
        bg="#2c313c", fg="#ffffff",
        insertbackground="#00bfff",
        borderwidth=0, relief="flat", highlightthickness=2, highlightbackground="#00bfff", highlightcolor="#00bfff"
    )
    entry.pack(pady=(0, 18), ipady=6)
    entry.bind("<FocusIn>", on_entry_focus_in)
    entry.bind("<FocusOut>", on_entry_focus_out)

    style = {
        "font": ("Segoe UI", 13, "bold"),
        "bg": "#00bfff",
        "fg": "#23272f",
        "activebackground": "#0099cc",
        "activeforeground": "#ffffff",
        "bd": 0,
        "cursor": "hand2",
        "relief": "flat"
    }
    start_btn = tk.Button(root, text="START", command=on_start, **style)
    start_btn.pack(ipadx=36, ipady=10, pady=(0, 14))
    start_btn.bind("<Enter>", on_enter)
    start_btn.bind("<Leave>", on_leave)

    log_frame = tk.Frame(root, bg="#181a20", highlightbackground="#00bfff", highlightthickness=2)
    log_frame.pack(padx=18, pady=(0, 10), fill="both", expand=True)
    log_box = scrolledtext.ScrolledText(
        log_frame, width=70, height=10,
        font=("Consolas", 10),
        bg="#181a20", fg="#00ff99",
        state='disabled', borderwidth=0, relief="flat"
    )
    log_box.pack(fill="both", expand=True, padx=2, pady=2)

    footer = tk.Label(
        root, text="by EchoStudio Duke",
        font=("Segoe UI", 9),
        bg="#23272f", fg="#e0e0e0"
    )
    footer.pack(side="bottom", pady=(0, 8))

    sys.stdout = TextRedirector(log_box)
    sys.stderr = TextRedirector(log_box)

    root.mainloop()

# --- Pojedyncze uruchomienie profilu ---
async def run_profile(pid: int, session_duration: int = 30*60):
    """Uruchamia jedną sesję FB przez session_duration sekund."""
    prof = start_profile(pid)
    port = prof["automation"]["port"]
    ws   = prof["automation"]["wsEndpoint"]
    ws_url = f"ws://127.0.0.1:{port}{ws}"
    log(f"[{pid}] łączę się pod {ws_url}")
    browser = await connect(browserWSEndpoint=ws_url)
    page = await browser.newPage()
    await init_cursor_dot(page)

    try:
        log(f"[{pid}] startuję akcje Facebook…")
        await simulate_facebook_actions(page)
        log(f"[{pid}] sesja potrwa {session_duration//60} minut")
        await asyncio.sleep(session_duration)
    finally:
        await browser.disconnect()
        stop_profile(pid)
        log(f"[{pid}] zakończono sesję i zatrzymano profil.")

# --- Nowy main(): uruchamia partie po 15, z 10-min przerwą, w pętli ---
async def main():
    profile_ids     = load_profiles()      # z profile.json
    batch_size      = 15
    session_duration= 30 * 60              # 30 minut
    cooldown        = 10 * 60              # 10 minut
    idx = 0

    while True:
        batch = profile_ids[idx: idx + batch_size] or profile_ids[:batch_size]
        log(f"Startuję turę {len(batch)} profili: {batch}")
        tasks = [asyncio.create_task(run_profile(pid, session_duration)) for pid in batch]
        await asyncio.gather(*tasks)

        log(f"Tura zakończona. Przerwa {cooldown//60} minut…")
        await asyncio.sleep(cooldown)

        idx = (idx + batch_size) % len(profile_ids)

# jeśli wywoływane bez GUI
if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
