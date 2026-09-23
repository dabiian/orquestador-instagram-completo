import json
from typing import Any, Tuple
from selenium.webdriver.common.by import By
from app.core.interfaces import IAIAPI, IAccountAPI

class ImageGeneratorService:
    def __init__(self, account_api: IAccountAPI, ia_api: IAIAPI, data: dict):
        self.account_api = account_api
        self.ia_api = ia_api
        self.data = data

    def generate_image(self, text_post: str) -> Tuple[bool, Any]:
        
        ia = self.account_api
        print("Generando imagen...")
        used_prompts = ia.get_comments(self.data["social_media_account"]["id"], category="img_prompts_v1")
        personalida = self.data["social_media_account"]["bot_personality"]["id"]
        
        structure = """
        {
                "message_text": "PROMPT FINAL PARA GENERAR LA IMAGEN (en una sola cadena de texto)",
                "metadata": {
                    "tone": "tonalidad del mensaje del post",
                    "focus": "enfoque principal del post",
                    "theme": "tema general del post",
                    "mood": "estado de ánimo transmitido por el post",
                    "intent": "objetivo del post"
                    }
            }

        """
        rta, prompt_img = self.ia_api.get_bot_ia(
            personalida,
            f"""
            Crea un PROMPT para generar una imagen que acompañe perfectamente el siguiente post:

            {text_post}

            Objetivo:
            - La imagen debe estar totalmente relacionada con la idea central del texto (tema y emoción).
            - Debe ser sencilla y clara: pocos elementos, un foco principal, composición limpia.
            - Puede ser realista o ilustrada (elige el estilo que mejor traduzca el mensaje). Preferir foto realista cuando el post NO sea reflexivo; si el post es reflexivo/emocional, prioriza minimalismo o simbolismo.

            Reglas obligatorias:
            - No inventes escenas complejas ni elementos que se alejen del tema.
            - Evita exceso de detalles: 1–3 elementos clave máximo.
            - Si el post es reflexivo o emocional, usa metáforas visuales simples en lugar de escenas complejas.
            - No incluir texto, letras, frases, marcas de agua, logotipos, ni tipografía dentro de la imagen.
            - Fondo simple, sin ruido visual.

            Evitar duplicados de prompts (NO negociable):
            - No repitas ningún prompt que ya haya sido utilizado anteriormente.

            used_messages = {used_prompts}

            Instrucciones de salida (NO negociable):
            - La respuesta debe ser únicamente un JSON válido (sin texto adicional, sin explicaciones y sin bloques de código).
            - El JSON debe tener exactamente esta estructura:

            {structure}
            """,
        )
        if rta:
            data = json.loads(prompt_img)
            message = data['message_text']
            ia.save_new_comment(self.data["social_media_account"]["id"], message, "img_prompts_v1", data['metadata'])
            resultado, link = self.ia_api.get_bot_ia_image(message)
            if resultado:
                print(f"link imagen: {link}")
                src_img = ia.download_image(link["image_url"], "image.jpg")
                print("Fin Generando imagen...")
                print(src_img)
                return (resultado, src_img)
            else:
                return (False, None)
        else:
            print("sin prompt de la foto")
            return (False, None)
        
