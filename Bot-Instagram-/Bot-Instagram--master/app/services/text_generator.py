import json
from queue import Queue
from typing import Any
from app.core.interfaces import IAIAPI, IAccountAPI
from .image_generator import ImageGeneratorService

class TextGeneratorService:
    def __init__(self, account_api: IAccountAPI, ia_api: IAIAPI, data: dict):
        self.account_api = account_api
        self.ia_api = ia_api
        self.image_service=ImageGeneratorService(account_api=self.account_api, ia_api=self.ia_api, data=data)
        self.data = data

    def generate_text_post(self):

        print("Generando texto...")
        ia = self.account_api
        used_messages = ia.get_comments(self.data["social_media_account"]["id"])
        extra_prompt = f'''
        No repitas ningún mensaje que ya haya sido utilizado anteriormente.
        
        used_messages = {used_messages}

        La variable used_messages contiene una lista de textos ya publicados. 
        Debes asegurarte de que el nuevo "message_text" sea completamente diferente a cualquiera de los textos contenidos en used_messages.

        Si el mensaje generado es similar en estructura, intención o redacción a alguno en used_messages, debes reformularlo hasta que sea claramente distinto.

        Está prohibido reutilizar frases, aperturas o cierres ya presentes en used_messages.
        '''

        personalidad = self.data["social_media_account"]["bot_personality"]["id"]
        rta, text_post = self.ia_api.get_bot_ia(
            personalidad,
            ("""
            Genera un mensaje listo para publicar en mi muro de Instagram, con estilo de pensamiento personal (reflexión, idea del día, aprendizaje, opinión suave o sentimiento). Debe poder publicarse solo como texto, sin depender de fotos, videos, links, noticias o contenido visual.

            La respuesta debe ser únicamente un JSON válido (sin texto adicional, sin explicaciones y sin bloques de código).

            El JSON debe tener exactamente esta estructura:

            {
            "message_text": "texto del mensaje aquí",
            "metadata": {
                "tone": "tonalidad del mensaje",
                "focus": "enfoque principal",
                "theme": "tema general",
                "mood": "estado de ánimo transmitido",
                "intent": "objetivo del mensaje"
            }
            }
            """ ) + extra_prompt,
        )

        if rta and text_post:
            data = json.loads(text_post)
            print(data)
            print(f"mensaje: {data['message_text']}")
            message = data['message_text']
            try:
                ia.save_new_comment(self.data["social_media_account"]["id"], message, 'publicacion', data['metadata'])
                print('comentario guardado exitosamente')
            except Exception as e:
                print("error al guardar el comentario en la bd: " + str(e))
                
            print("Fin Generando texto")
            return(True, message)
        
        else:
            print("error al obtener el mensaje")
            return (False, None)
            
