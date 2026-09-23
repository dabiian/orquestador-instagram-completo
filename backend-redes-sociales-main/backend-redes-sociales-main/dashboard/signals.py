from django.db.models.signals import post_save
from django.dispatch import receiver
import requests
from .models.proxy import Proxy
from .models.social_media_account import SocialMediaAccount


@receiver(post_save, sender=SocialMediaAccount)
def asignar_proxy_a_cuenta(sender, instance, created, **kwargs):
    if created and not instance.proxy:
        respuesta_api = obtener_datos_proxy()
        if respuesta_api:
            proxy = Proxy.objects.create(
                ip_address=respuesta_api["proxy_address"],
                port=respuesta_api["port"],
                username=respuesta_api.get("username", None),
                password=respuesta_api.get("password", None),
            )
            instance.proxy = proxy
            instance.save()


def obtener_datos_proxy():
    url = "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=2&page_size=25&country_code__in=US"
    headers = {"Authorization": "Token kcxe9dexex23qivam7jhh4pq3t7jx2rho632htf4"}

    try:
        respuesta = requests.get(url, headers=headers)
        if respuesta.status_code == 200:
            data = respuesta.json()
            for proxy_data in data["results"]:
                # Asegúrate de que el proxy está marcado como válido
                if (
                    proxy_data["valid"]
                    and not Proxy.objects.filter(
                        ip_address=proxy_data["proxy_address"], port=proxy_data["port"]
                    ).exists()
                ):
                    return proxy_data
    except Exception as e:
        print(f"Error al obtener datos de proxy: {e}")

    return None
