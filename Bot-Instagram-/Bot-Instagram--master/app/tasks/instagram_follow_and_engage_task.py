"""app/tasks/instagram_follow_and_engage_task.py

Tarea RPA para Instagram: Buscar posts con "sígueme y te sigo", responder comentarios,
seguir al usuario y comentar "ya te sigo, sígueme también".
"""

import json
import random
import time

from app.core.interfaces import IBrowser, IAIAPI, IAccountAPI, ITask
from app.config import settings
from app.utils.logger import get_logger
from app.services.instagram_safety_gate import InstagramSafetyGate


class InstagramFollowAndEngageTask(ITask):
    """
    Busca posts con keywords "sígueme y te sigo", interactúa con ellos:
    - Sigue al usuario
    - Comenta respondiendo a la llamada a la acción
    """
    
    def __init__(self, browser: IBrowser, ai_api: IAIAPI, account_api: IAccountAPI, data: dict):
        self.browser = browser
        self.ai_api = ai_api
        self.account_api = account_api
        self.data = data
        self.log = get_logger(self.__class__.__name__)
        campaign_type = (self.data.get("campaign_type") or (self.data.get("custom_task") or {}).get("campaign_type") or "botanica")
        self.safety_gate = InstagramSafetyGate(campaign_type)

    def execute(self) -> str:
        """Ejecuta la tarea de buscar y responder a 'sígueme y te sigo'."""
        try:
            self.log.info("Iniciando tarea: Buscar y responder 'sígueme y te sigo'")
            
            # ─── PASO 1: CONFIGURACIÓN ──────────────────────────────
            search_keywords = ["sígueme y te sigo", "follow me and i follow you", "f4f", "l4l"]
            num_interactions = self.data.get("custom_task", {}).get("num_interactions") or 3
            
            self.log.info("Palabras clave: %s, Interacciones: %d", search_keywords, num_interactions)
            
            # ─── PASO 2: IR A EXPLORAR/BUSCAR ──────────────────────
            explore_url = "https://www.instagram.com/explore/"
            self.browser.go_to_url(explore_url)
            self.log.info("Navegando a explorar: %s", explore_url)
            
            time.sleep(random.uniform(3, 6))
            
            # ─── PASO 3: BUSCAR POSTS CON KEYWORDS ─────────────────
            interactions_done = 0
            attempts = 0
            max_attempts = 15
            
            while interactions_done < num_interactions and attempts < max_attempts:
                attempts += 1
                
                try:
                    # Buscar todos los posts visibles (artículos)
                    posts_xpath = "//article"
                    posts = self.browser.obtener_elementos(posts_xpath, timeX=5)
                    
                    if not posts:
                        self.log.warning("No se encontraron posts, scrolleando...")
                        self.browser.scroll_to_xpath(posts_xpath, timeX=5)
                        time.sleep(random.uniform(2, 4))
                        continue
                    
                    # Seleccionar un post aleatorio
                    post = random.choice(posts)
                    
                    # Hacer clic para abrir el post
                    self.browser.click(posts_xpath, timeX=5, scroll=False)
                    time.sleep(random.uniform(2, 4))
                    
                    # ─── VERIFICAR SI EL POST TIENE "SÍGUEME Y TE SIGO" ───
                    post_text_xpath = "//span[contains(text(), 'sígueme') or contains(text(), 'follow me') or contains(text(), 'f4f')]"
                    
                    # Obtener todos los comentarios visibles
                    comments_xpath = "//ul//li"
                    comments = self.browser.obtener_elementos(comments_xpath, timeX=3)
                    
                    post_has_keyword = False
                    
                    # Verificar si algún comentario contiene la palabra clave
                    for keyword in search_keywords:
                        if self.browser.is_visible(f"//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"):
                            post_has_keyword = True
                            self.log.info("Post encontrado con keyword: %s", keyword)
                            break
                    
                    if not post_has_keyword and comments:
                        # Verificar en los textos de comentarios
                        for keyword in search_keywords:
                            for comment in comments:
                                try:
                                    comment_text = comment.text.lower()
                                    if keyword in comment_text:
                                        post_has_keyword = True
                                        self.log.info("Comentario encontrado con keyword: %s", keyword)
                                        break
                                except:
                                    continue
                            if post_has_keyword:
                                break
                    
                    if not post_has_keyword:
                        self.log.debug("Post no contiene keywords relevantes, pasando al siguiente")
                        self.browser.go_back_page()
                        time.sleep(random.uniform(1, 3))
                        continue
                    
                    # ─── INTERACCIÓN 1: SEGUIR AL USUARIO ───────────
                    follow_btn_xpath = "//button[contains(text(), 'Seguir')]"
                    account_key = str(self.data.get("target_username") or self.data.get("username") or f"followback-{attempts}")
                    if self.browser.is_visible(follow_btn_xpath):
                        try:
                            can_follow, reason = self.safety_gate.allow("follow", account_key, commit=False)
                            if can_follow:
                                self.browser.click(follow_btn_xpath, timeX=5)
                                self.safety_gate.allow("follow", account_key, commit=True)
                                self.log.info("Usuario seguido")
                                time.sleep(random.uniform(1, 2))
                            else:
                                self.log.info("[safety-gate] follow omitido: %s", reason)
                        except Exception:
                            self.log.debug("Error al seguir usuario")
                    
                    # ─── INTERACCIÓN 2: COMENTAR ────────────────────
                    comment_btn_xpath = "//button[@aria-label='Comentar']"
                    if self.browser.is_visible(comment_btn_xpath):
                        try:
                            self.browser.click(comment_btn_xpath, timeX=5)
                            time.sleep(random.uniform(1, 3))
                            
                            # Campo de comentario
                            comment_input_xpath = "//textarea[@aria-label='Añade un comentario...']"
                            if self.browser.is_visible(comment_input_xpath):
                                # Mensajes variados de respuesta
                                respuestas = [
                                    "Ya te sigo! Sígueme también 👍",
                                    "Listo, ya te seguí! 🔔",
                                    "Hecho! Siguiente a ti ahora 😊",
                                    "Ya estoy siguiendo! Retribución? 👊",
                                    "Te sigo! Espero que hagas lo mismo 🙌"
                                ]
                                comment_text = random.choice(respuestas)
                                
                                self.browser.click(comment_input_xpath, timeX=5)
                                time.sleep(random.uniform(0.5, 1))
                                self.browser.write_text(comment_input_xpath, comment_text, fast_t=0.05)
                                
                                # Botón enviar comentario
                                submit_btn_xpath = "//button[contains(text(), 'Publicar')]"
                                if self.browser.is_visible(submit_btn_xpath):
                                    self.browser.click(submit_btn_xpath, timeX=5)
                                    self.log.info("Comentario publicado: %s", comment_text)
                                    time.sleep(random.uniform(1, 2))
                        except Exception as e:
                            self.log.warning("Error al comentar: %s", str(e))
                    
                    # ─── INTERACCIÓN 3: DAR LIKE ────────────────────
                    like_btn_xpath = "//button[@aria-label='Me gusta']"
                    if self.browser.is_visible(like_btn_xpath):
                        try:
                            can_like, reason = self.safety_gate.allow("like", account_key, commit=False)
                            if can_like:
                                self.browser.click(like_btn_xpath, timeX=5)
                                self.safety_gate.allow("like", account_key, commit=True)
                                self.log.info("Like agregado")
                                time.sleep(random.uniform(1, 2))
                            else:
                                self.log.info("[safety-gate] like omitido: %s", reason)
                        except Exception:
                            self.log.debug("Error al dar like")
                    
                    interactions_done += 1
                    self.log.info("Interacción %d/%d completada exitosamente", interactions_done, num_interactions)
                    
                    # Volver al feed
                    self.browser.go_back_page()
                    time.sleep(random.uniform(3, 6))
                    
                except Exception as e:
                    self.log.warning("Error en interacción: %s", str(e))
                    try:
                        self.browser.go_back_page()
                    except:
                        pass
                    time.sleep(random.uniform(2, 4))
                    continue
            
            # ─── PASO 4: REPORTE ────────────────────────────────────
            if interactions_done > 0:
                resultado = {
                    "interacciones_completadas": interactions_done,
                    "accion": "Seguir + Comentar 'ya te sigo' en posts de 'sígueme y te sigo'",
                    "mensaje": f"✓ Se realizaron {interactions_done} interacciones de follow-back"
                }
                self.log.info("Tarea completada: %s", resultado)
                
                # Guardar en DB
                self.account_api.save_new_comment(
                    account_id=self.data["social_media_account"]["id"],
                    message_text=f"Follow-back: Seguir + Comentar en {interactions_done} posts",
                    category="interaccion",
                    metadata=resultado
                )
                
                return f"✓ {resultado['mensaje']}"
            else:
                return "✗ No se pudieron completar interacciones (no se encontraron posts 'sígueme y te sigo')"
            
        except Exception as e:
            self.log.exception("Error ejecutando InstagramFollowAndEngageTask")
            return f"✗ Error: {str(e)}"
