import requests

class ProxyValidator:

    def validate(self, proxy_ip: str, proxy_port: str,
                 proxy_user: str, proxy_password: str) -> bool:
        proxies = {
            "http": f"http://{proxy_user}:{proxy_password}@{proxy_ip}:{proxy_port}",
            "https": f"http://{proxy_user}:{proxy_password}@{proxy_ip}:{proxy_port}",
        }
        try:
            response = requests.get(
                "https://www.facebook.com/", proxies=proxies, timeout=5
            )
            return response.status_code == 200
        except requests.exceptions.ProxyError:
            print("Error de Proxy")
        except requests.exceptions.ConnectTimeout:
            print("Tiempo de conexión agotado")
        except requests.exceptions.SSLError:
            print("Error SSL, posible problema con el proxy HTTPS")
        except requests.exceptions.RequestException as e:
            print(f"Error al realizar la solicitud: {e}")
        return False