from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from time import sleep, time
from datetime import datetime, date
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import os
import pytz 
import json # Necessário para ler o JSON da variável de ambiente

# =============================================================
# 🔥 CONFIGURAÇÃO FIREBASE (CORRIGIDA PARA VARIÁVEL DE AMBIENTE)
# =============================================================
DATABASE_URL = os.getenv("DATABASE_URL")
credJson = os.getenv("SERVICE_ACCOUNT_KEY") # Chave JSON como string

# 🛑 LINHAS DE DEBUG PARA IDENTIFICAR FALHA NA VARIÁVEL DE AMBIENTE 🛑
print("DB_URL:", DATABASE_URL)
print("KEY EXISTS:", credJson is not None)
print("KEY SIZE:", len(str(credJson)) if credJson else 0)
# ------------------------------------------------------------------

try:
    if credJson is None or not credJson.strip():
        raise ValueError("SERVICE_ACCOUNT_KEY está vazia ou não configurada no ambiente.")
        
    # Tenta carregar o JSON da variável de ambiente SERVICE_ACCOUNT_KEY
    cred = credentials.Certificate(json.loads(credJson))
    
    # O RESTO DO SEU CÓDIGO DO FIREBASE...
    firebase_admin.initialize_app(cred, {
        "databaseURL": DATABASE_URL
    })
    print("✅ Firebase Admin SDK inicializado com sucesso.")
except Exception as e:
    # O bot não vai parar, mas o erro de Firebase será impresso.
    print(f"\n❌ ERRO CRÍTICO DE CONEXÃO FIREBASE: {e}")
    print("⚠️ Por causa da falha no Firebase, os multiplicadores NÃO SERÃO SALVOS no banco de dados.")

# =============================================================
# ⚙️ VARIÁVEIS PRINCIPAIS
# =============================================================
URL_DO_SITE = "https://www.goathbet.com"
LINK_AVIATOR = "https://www.goathbet.com/game/spribe-aviator"
COOKIES_FILE = "cookies.pkl" 

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

POLLING_INTERVAL = 1.0          # Intervalo entre as checagens (1 segundo)
INTERVALO_MINIMO_ENVIO = 2.0    # Mínimo de tempo entre dois envios (segundos)
TEMPO_MAX_INATIVIDADE = 360     # 6 minutos (360 segundos)
TZ_BR = pytz.timezone("America/Sao_Paulo")

# =============================================================
# 🔧 FUNÇÕES AUXILIARES
# =============================================================
def getColorClass(value):
    m = float(value)
    if 1.0 <= m < 2.0:
        return "blue-bg"
    if 2.0 <= m < 10.0:
        return "purple-bg"
    if m >= 10.0:
        return "magenta-bg"
    return "default-bg"

def safe_click(driver, by, value, timeout=5):
    try:
        el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
        el.click()
        return True
    except Exception:
        return False

def safe_find(driver, by, value, timeout=5):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except Exception:
        return None


def initialize_game_elements(driver):
    """Localiza iframe e histórico do Aviator (Sua lista robusta mantida)."""
    POSSIVEIS_IFRAMES = [
        '//iframe[contains(@src, "/aviator/")]',
        '//iframe[contains(@src, "spribe")]',
        '//iframe[contains(@src, "aviator-game")]'
    ]
    
    POSSIVEIS_HISTORICOS = [
        ('.rounds-history', By.CSS_SELECTOR),
        ('.history-list', By.CSS_SELECTOR),
        ('.multipliers-history', By.CSS_SELECTOR),
        ('.result-history', By.CSS_SELECTOR),
        ('[data-testid="history"]', By.CSS_SELECTOR),
        ('.game-history', By.CSS_SELECTOR),
        ('.bet-history', By.CSS_SELECTOR),
        ('div[class*="recent-list"]', By.CSS_SELECTOR),
        ('ul.results-list', By.CSS_SELECTOR),
        ('div.history-block', By.CSS_SELECTOR),
        ('div[class*="history-container"]', By.CSS_SELECTOR),
        ('//div[contains(@class, "history")]', By.XPATH),
        ('//div[contains(@class, "rounds-list")]', By.XPATH)
    ]

    iframe = None
    for xpath in POSSIVEIS_IFRAMES:
        try:
            driver.switch_to.default_content() 
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            driver.switch_to.frame(iframe)
            print(f"✅ Iframe encontrado com XPath: {xpath}")
            break
        except Exception:
            continue

    if not iframe:
        print("⚠️ Nenhum iframe encontrado. Verifique se o jogo está carregado.")
        return None, None 

    historico_elemento = None
    for selector, by_method in POSSIVEIS_HISTORICOS:
        try:
            historico_elemento = WebDriverWait(driver, 7).until(
                EC.presence_of_element_located((by_method, selector))
            )
            print(f"✅ Seletor de histórico encontrado: {selector} ({by_method})")
            break
        except Exception:
            continue

    if not historico_elemento:
        print("⚠️ Nenhum seletor de histórico encontrado!")
        driver.switch_to.default_content()
        return None, None 

    return iframe, historico_elemento 

def process_login(driver):
    """Executa o fluxo de login e navegação para o Aviator."""
    if not EMAIL or not PASSWORD:
        print("❌ ERRO: EMAIL ou PASSWORD não configurados.")
        return False

    print("➡️ Executando login automático...")

    driver.get(URL_DO_SITE)
    sleep(2)

    if safe_click(driver, By.CSS_SELECTOR, 'button[data-age-action="yes"]', 5):
        print("✅ Confirmado maior de 18.")
        sleep(1)

    if not safe_click(driver, By.CSS_SELECTOR, 'a[data-ix="window-login"].btn-small.w-button', 5):
        print("❌ Botão 'Login' inicial não encontrado.")
        return False
    sleep(1)

    email_input = safe_find(driver, By.ID, "field-15", 5)
    pass_input = safe_find(driver, By.ID, "password-login", 5)

    if email_input and pass_input:
        email_input.clear()
        email_input.send_keys(EMAIL)
        pass_input.clear()
        pass_input.send_keys(PASSWORD)
        sleep(0.5)
        
        if safe_click(driver, By.CSS_SELECTOR, "a[login-btn].btn-small.btn-color-2.full-width.w-inline-block", 5):
            print("✅ Credenciais preenchidas e login confirmado.")
            sleep(5) 
        else:
            print("❌ Botão final de login não encontrado ou falha ao clicar.")
            return False
    else:
        print("⚠️ Campos de login não encontrados!")
        return False
        
    safe_click(driver, By.XPATH, "//button[contains(., 'Aceitar')]", 4)
    print("✅ Cookies aceitos (se aplicável).")
    sleep(1)

    if safe_click(driver, By.CSS_SELECTOR, "img.slot-game", 4):
        print("✅ Aviator aberto via imagem.")
    else:
        driver.get(LINK_AVIATOR)
        print("ℹ️ Indo direto para o Aviator via link.")
    sleep(10) 
    
    return True

# =============================================================
# 🚀 FUNÇÃO DE INICIALIZAÇÃO DO DRIVER (CORRIGIDA PARA DOCKER)
# =============================================================
def start_driver():
    """Inicializa o driver apontando para o Chromium do sistema."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-features=BlinkGenPropertyTrees")
    options.add_argument("--window-size=1920,1080")

    # Aponta para o binário do Chromium instalado pelo Dockerfile
    options.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/chromium") 
    
    # Aponta para o ChromeDriver do sistema
    service = Service(executable_path=os.environ.get("CHROME_DRIVER_PATH", "/usr/bin/chromedriver"))
    
    return webdriver.Chrome(service=service, options=options)


# =============================================================
# 🤖 LOOP PRINCIPAL DO BOT
# =============================================================
def start_bot(relogin_done_for: date = None):
    print("\n==============================================")
    print("         INICIALIZANDO GOATHBOT")
    print("==============================================")
    
    # Tenta inicializar o driver
    try:
        driver = start_driver()
    except Exception as e:
        print(f"❌ ERRO AO INICIAR DRIVER: {e}")
        return 

    def setup_game(driver):
        if not process_login(driver):
            return None, None
        
        iframe, hist = initialize_game_elements(driver) 
        if not hist:
            print("❌ Não conseguiu iniciar o jogo. Tentando novamente...")
            return None, None
        return iframe, hist

    iframe, hist = setup_game(driver)

    if not hist:
        driver.quit()
        return start_bot() 

    LAST_SENT = None
    ULTIMO_ENVIO = time() 
    ULTIMO_MULTIPLIER_TIME = time() 
    falhas = 0
    relogin_done_for = relogin_done_for if relogin_done_for else date.today() 

    print("✅ Captura iniciada.\n")

    while True:
        try:
            now_br = datetime.now(TZ_BR)

            # Lógica de Reinício Diário Programado
            if now_br.hour == 23 and now_br.minute >= 59 and (relogin_done_for != now_br.date()):
                print(f"🕛 REINÍCIO PROGRAMADO: Fechando bot às {now_br.strftime('%H:%M:%S')} para reabrir após 00:00.")
                driver.quit()
                print("💤 Bot offline por 1 minuto... (Reiniciando em 00:00:xx)")
                sleep(60) 
                return start_bot(relogin_done_for=now_br.date()) 

            # Lógica de Inatividade
            if (time() - ULTIMO_MULTIPLIER_TIME) > TEMPO_MAX_INATIVIDADE:
                 print(f"🚨 Inatividade por mais de 6 minutos! Último envio em: {datetime.fromtimestamp(ULTIMO_MULTIPLIER_TIME).strftime('%H:%M:%S')}. Reiniciando o bot...")
                 driver.quit()
                 return start_bot()

            # Tenta trocar para o iframe do jogo
            try:
                driver.switch_to.frame(iframe) 
            except Exception:
                driver.switch_to.default_content()
                iframe, hist = initialize_game_elements(driver) 
                if not hist:
                    print("⚠️ Falha crítica: Iframe/Histórico perdido. Reiniciando o bot...")
                    driver.quit()
                    return start_bot() 

            # === LEITURA DOS RESULTADOS ===
            resultados_texto = hist.text.strip() if hist else ""
            if not resultados_texto:
                falhas += 1
                if falhas > 5:
                    print("⚠️ Mais de 5 falhas de leitura. Tentando re-inicializar elementos...")
                    driver.switch_to.default_content()
                    iframe, hist = initialize_game_elements(driver)
                    falhas = 0
                sleep(1)
                continue
            
            falhas = 0

            # Processa e filtra os multiplicadores
            resultados = []
            seen = set()
            for n in resultados_texto.split("\n"):
                n = n.replace("x", "").strip()
                try:
                    if n:
                        v = float(n)
                        if v >= 1.0 and v not in seen:
                            seen.add(v)
                            resultados.append(v)
                except ValueError:
                    pass

            # Salva o novo resultado no Firebase
            if resultados:
                novo = resultados[0] 
                if (novo != LAST_SENT) and ((time() - ULTIMO_ENVIO) > INTERVALO_MINIMO_ENVIO):
                    
                    now = datetime.now()
                    now_br = now.astimezone(TZ_BR)

                    raw = f"{novo:.2f}"
                    date_str = now_br.strftime("%Y-%m-%d")
                    time_key = now_br.strftime("%H-%M-%S.%f")
                    time_display = now_br.strftime("%H:%M:%S")
                    color = getColorClass(novo)
                    
                    entry_key = f"{date_str}_{time_key}_{raw}x".replace(':', '-').replace('.', '-')
                    entry = {"multiplier": raw, "time": time_display, "color": color, "date": date_str}
                    
                    # Tenta salvar no Firebase (só funcionará se o Firebase foi inicializado com sucesso)
                    try:
                        db.reference(f"history/{entry_key}").set(entry)
                        print(f"🔥 {raw}x salvo às {time_display}")
                    except Exception as e:
                        print("⚠️ Erro ao salvar (Firebase pode não ter sido inicializado):", e)
                        
                    LAST_SENT = novo
                    ULTIMO_ENVIO = time()
                    ULTIMO_MULTIPLIER_TIME = time()
            
            # Volta para o conteúdo principal antes de esperar o polling (boa prática)
            driver.switch_to.default_content()
            sleep(POLLING_INTERVAL)

        except (StaleElementReferenceException, TimeoutException):
            print("⚠️ Elemento histórico obsoleto/sumiu. Recarregando elementos...")
            driver.switch_to.default_content()
            iframe, hist = initialize_game_elements(driver)
            continue

        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
            sleep(3)
            continue

# =============================================================
# ▶️ INÍCIO DO SCRIPT
# =============================================================
if __name__ == "__main__":
    if not EMAIL or not PASSWORD:
        print("\n❗ Configure as variáveis de ambiente EMAIL e PASSWORD ou defina-as diretamente no código.")
    else:
        start_bot(relogin_done_for=date.today())
