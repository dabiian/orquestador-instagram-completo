from django.db import models

class ActiveWebSocketConnection(models.Model):
    channel_name = models.CharField(max_length=255, unique=True)
    room = models.CharField(max_length=255)
    ip = models.GenericIPAddressField()
    connected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'dashboard'